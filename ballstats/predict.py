"""Game prediction for the days ahead.

margin (home minus away, points) =
    HOME_EDGE + C_ROSTER * (roster rating gap on the game day) + C_FORM * (recent-form gap)
              + back-to-back + matchup

  roster       each team's rotation, minutes-weighted player ratings (minutes per game played, so a star with few games
               still counts), with who can actually play on the game day: a player listed Out is left out unless his
               return date is on or before that day; day-to-day players count at teams.DAY_TO_DAY_FACTOR. The minutes an
               absence frees go to weaker teammates (teams._roster_with_injuries). Season-level data say a team loses
               about INJURY_AMP times what that reshuffle alone predicts (the system has to be rebuilt), so the injury
               part is scaled by INJURY_AMP.
  form         mean margin of the team's last FORM_GAMES games this season, shrunk toward 0 by FORM_SHRINK pseudo-games.
  back-to-back a team that also played the day before loses BACK_TO_BACK points (fatigue), either side.
  matchup      each side's key players (the NUM_KEY best rated able to play) against the other side's: offence
               archetype x defence archetype (feat.role_matchup, pooled seasons). Scaled down (STAR_SHARE) and capped.
  fit          shown (feat.role_synergy pairs of the key players) but not part of the margin: in the backtest it
               explains nothing.

The coefficients come from scripts/backtest_predictor.py (2016-17..2025-26, 11982 games, leave-one-season-out:
64% right with roster + back-to-back, 66% with form; always picking the home team is 56%). That backtest has
no per-game injuries; INJURY_AMP is fitted on team-season games missed (300 team-seasons, see the commit message).
"""

import datetime as dt
import math

import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb

from ballstats import blend, live, teams

NUM_KEY = 5                     # the key players: the five best rated among those able to play that day
                                # (by rating, not minutes: early in a season minutes are a few games' worth)
HOME_EDGE = 2.0
C_ROSTER = 0.78                 # points of margin per point of rotation rating
C_FORM = 0.73                   # points of margin per point of (shrunk) recent average margin
FORM_GAMES, FORM_SHRINK, MIN_FORM = 20, 10, 3
INJURY_AMP = 1.8                # an absence costs this times what moving its minutes to weaker teammates predicts
BACK_TO_BACK = 2.3              # points a team loses when it also played the day before
SIGMA = 13.5                    # sd of a game's margin around the prediction
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
        SELECT s.team, s.player_id, s.name, s.minutes / greatest(s.gp, 1), rt.ovr, rt.off, rt.def,
               (SELECT top_archetype_id FROM feat.player_role r WHERE r.season = s.season AND r.player_id = s.player_id AND r.side = 'offense') AS off_type,
               (SELECT top_archetype_id FROM feat.player_role r WHERE r.season = s.season AND r.player_id = s.player_id AND r.side = 'defense') AS def_type
        FROM feat.player_stats s LEFT JOIN feat.player_rating rt USING (season, player_id)
        WHERE s.season = %s AND s.team IS NOT NULL
        """, (season,)).fetchall()
    df = pd.DataFrame(rows, columns=["team", "pid", "name", "min", "ovr", "off", "def", "off_type", "def_type"])   # min: per game played
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


def _game_days(conn: psycopg.Connection, season: str) -> dict[str, set[dt.date]]:
    """The dates each team plays this season, played or still to come (US Eastern)."""
    days: dict[str, set[dt.date]] = {}
    for team, d in conn.execute("SELECT team, game_date FROM live.game WHERE season = %s", (season,)):
        days.setdefault(team, set()).add(d)
    return days


def _margins(conn: psycopg.Connection, season: str) -> dict[str, list[tuple[dt.date, float]]]:
    """Each team's finished regular-season games this season in date order, as (date, margin)."""
    out: dict[str, list[tuple[dt.date, float]]] = {}
    for team, d, m in conn.execute("SELECT team, game_date, team_score - opp_score FROM live.game"
                                   " WHERE season = %s AND season_type = 2 AND completed AND team_score IS NOT NULL"
                                   " ORDER BY game_date", (season,)):
        out.setdefault(team, []).append((d, float(m)))
    return out


def _form(margins: list[tuple[dt.date, float]], day: dt.date) -> float:
    """Recent form before `day`: sum of the last FORM_GAMES margins over (games + FORM_SHRINK); 0 until MIN_FORM games."""
    ms = [m for d, m in margins if d < day][-FORM_GAMES:]
    return sum(ms) / (len(ms) + FORM_SHRINK) if len(ms) >= MIN_FORM else 0.0


def _cap(v: float) -> float:
    return max(-COMPONENT_CAP, min(COMPONENT_CAP, v))


