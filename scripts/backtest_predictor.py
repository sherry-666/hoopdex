"""Backtest the game predictor on 2016-17..2025-26 regular seasons (leave-one-season-out).

Only what could be known before the game feeds each model, as far as the stored data allows:
  - player strength = the player's rating the PREVIOUS season (rookies and new arrivals get a replacement level)
  - the roster = who finished season S with the team, ordered by season-S minutes (so injuries and trades during the
    season are NOT modelled: that needs per-game lineups, stored only for 2026-27)
  - the team's own previous-season rating, home court, back-to-back (from the schedule), experience (years since a
    player's first season), and the lineup-fit / matchup tables (fitted on these same seasons: in-sample, so they
    flatter those two terms)

Run: .venv/bin/python scripts/backtest_predictor.py
"""

import math

import numpy as np
import pandas as pd
import psycopg

from ballstats import config, predict, teams

FIRST, LAST = 2016, 2025       # season start years tested
REPLACEMENT_Q = 0.25
FORM_N = (5, 10, 20, 30, 40, 82)
MIN_FORM = 3
SHRINK = 10


def season_str(y: int) -> str:
    return f"{y}-{str(y + 1)[2:]}"


def load(conn):
    games = pd.DataFrame(conn.execute(
        "SELECT season, game_id, game_date, team AS h, opp AS a, team_score - opp_score AS m FROM live.game"
        " WHERE home AND completed AND season_type = 2 AND team_score IS NOT NULL").fetchall(),
        columns=["season", "gid", "date", "h", "a", "m"])
    sched = pd.DataFrame(conn.execute("SELECT season, team, game_date, team_score - opp_score FROM live.game WHERE season_type = 2").fetchall(),
                         columns=["season", "team", "date", "tm"])
    rating = pd.DataFrame(conn.execute("SELECT season, player_id, ovr FROM feat.player_rating").fetchall(),
                          columns=["season", "pid", "ovr"]).astype({"ovr": float})
    stats = pd.DataFrame(conn.execute("SELECT season, player_id, team, minutes FROM feat.player_stats WHERE season <> 'career'").fetchall(),
                         columns=["season", "pid", "team", "min"]).astype({"min": float})
    first = dict(conn.execute("SELECT player_id, left(first_season, 4)::int FROM core.player WHERE first_season IS NOT NULL").fetchall())
    team_ovr = pd.DataFrame(conn.execute("SELECT season, team, ovr FROM feat.team_profile").fetchall(),
                            columns=["season", "team", "ovr"]).astype({"ovr": float})
    roles = {(s, p, side): t for s, p, side, t in conn.execute(
        "SELECT season, player_id, side, top_archetype_id FROM feat.player_role")}
    syn = {(s, a, b): e for s, a, b, e in conn.execute("SELECT side, type_a, type_b, effect FROM feat.role_synergy")}
    mat = {(o, d): e for o, d, e in conn.execute("SELECT off_type, def_type, effect FROM feat.role_matchup WHERE season = 'all'")}
    names = {}
    return games, sched, rating, stats, first, team_ovr, roles, syn, mat, names


def team_features(y, rating, stats, first, roles, syn, mat):
    """Per team of season y: prior-rating roster strength, experience, and the key-player tables' pair sums."""
    s, prev = season_str(y), season_str(y - 1)
    prior = rating[rating.season == prev].set_index("pid").ovr
    repl = prior.quantile(REPLACEMENT_Q)
    st = stats[stats.season == s]
    out, key = {}, {}
    for team, g in st.groupby("team"):
        g = g.sort_values("min", ascending=False).head(teams.NUM_ROTATION)
        ovr = g.pid.map(prior).fillna(repl)
        w = g["min"]
        exp = g.pid.map(lambda p: y - first[p] if p in first else np.nan)
        out[team] = {"roster": float(np.average(ovr, weights=w)),
                     "exp": float(np.average(exp.fillna(exp.mean()), weights=w)) if exp.notna().any() else np.nan}
        top = g.assign(ovr=ovr).sort_values("ovr", ascending=False).head(predict.NUM_KEY)
        key[team] = [(int(p), roles.get((s, p, "offense")), roles.get((s, p, "defense"))) for p in top.pid]
    fit = {}
    for team, ps in key.items():
        tot = 0.0
        for side, i in (("offense", 1), ("defense", 2)):
            ts = [p[i] for p in ps if p[i] is not None]
            for a in range(len(ts)):
                for b in range(a + 1, len(ts)):
                    tot += syn.get((side, min(ts[a], ts[b]), max(ts[a], ts[b])), 0.0)
        fit[team] = predict._cap(tot * predict.FIT_OVERLAP * predict.STAR_SHARE)
    return out, key, fit


