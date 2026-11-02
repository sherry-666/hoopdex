"""Does team height (starters / rotation average) add anything to game prediction? (leave-one-season-out, 2016-17..2025-26)

Same frame as scripts/backtest_team_rating.py: margin ~ 1 + minutes-weighted top-9 prior-rating average + back-to-back
+ shrunk form of the last 20 games, then add height terms. Height is the player's listed height (inches) that season;
starters = the team's top 5 by season minutes, rotation = top 9.

Result (11982 games, 300 team-seasons; logloss vs the rating-average base 0.6184, + = better): height adds nothing.
  starters' height -0.00005, rotation +0.00001, bench -0.00006, tallest starter -0.00012, count of 6'10"+ starters -0.00005
  (all within one se); coefficients -0.07 to -0.14 margin points per inch, t about -1. Across teams the starters' height
  has sd 1.07 in, corr with win% -0.06 (taller teams if anything slightly worse), top / bottom tercile win% 0.488 / 0.510.
  Height is already inside the ratings (rebounding, rim protection), so nothing is left over for it to explain.

Run: .venv/bin/python scripts/backtest_height.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parent))
import backtest_predictor as bp   # noqa: E402
import backtest_team_rating as tr   # noqa: E402
from ballstats import config   # noqa: E402


def make_extra():
    rating, stats, _ = tr.load()
    with psycopg.connect(config.DSN) as conn:
        rows = conn.execute("SELECT params->>'season', jsonb_array_elements(body->'resultSets'->0->'rowSet') "
                            "FROM raw.raw_response WHERE endpoint='LeagueDashPlayerBioStats' AND status='ok'").fetchall()
    h = {(s, int(r[0])): float(r[6]) for s, r in rows if r[6] is not None}
    anyh = {}
    for (s, p), v in h.items():
        anyh[p] = v

    def extra(y):
        s, prev = bp.season_str(y), bp.season_str(y - 1)
        pr = rating[rating.season == prev].set_index("pid")
        out, lg = {}, []
        teams = {}
        for team, g in stats[stats.season == s].groupby("team"):
            g = g.sort_values("min", ascending=False).head(9).copy()
            g["h"] = [h.get((s, p), anyh.get(p, np.nan)) for p in g.pid]
            g["o"] = g.pid.map(pr["ovr"]).fillna(pr["ovr"].quantile(bp.REPLACEMENT_Q))
            teams[team] = g.reset_index(drop=True)
            lg.extend(g.h.dropna())
        mu = float(np.mean(lg))
        for team, g in teams.items():
            g = g.assign(h=g.h.fillna(mu))
            top5 = g.head(5)
            out[team] = {"avg9": tr.wavg(g.o, g["min"]),
                         "h_start": float(top5.h.mean()) - mu,
                         "h_rot": tr.wavg(g.h, g["min"]) - mu,
                         "h_bench": float(g.h[5:].mean()) - mu,
                         "h_max": float(top5.h.max()) - mu,
                         "h_sd": float(top5.h.std()),
                         "bigs": float((top5.h >= 82).sum()),         # 6'10"+
                         "h_wt": float(np.average(g.h, weights=g.o.clip(lower=1) * g["min"])) - mu}
        return out
    return extra


if __name__ == "__main__":
    df = bp.build(extra=make_extra())
    print(f"{len(df)} games")
    # season-level: team average win% vs team height
    base_cols = ["b2b", "sform20"]
    models = [("BASE rating avg", ["d_avg9"]),
              ("+ starters height", ["d_avg9", "d_h_start"]),
              ("+ rotation height (min-wtd)", ["d_avg9", "d_h_rot"]),
              ("+ bench height", ["d_avg9", "d_h_bench"]),
              ("+ tallest starter", ["d_avg9", "d_h_max"]),
              ("+ starters height spread", ["d_avg9", "d_h_sd"]),
              ("+ count of 6'10\"+ starters", ["d_avg9", "d_bigs"]),
              ("+ starters & bench height", ["d_avg9", "d_h_start", "d_h_bench"]),
              ("height only (no rating)", ["d_h_start"])]
    base = tr.evaluate(df, models[0][1] + base_cols)
    print(f"\n{'model':32s} {'acc':>6s} {'logloss':>8s} {'vs BASE':>9s} {'se':>7s} {'seasons+':>9s}")
    for name, cols in models:
        r = tr.evaluate(df, cols + base_cols)
        d = base["ll"] - r["ll"]
        better = sum(d[(df.season == y).to_numpy()].mean() > 0 for y in df.season.unique())
        print(f"{name:32s} {r['hit'].mean():6.3f} {r['ll'].mean():8.4f} {d.mean():+9.5f} {d.std() / math.sqrt(len(d)):7.5f} {better:>6d}/10")
    print("\ncoefficients (margin points per inch; t):")
    for cols in (["d_avg9", "d_h_start"], ["d_avg9", "d_h_rot"], ["d_avg9", "d_h_start", "d_h_bench"], ["d_avg9", "d_bigs"],
                 ["d_h_start"]):
        print(" ", {k: v for k, v in tr.coefs(df, cols + base_cols).items() if k not in ("const", "b2b", "sform20")})
    # raw: correlation of team height with team win% by season
    g = pd.concat([df.assign(t=df.h_team if "h_team" in df else None)]) if False else None
    # raw: across team-seasons, do taller teams win more? (season win% vs height; then with the prior-rating average held)
    with psycopg.connect(config.DSN) as conn:
        g = pd.DataFrame(conn.execute("SELECT season, team, (team_score > opp_score)::int FROM live.game"
                                      " WHERE completed AND season_type = 2 AND team_score IS NOT NULL").fetchall(),
                         columns=["season", "team", "w"])
    wp = g.groupby(["season", "team"]).w.mean()
    ex = make_extra()
    tab = pd.DataFrame([{"season": y, "team": t, "wp": wp.get((bp.season_str(y), t), np.nan), **f}
                        for y in range(bp.FIRST, bp.LAST + 1) for t, f in ex(y).items()]).dropna()
    print(f"\n{len(tab)} team-seasons, starters' height spread across teams: sd {tab.h_start.std():.2f} in")
    for c in ("h_start", "h_rot", "h_bench"):
        r = np.corrcoef(tab[c], tab.wp)[0, 1]
        print(f"  corr({c}, win%) = {r:+.3f}   corr({c}, prior rating avg) = {np.corrcoef(tab[c], tab.avg9)[0, 1]:+.3f}")
    X = np.c_[np.ones(len(tab)), tab.avg9, tab.h_start]
    b = np.linalg.lstsq(X, tab.wp, rcond=None)[0]
    e = tab.wp - X @ b
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * e.var())
    print(f"  win% ~ rating avg + starters height: height coef {b[2]:+.4f}/in (t {b[2] / se[2]:+.1f}); "
          f"alone: {np.polyfit(tab.h_start, tab.wp, 1)[0]:+.4f}/in")
    print("  by starters' height tercile:", tab.groupby(pd.qcut(tab.h_start, 3, labels=["short", "mid", "tall"]), observed=True).wp.mean().round(3).to_dict())
