"""Which way of turning player ratings into a team score predicts games best? (leave-one-season-out, 2016-17..2025-26)

Every model is  margin ~ 1 + <roster feature(s)> + back-to-back + shrunk form of the last 20 games, the same
frame as scripts/backtest_predictor.py; only the roster score changes. Player ratings are last season's, the
rotation is the season's top 9 (or 10) by minutes. Ideas tested:
  star    more weight for the best one or two players (90+ players)
  fit     complementarity: offense / defense split, weak links, specialists
  lineups a starting five (1 inside + 2 outside + 2 seam by offensive family) and a second five, scored separately
Position comes from the offensive role family of that season (inside = 内线, outside = 持球创造者, seam = 无球侧翼 / 射手).

Result (11982 games; logloss vs the minutes-weighted top-9 average 0.6184, + = better, se ~0.0001-0.0008):
  star     nothing helps. Weights that grow with the rating are clearly worse (k=0.10: -0.0023, k=0.20: -0.0038);
           90+ players add nothing (coefficient -0.02, t -0.5): minutes weighting already counts the stars.
  fit      weak links hurt MORE than the average says (coefficients -0.64 off, -0.41 def, t about -4 in sample), the
           opposite of "the rest make up for it", but held out it is no better (-0.0003). Giving offense and defense
           their own weights is the one small gain (+0.0004, 7 of 10 seasons, t 2.6): 0.72 per offense point,
           0.35 per defense point.
  lineups  slot lineups (1 inside + 2 outside + 2 seam) are no better than top 5 / next 5 by rating without positions
           (-0.0007 vs -0.0008); the second five matters almost as much as the starters (0.41 vs 0.53 per point),
           so 0.8 / 0.2 is the worst split (-0.0010). The current roster score stays.
Caveats: the rotation is who finished the season with the team (no injuries or trades), ratings are today's model
applied to past seasons, positions are approximated by offensive role families.

Run: .venv/bin/python scripts/backtest_team_rating.py
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).parent))
import backtest_predictor as bp   # noqa: E402
from ballstats import config   # noqa: E402

SLOT = {"内线": "inside", "持球创造者": "outside", "无球侧翼 / 射手": "seam"}
SLOTS = ["inside", "outside", "outside", "seam", "seam"]
ROT, ROT2 = 9, 10


def load():
    with psycopg.connect(config.DSN) as conn:
        rating = pd.DataFrame(conn.execute("SELECT season, player_id, ovr, off, def FROM feat.player_rating").fetchall(),
                              columns=["season", "pid", "ovr", "off", "def"]).astype({"ovr": float, "off": float, "def": float})
        stats = pd.DataFrame(conn.execute("SELECT season, player_id, team, minutes FROM feat.player_stats"
                                          " WHERE season <> 'career' AND team IS NOT NULL").fetchall(),
                             columns=["season", "pid", "team", "min"]).astype({"min": float})
        fam = {(s, p): SLOT.get(f) for s, p, f in conn.execute(
            "SELECT season, player_id, family_name FROM feat.player_role WHERE side = 'offense'")}
    return rating, stats, fam


def wavg(v, w):
    return float(np.average(v, weights=w)) if len(v) and np.sum(w) > 0 else 0.0


def pick_lineups(g: pd.DataFrame) -> tuple[list[int], list[int]]:
    """Starting five and second five from the rotation's players (ordered by prior rating): the best per slot
    (inside, 2 outside, 2 seam); a slot nobody fills takes the best player left."""
    left = list(g.sort_values("o", ascending=False).index)
    out = []
    for _ in range(2):
        chosen = []
        for slot in SLOTS:
            c = next((i for i in left if g.slot[i] == slot), None)
            if c is None and left:
                c = left[0]
            if c is not None:
                chosen.append(c)
                left.remove(c)
        out.append(chosen)
    return out[0], out[1]


def make_extra():
    rating, stats, fam = load()

    def extra(y: int) -> dict:
        s, prev = bp.season_str(y), bp.season_str(y - 1)
        pr = rating[rating.season == prev].set_index("pid")
        repl = pr[["ovr", "off", "def"]].quantile(bp.REPLACEMENT_Q)
        teams = {}
        for team, g in stats[stats.season == s].groupby("team"):
            g = g.sort_values("min", ascending=False).head(ROT2).copy()
            for k, c in (("o", "ovr"), ("f", "off"), ("d", "def")):
                g[k] = g.pid.map(pr[c]).fillna(repl[c])
            g["slot"] = g.pid.map(lambda p: fam.get((s, p)))
            teams[team] = g.reset_index(drop=True)
        lg = pd.concat(t.head(ROT) for t in teams.values())
        lg_f, lg_d = wavg(lg.f, lg["min"]), wavg(lg.d, lg["min"])
        out = {}
        for team, g in teams.items():
            r, w = g.head(ROT), g.head(ROT)["min"]
            avg = wavg(r.o, w)
            o_sorted = sorted(r.o, reverse=True)
            F, D = wavg(r.f, w), wavg(r.d, w)
            f = {"avg9": avg, "avg10": wavg(g.o, g["min"])}
            # --- stars
            f["star1"] = o_sorted[0] - avg
            f["star2"] = (o_sorted[0] + o_sorted[1]) / 2 - avg
            f["top1"], f["top2"] = o_sorted[0], (o_sorted[0] + o_sorted[1]) / 2
            f["star85"] = float(sum(max(0.0, x - 85) for x in r.o))
            f["star90"] = float(sum(max(0.0, x - 90) for x in r.o))
            for k in (0.05, 0.1, 0.2):   # weights that grow with the rating: minutes x exp(k x (rating - average))
                sw = w * np.exp(k * (r.o - avg))
                f[f"sm{int(k * 100):02d}"] = wavg(r.o, sw)
            # --- fit / complementarity
            f["F"], f["D"] = F, D
            f["imb"], f["mn"] = abs(F - D), min(F, D)
            f["wk_off"] = wavg(np.maximum(0, lg_f - r.f), w)    # minutes-weighted shortfall of below-average offensive players
            f["wk_def"] = wavg(np.maximum(0, lg_d - r.d), w)
            f["spec"] = wavg((r.f - r.d).abs(), w)              # how lopsided the players are
            # --- lineups
            start, second = pick_lineups(g)
            f["sl_start"], f["sl_second"] = float(g.o[start].mean()), float(g.o[second].mean()) if second else float(g.o[start].mean())
            by_o = list(g.sort_values("o", ascending=False).index)
            f["rt_start"] = float(g.o[by_o[:5]].mean())
            f["rt_second"] = float(g.o[by_o[5:10]].mean()) if len(by_o) > 5 else f["rt_start"]
            f["mn_start"], f["mn_second"] = float(g.o[:5].mean()), float(g.o[5:10].mean()) if len(g) > 5 else float(g.o[:5].mean())
            for c in (0.5, 0.6, 0.7, 0.8):
                for tag in ("sl", "rt", "mn"):
                    f[f"{tag}_c{int(c * 10)}"] = c * f[f"{tag}_start"] + (1 - c) * f[f"{tag}_second"]
            out[team] = f
        return out
    return extra


def evaluate(df: pd.DataFrame, cols: list[str]):
    """Leave-one-season-out; per-game log loss and hits so models can be compared game by game."""
    pred, sig = np.zeros(len(df)), np.zeros(len(df))
    for y in df.season.unique():
        tr, te = (df.season != y).to_numpy(), (df.season == y).to_numpy()
        X = np.c_[np.ones(tr.sum()), df.loc[tr, cols].to_numpy()]
        b = np.linalg.lstsq(X, df.m[tr], rcond=None)[0]
        sig[te] = (df.m[tr] - X @ b).std()
        pred[te] = np.c_[np.ones(te.sum()), df.loc[te, cols].to_numpy()] @ b
    p = np.clip(0.5 * (1 + np.vectorize(math.erf)(pred / sig / math.sqrt(2))), 1e-4, 1 - 1e-4)
    win = (df.m > 0).to_numpy()
    return {"ll": -np.where(win, np.log(p), np.log(1 - p)), "hit": (pred > 0) == win, "brier": (p - win) ** 2, "pred": pred}


def coefs(df, cols):
    X = np.c_[np.ones(len(df)), df[cols].to_numpy()]
    b = np.linalg.lstsq(X, df.m, rcond=None)[0]
    e = df.m - X @ b
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * e.var())
    return {c: (round(float(bb), 3), round(float(bb / s), 1)) for c, bb, s in zip(["const"] + cols, b, se)}


if __name__ == "__main__":
    df = bp.build(extra=make_extra())
    print(f"{len(df)} games, {df.season.min()}-{df.season.max()}")
    base_cols = ["b2b", "sform20"]
    models = [
        ("BASE  minutes-weighted avg, top 9", ["d_avg9"]),
        ("minutes-weighted avg, top 10", ["d_avg10"]),
        ("-- stars --", None),
        ("avg + best player", ["d_avg9", "d_star1"]),
        ("avg + best two", ["d_avg9", "d_star2"]),
        ("avg + best + second", ["d_avg9", "d_star1", "d_star2"]),
        ("avg + stars above 85 (sum of points)", ["d_avg9", "d_star85"]),
        ("avg + stars above 90 (sum of points)", ["d_avg9", "d_star90"]),
        ("rating-weighted avg, k=0.05", ["d_sm05"]),
        ("rating-weighted avg, k=0.10", ["d_sm10"]),
        ("rating-weighted avg, k=0.20", ["d_sm20"]),
        ("-- fit / complementarity --", None),
        ("offense avg + defense avg (own weights)", ["d_F", "d_D"]),
        ("avg + |offense - defense| imbalance", ["d_avg9", "d_imb"]),
        ("avg + weaker of offense / defense", ["d_avg9", "d_mn"]),
        ("avg + weak links (off, def)", ["d_avg9", "d_wk_off", "d_wk_def"]),
        ("avg + specialists (|off - def|)", ["d_avg9", "d_spec"]),
        ("-- lineups --", None),
        ("slot lineups, free weights", ["d_sl_start", "d_sl_second"]),
        ("slot lineups 0.5/0.5", ["d_sl_c5"]), ("slot lineups 0.6/0.4", ["d_sl_c6"]),
        ("slot lineups 0.7/0.3", ["d_sl_c7"]), ("slot lineups 0.8/0.2", ["d_sl_c8"]),
        ("control: top 5 / next 5 by rating, free", ["d_rt_start", "d_rt_second"]),
        ("control: top 5 / next 5 by minutes, free", ["d_mn_start", "d_mn_second"]),
        ("control: top 5 / next 5 by minutes 0.7/0.3", ["d_mn_c7"]),
    ]
    base = evaluate(df, models[0][1] + base_cols)
    print(f"\n{'model':44s} {'acc':>6s} {'brier':>7s} {'logloss':>8s} {'vs BASE':>9s} {'se':>6s} {'seasons+':>9s}")
    for name, cols in models:
        if cols is None:
            print(name)
            continue
        r = evaluate(df, cols + base_cols)
        d = base["ll"] - r["ll"]     # > 0: better than BASE
        better = sum(d[(df.season == y).to_numpy()].mean() > 0 for y in df.season.unique())
        print(f"{name:44s} {r['hit'].mean():6.3f} {r['brier'].mean():7.4f} {r['ll'].mean():8.4f} {d.mean():+9.5f} {d.std() / math.sqrt(len(d)):6.5f} {better:>6d}/10")
    print("\ncoefficients (margin points per unit; t):")
    for cols in (["d_avg9", "d_star1", "d_star2"], ["d_avg9", "d_star90"], ["d_F", "d_D"], ["d_avg9", "d_wk_off", "d_wk_def", "d_spec"],
                 ["d_sl_start", "d_sl_second"], ["d_mn_start", "d_mn_second"]):
        print(" ", {k: v for k, v in coefs(df, cols + base_cols).items() if k not in ("const", "b2b", "sform20")})