def _able(df: pd.DataFrame, team: str, inj: dict, day: dt.date) -> pd.DataFrame:
    """The team's rated players who can play in full on the day (out or day-to-day players are left out)."""
    t = df[(df.team == team) & df.ovr.notna()].copy()
    t["avail"] = [can_play(*inj.get(p, (None, None)), day) for p in t.pid]
    return t[t.avail == 1]


def _key_players(df: pd.DataFrame, team: str, inj: dict, day: dt.date) -> pd.DataFrame:
    return _able(df, team, inj, day).sort_values("ovr", ascending=False).head(NUM_KEY)


def _fit_items(team: str, stars: pd.DataFrame, syn: dict, names: dict) -> list[dict]:
    """Every pair of the team's key players on one side, with what the pair's kinds do together in points per game
    (before the cap)."""
    items = []
    for side, col in (("offense", "off_type"), ("defense", "def_type")):
        rows = [r for _, r in stars.dropna(subset=[col]).iterrows()]
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                ta, tb = int(rows[i][col]), int(rows[j][col])
                eff = syn.get((side, min(ta, tb), max(ta, tb)), 0.0)
                items.append({"team": team, "side": side, "effect": round(float(eff), 2),
                              "points": round(float(eff * FIT_OVERLAP * STAR_SHARE), 2),
                              "a": {"name": rows[i]["name"], "type": names.get((side, ta))},
                              "b": {"name": rows[j]["name"], "type": names.get((side, tb))}})
    return sorted(items, key=lambda x: -abs(x["points"]))


def _matchup_items(mine: str, attackers: pd.DataFrame, defenders: pd.DataFrame, mat: dict, names: dict) -> list[dict]:
    """My key players' offence against each of their key players' defence, in points per game for my team (before the
    cap). Each attacker's effect is the average over the defenders, so the points add up to the team's matchup."""
    a, d = attackers.dropna(subset=["off_type"]), defenders.dropna(subset=["def_type"])
    items = []
    for _, x in a.iterrows():
        for _, y in d.iterrows():
            eff = mat.get((int(x.off_type), int(y.def_type)), 0.0)
            items.append({"team": mine, "effect": round(float(eff), 2),
                          "points": round(float(eff / 100 * MATCHUP_POSS * STAR_SHARE / len(d)), 2),
                          "off": {"name": x["name"], "type": names.get(("offense", int(x.off_type)))},
                          "def": {"name": y["name"], "type": names.get(("defense", int(y.def_type)))}})
    return sorted(items, key=lambda i: -abs(i["points"]))


def _total(items: list[dict]) -> float:
    return _cap(sum(i["points"] for i in items))


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
    replacement = df.drop_duplicates("pid")[["ovr", "off", "def"]].quantile(teams.REPLACEMENT_QUANTILE)
    return {
        "season": season, "df": df, "inj": inj, "replacement": replacement,
        "pairs": _pair_effects(conn),
        "game_days": _game_days(conn, season),
        "margins": _margins(conn, season),
        "type_names": {(side, tid): name for side, tid, name in conn.execute(
            "SELECT side, type_id, name FROM feat.role_type WHERE level = 'archetype'"
            " AND season = (SELECT max(season) FROM feat.role_type WHERE level = 'archetype')")},
    }