def matchup(mine, theirs, mat):
    a, d = [p[1] for p in mine if p[1] is not None], [p[2] for p in theirs if p[2] is not None]
    if not a or not d:
        return 0.0
    return predict._cap(sum(np.mean([mat.get((o, x), 0.0) for x in d]) for o in a) / 100 * predict.MATCHUP_POSS * predict.STAR_SHARE)


def build():
    with psycopg.connect(config.DSN) as conn:
        games, sched, rating, stats, first, team_ovr, roles, syn, mat, _ = load(conn)
    days = {(r.season, r.team): set() for r in sched.drop_duplicates(["season", "team"]).itertuples()}
    for r in sched.itertuples():
        days[(r.season, r.team)].add(r.date)
    # Recent form: mean margin of a team's last N games earlier in the same season (needs MIN_FORM games, else 0).
    played = sched.dropna(subset=["tm"]).astype({"tm": float}).sort_values(["season", "team", "date"])
    form = {}
    for (s_, t_), g_ in played.groupby(["season", "team"]):
        ds, ms = list(g_.date), g_.tm.to_numpy()
        for i, d_ in enumerate(ds):
            form[(s_, t_, d_)] = {n: (float(ms[max(0, i - n):i].mean()) if i >= MIN_FORM else 0.0) for n in FORM_N}
            # shrunk toward 0 by SHRINK pseudo-games: little weight on a few games early in the season
            form[(s_, t_, d_)].update({-n: float(ms[max(0, i - n):i].sum() / (min(i, n) + SHRINK)) for n in FORM_N})
    prev_ovr = team_ovr.set_index(["season", "team"]).ovr
    rows = []
    for y in range(FIRST, LAST + 1):
        s = season_str(y)
        feat, key, fit = team_features(y, rating, stats, first, roles, syn, mat)
        for g in games[games.season == s].itertuples():
            if g.h not in feat or g.a not in feat:
                continue
            one = pd.Timedelta(days=1)
            tired = lambda t: (pd.Timestamp(g.date) - one).date() in days[(s, t)]
            rows.append({
                "season": y, "m": float(g.m),
                "d_roster": feat[g.h]["roster"] - feat[g.a]["roster"],
                "d_last": prev_ovr.get((season_str(y - 1), g.h), np.nan) - prev_ovr.get((season_str(y - 1), g.a), np.nan),
                "d_end": prev_ovr.get((s, g.h), np.nan) - prev_ovr.get((s, g.a), np.nan),   # oracle: this season's final rating
                "b2b": float(tired(g.a)) - float(tired(g.h)),
                "d_exp": feat[g.h]["exp"] - feat[g.a]["exp"],
                **{f"form{n}": form[(s, g.h, g.date)][n] - form[(s, g.a, g.date)][n] for n in FORM_N},
                **{f"sform{n}": form[(s, g.h, g.date)][-n] - form[(s, g.a, g.date)][-n] for n in FORM_N},
                "fit": fit[g.h] - fit[g.a],
                "match": matchup(key[g.h], key[g.a], mat) - matchup(key[g.a], key[g.h], mat),
            })
    return pd.DataFrame(rows).dropna()


