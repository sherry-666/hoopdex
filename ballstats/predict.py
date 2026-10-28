"""Game prediction for the days ahead.

margin (home minus away, points) =
    K * (rating gap on the game day) + HOME_EDGE + fit + matchup

  rating gap   each team's rating (feat.team_profile, built with today's injury report) corrected for who can
               actually play on the game day: a player listed Out is left out unless his return date is on or before
               that day; day-to-day players count at teams.DAY_TO_DAY_FACTOR. The correction is the change in the
               rotation's minutes-weighted rating (teams._roster_with_injuries), in team-rating points.
  fit          the team's NUM_KEY best-rated players among those fully able to play that day, pairwise: do two such kinds of player share the
               floor better or worse than their own levels predict (feat.role_synergy, offence and defence).
  matchup      each side's key players against the other side's key players: offence archetype x defence archetype
               (feat.role_matchup, pooled seasons).

K, HOME_EDGE and SIGMA come from regressing 13212 regular-season games of 2015-16..2025-26 on the end-of-season
rating gap (in-sample, so K leans high). The fit and matchup tables were backtested and add next to nothing
(matchup.py, lineup_synergy.py): they are scaled down (STAR_SHARE), capped, and reported as their own lines so the
page can show them apart from the rating-based margin.
"""

import datetime as dt
import math

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import tuple_row

from ballstats import blend, live, teams

NUM_KEY = 5                     # the key players: the five best rated among those able to play that day
                                # (by rating, not minutes: early in a season minutes are a few games' worth)
K = 0.79                        # points of margin per team-rating point
HOME_EDGE = 2.15
SIGMA = 13.1                    # sd of a game's margin around the prediction
FIT_OVERLAP = 0.5               # share of a game two stars are on the floor together
MATCHUP_POSS = 4                # partial possessions of one star-pair matchup per game
STAR_SHARE = 0.25               # the pair tables explain next to nothing held out: count a quarter of them
COMPONENT_CAP = 1.5             # and never more than this many points each


def can_play(status: str | None, return_date: dt.date | None, day: dt.date) -> float:
    """Availability on a given day: 0 when out through it (or out with no return date), else 1 (day-to-day: DAY_TO_DAY_FACTOR)."""
    if status == "Out":
        return 1.0 if return_date is not None and return_date <= day else 0.0
    return teams.DAY_TO_DAY_FACTOR if status else 1.0


def _load(conn: psycopg.Connection, season: str):
    rows = conn.execute(
        """
        SELECT s.team, s.player_id, s.name, s.minutes, rt.ovr, rt.off, rt.def,
               (SELECT top_archetype_id FROM feat.player_role r WHERE r.season = s.season AND r.player_id = s.player_id AND r.side = 'offense') AS off_type,
               (SELECT top_archetype_id FROM feat.player_role r WHERE r.season = s.season AND r.player_id = s.player_id AND r.side = 'defense') AS def_type
        FROM feat.player_stats s LEFT JOIN feat.player_rating rt USING (season, player_id)
        WHERE s.season = %s AND s.team IS NOT NULL
        """, (season,)).fetchall()
    df = pd.DataFrame(rows, columns=["team", "pid", "name", "min", "ovr", "off", "def", "off_type", "def_type"])
    for c in ("min", "ovr", "off", "def"):
        df[c] = df[c].astype(float)
    inj = {pid: (status, ret) for pid, status, ret in conn.execute(
        "SELECT DISTINCT ON (player_id) player_id, status, return_date FROM live.injury WHERE player_id IS NOT NULL"
        " ORDER BY player_id, reported_at DESC NULLS LAST")}
    return df, inj


def _rotation_ovr(df: pd.DataFrame, hurt: dict[int, float], replacement: pd.Series) -> float:
    off = df.sort_values("min", ascending=False)
    top = off.head(teams.NUM_ROTATION).dropna(subset=["ovr"])
    if not len(top):
        return float("nan")
    return teams._roster_with_injuries(top, off.dropna(subset=["ovr"]), hurt, replacement)["ovr"]


def _pair_effects(conn: psycopg.Connection):
    syn = {(s, a, b): e for s, a, b, e in conn.execute("SELECT side, type_a, type_b, effect FROM feat.role_synergy")}
    mat = {(o, d): e for o, d, e in conn.execute("SELECT off_type, def_type, effect FROM feat.role_matchup WHERE season = 'all'")}
    return syn, mat


def _cap(v: float) -> float:
    return max(-COMPONENT_CAP, min(COMPONENT_CAP, v))


def _able(df: pd.DataFrame, team: str, inj: dict, day: dt.date) -> pd.DataFrame:
    """The team's rated players who can play in full on the day (out or day-to-day players are left out)."""
    t = df[(df.team == team) & df.ovr.notna()].copy()
    t["avail"] = [can_play(*inj.get(p, (None, None)), day) for p in t.pid]
    return t[t.avail == 1]


