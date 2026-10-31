"""Does a different offense / defense / PIE split in the player OVR make the team score predict games better?

OVR is  z(0.5 x offense + 0.3 x defense + 0.2 x PIE)  pulled toward replacement by sample size (ratings.py). The
component z-scores are stored per player season (feat.player_rating.detail), so any other split can be rebuilt:
standardise the weighted sum over that season's 500+ minute players, apply the same pull, scale to 77 + 6.5 z.
Team score = minutes-weighted average of the top 9 (the season's own rotation) of LAST season's rebuilt OVR, in the
frame of scripts/backtest_team_rating.py (+ back-to-back + shrunk form of the last 20 games), leave-one-season-out.

Result (11982 games, base split 0.5 / 0.3 / 0.2 = logloss 0.6189; + = better, se about 0.0002):
  Raising offense does not help. Offense 0.6 / defense 0.2 / PIE 0.2: -0.00003; 0.7 / 0.2 / 0.1: -0.00007;
  0.8 / 0.1 / 0.1: -0.0007; 0.9 / 0.1 / 0: -0.0009. Lowering it is worse too (0.3 / 0.4 / 0.3: -0.0009).
  The best split on the 0.1 grid is 0.6 / 0.3 / 0.1 (and 0.7 / 0.3 / 0), only +0.0001 over the current one; choosing
  the split on the other seasons for each held-out season gains +0.00002 (se 0.0001). The current split stays.
  The defense weight 0.3 is the one every good split keeps; PIE can shrink to 0.1 without loss.

Run: .venv/bin/python scripts/backtest_ovr_weights.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parent))
import backtest_predictor as bp   # noqa: E402
from backtest_team_rating import evaluate, wavg   # noqa: E402
from ballstats import config, ratings   # noqa: E402

STEP = 0.1
GRID = [(round(o, 1), round(d, 1), round(1 - o - d, 1)) for o in np.arange(0.1, 1.0, STEP) for d in np.arange(0.0, 1.0, STEP)
        if o + d <= 1.0001]
BASE = (0.5, 0.3, 0.2)


def tag(w):
    return f"w{int(w[0] * 10)}{int(w[1] * 10)}{int(w[2] * 10)}"


def load():
    with psycopg.connect(config.DSN) as conn:
        r = pd.DataFrame(conn.execute(
            "SELECT season, player_id, minutes, ovr, (detail->>'offense')::float, (detail->>'defense')::float,"
            " (detail->>'contribution')::float, (detail->>'reliability')::float FROM feat.player_rating WHERE qualified OR minutes > 0").fetchall(),
            columns=["season", "pid", "minutes", "ovr_stored", "off", "def", "pie", "rel"]).astype({"ovr_stored": float})
        stats = pd.DataFrame(conn.execute("SELECT season, player_id, team, minutes FROM feat.player_stats"
                                          " WHERE season <> 'career' AND team IS NOT NULL").fetchall(),
                             columns=["season", "pid", "team", "min"]).astype({"min": float})
    return r.dropna(), stats


def rebuild(r: pd.DataFrame, w) -> pd.Series:
    """Rebuilt OVR (rating points, unrounded) for every player season under the split w = (offense, defense, PIE)."""
    combo = w[0] * r.off + w[1] * r["def"] + w[2] * r.pie
    ref = combo[r.minutes >= ratings.MIN_MINUTES].groupby(r.season)
    zc = (combo - ref.transform("mean").reindex(r.index)) / ref.transform("std").reindex(r.index)
    z = r.rel * zc + (1 - r.rel) * ratings.REPLACEMENT_Z
    return np.clip(ratings.SCALE_MID + ratings.SCALE_SD * z, 40, 99)


def make_extra():
    r, stats = load()
    r = r.reset_index(drop=True)
    for w in GRID:
        r[tag(w)] = rebuild(r, w)
    ok = r[tag(BASE)].notna()
    print(f"rebuild check, base split vs stored OVR: corr {np.corrcoef(r.loc[ok, tag(BASE)], r.ovr_stored[ok])[0, 1]:.4f}, "
          f"mean abs diff {np.abs(r[tag(BASE)] - r.ovr_stored)[ok].mean():.2f} points")

    def extra(y: int) -> dict:
        s, prev = bp.season_str(y), bp.season_str(y - 1)
        pr = r[r.season == prev].set_index("pid")
        repl = pr[[tag(w) for w in GRID]].quantile(bp.REPLACEMENT_Q)
        out = {}
        for team, g in stats[stats.season == s].groupby("team"):
            g = g.sort_values("min", ascending=False).head(bp.teams.NUM_ROTATION)
            out[team] = {tag(w): wavg(g.pid.map(pr[tag(w)]).fillna(repl[tag(w)]), g["min"]) for w in GRID}
        return out
    return extra


def fit_predict(df, cols, train, test):
    X = np.c_[np.ones(train.sum()), df.loc[train, cols].to_numpy()]
    b = np.linalg.lstsq(X, df.m[train], rcond=None)[0]
    sig = (df.m[train] - X @ b).std()
    return np.c_[np.ones(test.sum()), df.loc[test, cols].to_numpy()] @ b, sig, X @ b


def logloss(pred, sig, m):
    p = np.clip(0.5 * (1 + np.vectorize(math.erf)(pred / sig / math.sqrt(2))), 1e-4, 1 - 1e-4)
    return -np.where(m > 0, np.log(p), np.log(1 - p))


if __name__ == "__main__":
    df = bp.build(extra=make_extra())
    print(f"{len(df)} games, {df.season.min()}-{df.season.max()}")
    fixed = ["b2b", "sform20"]
    base = evaluate(df, [f"d_{tag(BASE)}"] + fixed)
    print(f"base split {BASE}: acc {base['hit'].mean():.3f} brier {base['brier'].mean():.4f} logloss {base['ll'].mean():.4f}\n")

    print("one line: offense weight x, defense : PIE kept at 3 : 2")
    print(f"{'offense':>8s} {'defense':>8s} {'PIE':>6s} {'acc':>6s} {'logloss':>8s} {'vs base':>9s} {'se':>7s} {'seasons+':>9s}")
    for o in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        d = round(0.6 * (1 - o), 1)
        w = (o, d, round(1 - o - d, 1))
        if tag(w) not in df.columns.str.replace("d_", ""):
            continue
        r = evaluate(df, [f"d_{tag(w)}"] + fixed)
        diff = base["ll"] - r["ll"]
        better = sum(diff[(df.season == y).to_numpy()].mean() > 0 for y in df.season.unique())
        print(f"{w[0]:8.1f} {w[1]:8.1f} {w[2]:6.1f} {r['hit'].mean():6.3f} {r['ll'].mean():8.4f} {diff.mean():+9.5f} "
              f"{diff.std() / math.sqrt(len(diff)):7.5f} {better:>6d}/10")

    print("\nevery split on the 0.1 grid, best 8 by log loss (the best of many is flattered, see the nested line)")
    res = []
    for w in GRID:
        r = evaluate(df, [f"d_{tag(w)}"] + fixed)
        res.append((r["ll"].mean(), w, r["hit"].mean()))
    for ll, w, acc in sorted(res)[:8]:
        print(f"  off {w[0]:.1f} def {w[1]:.1f} PIE {w[2]:.1f}  acc {acc:.3f}  logloss {ll:.4f}  ({base['ll'].mean() - ll:+.5f} vs base)")

    # Nested: for each held-out season pick the split that fits the other seasons best, then score the held-out one.
    nested, picks = np.zeros(len(df)), {}
    for y in df.season.unique():
        tr, te = (df.season != y).to_numpy(), (df.season == y).to_numpy()
        def in_sample(w):
            pred, sig, _ = fit_predict(df, [f"d_{tag(w)}"] + fixed, tr, tr)
            return logloss(pred, sig, df.m[tr]).mean()
        best = min(GRID, key=in_sample)
        picks[y] = best
        pred, sig, _ = fit_predict(df, [f"d_{tag(best)}"] + fixed, tr, te)
        nested[te] = logloss(pred, sig, df.m[te])
    diff = base["ll"] - nested
    print(f"\nnested (split chosen on the other seasons): logloss {nested.mean():.4f}, {diff.mean():+.5f} vs base (se {diff.std() / math.sqrt(len(diff)):.5f})")
    print("picked per held-out season:", {int(y): f"{w[0]:.1f}/{w[1]:.1f}/{w[2]:.1f}" for y, w in picks.items()})