def _game(ctx: dict, away: str, home: str, day: dt.date) -> dict:
    df, inj, replacement = ctx["df"], ctx["inj"], ctx["replacement"]
    hurt_day = {p: f for p, (st, ret) in inj.items() if (f := can_play(st, ret, day)) < 1}
    healthy, played, eff, form = {}, {}, {}, {}
    for team in (away, home):
        g = df[df.team == team]
        healthy[team] = _rotation_ovr(g, {}, replacement)
        played[team] = _rotation_ovr(g, hurt_day, replacement)
        eff[team] = healthy[team] + INJURY_AMP * (played[team] - healthy[team])
        form[team] = _form(ctx["margins"].get(team, []), day)
    injury_hit = {t: C_ROSTER * INJURY_AMP * (played[t] - healthy[t]) for t in (away, home)}
    syn, mat = ctx["pairs"]
    sa, sh = _key_players(df, away, inj, day), _key_players(df, home, inj, day)
    names = ctx["type_names"]
    fit_items = {away: _fit_items(away, sa, syn, names), home: _fit_items(home, sh, syn, names)}
    match_items = {away: _matchup_items(away, sa, sh, mat, names), home: _matchup_items(home, sh, sa, mat, names)}
    fit = _total(fit_items[home]) - _total(fit_items[away])
    matchup = _total(match_items[home]) - _total(match_items[away])
    roster = C_ROSTER * (eff[home] - eff[away])
    form_gap = C_FORM * (form[home] - form[away])
    tired = {team: (day - dt.timedelta(days=1)) in ctx["game_days"].get(team, ()) for team in (away, home)}
    rest = BACK_TO_BACK * (tired[away] - tired[home])
    margin = HOME_EDGE + roster + form_gap + rest + matchup
    key_rows = lambda s: [{"player_id": int(r.pid), "name": r["name"], "ovr": int(r.ovr)} for _, r in s.sort_values("ovr", ascending=False).iterrows()]
    best = lambda team: int(_able(df, team, inj, day).sort_values("ovr", ascending=False).pid.iloc[0]) if len(_able(df, team, inj, day)) else None
    return {
        "season": ctx["season"], "date": day.isoformat(), "away": away, "home": home,
        "home_edge": HOME_EDGE, "roster": round(float(roster), 2), "form": round(float(form_gap), 2),
        "injury_hit": {t: round(float(v), 2) for t, v in injury_hit.items()},
        "rest": round(float(rest), 2), "back_to_back": tired, "fit": round(float(fit), 2), "matchup": round(float(matchup), 2),
        "margin": round(float(margin), 1), "home_win": round(0.5 * (1 + math.erf(margin / SIGMA / math.sqrt(2))), 3),
        "fit_items": fit_items, "matchup_items": match_items, "component_cap": COMPONENT_CAP,
        "key_players": {away: key_rows(sa), home: key_rows(sh)}, "best_player": {away: best(away), home: best(home)},
        "inputs": {
            "rotation_healthy": {t: _num(healthy[t]) for t in (away, home)},
            "rotation_on_day": {t: _num(played[t]) for t in (away, home)},
            "rotation_effective": {t: _num(eff[t]) for t in (away, home)},
            "form": {t: _num(form[t]) for t in (away, home)},
            "games_played": {t: sum(1 for d, _ in ctx["margins"].get(t, []) if d < day) for t in (away, home)},
            "constants": {"HOME_EDGE": HOME_EDGE, "C_ROSTER": C_ROSTER, "C_FORM": C_FORM, "FORM_GAMES": FORM_GAMES,
                          "FORM_SHRINK": FORM_SHRINK, "INJURY_AMP": INJURY_AMP, "BACK_TO_BACK": BACK_TO_BACK,
                          "SIGMA": SIGMA, "STAR_SHARE": STAR_SHARE, "COMPONENT_CAP": COMPONENT_CAP},
        },
        "injuries": [
            {"team": r.team, "player_id": int(r.pid), "name": r["name"], "status": inj[r.pid][0],
             "return_date": inj[r.pid][1].isoformat() if inj[r.pid][1] else None,
             "available": can_play(*inj[r.pid], day), "ovr": _num(r.ovr), "min": _num(r["min"])}
            for _, r in df[df.team.isin((away, home)) & df.pid.isin(inj)].sort_values(["team", "min"], ascending=[True, False]).iterrows()
        ],
    }


def _num(v) -> float | None:
    return None if v is None or pd.isna(v) else round(float(v), 3)


AHEAD_DAYS = 3   # the snapshot also covers the games of the next few days


def snapshot(conn: psycopg.Connection, day: dt.date | None = None, ahead: int = AHEAD_DAYS) -> int:
    """Store the prediction for every unfinished game from `day` (default: today, US Eastern) through `ahead` days later,
    each as the model sees it today, replacing an earlier snapshot of the same game taken the same day. Returns the
    number of games stored."""
    day = day or dt.datetime.now(live.EASTERN).date()
    games = conn.execute("SELECT game_id, team, opp, game_date FROM live.game WHERE home AND NOT completed"
                         " AND game_date BETWEEN %s AND %s ORDER BY game_date, tipoff, game_id",
                         (day, day + dt.timedelta(days=ahead))).fetchall()
    preds = predict_many(conn, [(away, home, gd) for _, home, away, gd in games]) if games else []
    for (gid, _, _, gd), p in zip(games, preds):
        components = {k: p[k] for k in ("home_edge", "roster", "form", "rest", "matchup", "fit", "injury_hit")}
        inputs = {**p["inputs"], "back_to_back": p["back_to_back"]}
        conn.execute(
            "INSERT INTO live.prediction_snapshot (game_id, snapshot_date, game_date, season, home, away, margin, home_win,"
            " components, inputs, injuries, prediction) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (game_id, snapshot_date) DO UPDATE SET taken_at = now(), margin = excluded.margin,"
            " home_win = excluded.home_win, components = excluded.components, inputs = excluded.inputs,"
            " injuries = excluded.injuries, prediction = excluded.prediction",
            (gid, day, gd, p["season"], p["home"], p["away"], p["margin"], p["home_win"],
             Jsonb(components), Jsonb(inputs), Jsonb(p["injuries"]), Jsonb(p)))
    return len(games)