def _key_players(df: pd.DataFrame, team: str, inj: dict, day: dt.date) -> pd.DataFrame:
    return _able(df, team, inj, day).sort_values("ovr", ascending=False).head(NUM_KEY)


def _fit(stars: pd.DataFrame, syn: dict) -> float:
    s = stars
    total = 0.0
    for side, col in (("offense", "off_type"), ("defense", "def_type")):
        types = [int(x) for x in s[col].dropna()]
        for i in range(len(types)):
            for j in range(i + 1, len(types)):
                total += syn.get((side, min(types[i], types[j]), max(types[i], types[j])), 0.0)
    return _cap(total * FIT_OVERLAP * STAR_SHARE)   # per 100 possessions ~ points per game


def _matchup(mine: pd.DataFrame, theirs: pd.DataFrame, mat: dict) -> float:
    """What my stars' offence gains or loses against their stars' defence, in points per game."""
    a, d = mine.dropna(subset=["off_type"]), theirs.dropna(subset=["def_type"])
    if a.empty or d.empty:
        return 0.0
    per_star = [np.mean([mat.get((int(o), int(x)), 0.0) for x in d.def_type]) for o in a.off_type]
    return _cap(sum(per_star) / 100 * MATCHUP_POSS * STAR_SHARE)


def predict(conn: psycopg.Connection, away: str, home: str, day: dt.date) -> dict:
    """One game on a given day."""
    return predict_many(conn, [(away, home, day)])[0]


def predict_many(conn: psycopg.Connection, games: list[tuple[str, str, dt.date]]) -> list[dict]:
    """Several games sharing one load of the season's players; runs with tuple rows on the connection
    (the API pool hands out dict rows)."""
    saved, conn.row_factory = conn.row_factory, tuple_row
    try:
        ctx = _context(conn)
        return [_game(ctx, away, home, day) for away, home, day in games]
    finally:
        conn.row_factory = saved


def _context(conn: psycopg.Connection) -> dict:
    season = blend.ongoing_season(conn) or conn.execute("SELECT max(season) FROM feat.team_profile").fetchone()[0]
    df, inj = _load(conn, season)
    today = dt.datetime.now(live.EASTERN).date()
    hurt_now = {p: f for p, (st, ret) in inj.items() if (f := teams.availability(st, ret, today)) < 1}
    replacement = df.drop_duplicates("pid")[["ovr", "off", "def"]].quantile(teams.REPLACEMENT_QUANTILE)
    return {
        "season": season, "df": df, "inj": inj, "hurt_now": hurt_now, "replacement": replacement,
        "league_sd": float(np.nanstd([_rotation_ovr(g, hurt_now, replacement) for _, g in df.groupby("team")])),
        "rating": dict(conn.execute("SELECT team, ovr FROM feat.team_profile WHERE season = %s", (season,)).fetchall()),
        "pairs": _pair_effects(conn),
    }


def _game(ctx: dict, away: str, home: str, day: dt.date) -> dict:
    df, inj, replacement = ctx["df"], ctx["inj"], ctx["replacement"]
    hurt_day = {p: f for p, (st, ret) in inj.items() if (f := can_play(st, ret, day)) < 1}
    side = {}
    for team in (away, home):
        g = df[df.team == team]
        shift = (_rotation_ovr(g, hurt_day, replacement) - _rotation_ovr(g, ctx["hurt_now"], replacement)) / ctx["league_sd"] * teams.TEAM_SD
        side[team] = float(ctx["rating"][team]) + (0.0 if math.isnan(shift) else shift)
    syn, mat = ctx["pairs"]
    sa, sh = _key_players(df, away, inj, day), _key_players(df, home, inj, day)
    fit = _fit(sh, syn) - _fit(sa, syn)
    matchup = _matchup(sh, sa, mat) - _matchup(sa, sh, mat)
    base = K * (side[home] - side[away]) + HOME_EDGE
    margin = base + fit + matchup
    key_rows = lambda s: [{"player_id": int(r.pid), "name": r["name"], "ovr": int(r.ovr)} for _, r in s.sort_values("ovr", ascending=False).iterrows()]
    best = lambda team: int(_able(df, team, inj, day).sort_values("ovr", ascending=False).pid.iloc[0]) if len(_able(df, team, inj, day)) else None
    return {
        "season": ctx["season"], "date": day.isoformat(), "away": away, "home": home,
        "rating": {away: round(float(side[away]), 1), home: round(float(side[home]), 1)},
        "base_margin": round(float(base), 1), "fit": round(float(fit), 2), "matchup": round(float(matchup), 2),
        "margin": round(float(margin), 1), "home_win": round(0.5 * (1 + math.erf(margin / SIGMA / math.sqrt(2))), 3),
        "key_players": {away: key_rows(sa), home: key_rows(sh)}, "best_player": {away: best(away), home: best(home)},
    }