def evaluate(df: pd.DataFrame, cols: list[str]):
    """Leave-one-season-out: fit margin ~ 1 + cols on the other seasons, predict the held-out one."""
    pred = np.zeros(len(df))
    sig = np.zeros(len(df))
    for y in df.season.unique():
        tr, te = df.season != y, df.season == y
        X = np.c_[np.ones(tr.sum()), df.loc[tr, cols].to_numpy()]
        b = np.linalg.lstsq(X, df.loc[tr, "m"], rcond=None)[0]
        sig[te.to_numpy()] = (df.loc[tr, "m"] - X @ b).std()
        pred[te.to_numpy()] = np.c_[np.ones(te.sum()), df.loc[te, cols].to_numpy()] @ b
    p = 0.5 * (1 + np.vectorize(math.erf)(pred / sig / math.sqrt(2)))
    p = np.clip(p, 1e-4, 1 - 1e-4)
    win = (df.m > 0).to_numpy()
    return {"acc": float(np.mean((pred > 0) == win)), "brier": float(np.mean((p - win) ** 2)),
            "logloss": float(-np.mean(np.where(win, np.log(p), np.log(1 - p)))), "rmse": float(np.sqrt(np.mean((df.m - pred) ** 2)))}


def coefs(df, cols):
    X = np.c_[np.ones(len(df)), df[cols].to_numpy()]
    b = np.linalg.lstsq(X, df.m, rcond=None)[0]
    e = df.m - X @ b
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * e.var())
    return {c: (round(float(bb), 3), round(float(bb / s), 1)) for c, bb, s in zip(["const"] + cols, b, se)}


if __name__ == "__main__":
    df = build()
    print(f"{len(df)} games, seasons {df.season.min()}-{df.season.max()}; home win rate {np.mean(df.m > 0):.3f}")
    models = [
        ("always home", []),
        ("last season's team rating", ["d_last"]),
        ("prior-rating roster", ["d_roster"]),
        ("roster + last season", ["d_roster", "d_last"]),
        ("  + back-to-back", ["d_roster", "d_last", "b2b"]),
        ("  + experience", ["d_roster", "d_last", "b2b", "d_exp"]),
        ("  + fit + matchup", ["d_roster", "d_last", "b2b", "fit", "match"]),
        ("  + all", ["d_roster", "d_last", "b2b", "d_exp", "fit", "match"]),
        ("roster + b2b", ["d_roster", "b2b"]),
        ("  + form last 5", ["d_roster", "b2b", "form5"]),
        ("  + form last 10", ["d_roster", "b2b", "form10"]),
        ("  + form last 20", ["d_roster", "b2b", "form20"]),
        ("  + form last 30", ["d_roster", "b2b", "form30"]),
        ("  + form last 40", ["d_roster", "b2b", "form40"]),
        ("  + form whole season so far", ["d_roster", "b2b", "form82"]),
        ("  + shrunk form 20", ["d_roster", "b2b", "sform20"]),
        ("  + shrunk form 40", ["d_roster", "b2b", "sform40"]),
        ("  + shrunk form 82", ["d_roster", "b2b", "sform82"]),
        ("  + shrunk 20 + 82", ["d_roster", "b2b", "sform20", "sform82"]),
        ("  + form 10 + match", ["d_roster", "b2b", "form10", "match"]),
        ("[oracle] this season's final rating", ["d_end"]),
    ]
    print(f"{'model':38s} {'acc':>6s} {'brier':>7s} {'logloss':>8s} {'rmse':>6s}")
    for name, cols in models:
        r = evaluate(df, cols)
        print(f"{name:38s} {r['acc']:6.3f} {r['brier']:7.4f} {r['logloss']:8.4f} {r['rmse']:6.2f}")
    print("\ncoefficients (all terms, margin points; t-stat):")
    for k, v in coefs(df, ["d_roster", "b2b", "form5", "form10", "form20", "match", "fit"]).items():
        print(f"  {k:9s} {v[0]:7.3f}  t={v[1]}")
