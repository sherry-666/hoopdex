"""Player-type matchups: does an offensive archetype score more or less against a defensive archetype?

Unit: one (offensive player, defender) pair in a season, from the tracked matchup data (partial
possessions and points). Each player gets his own level (fixed effect), so talent drops out; what is left
is the interaction between the two players' archetype mixes (feat.player_role weights), a bilinear
offence-archetype x defence-archetype table, doubly centred. Ridge only makes the redundant terms unique.
The permutation test shuffles defenders' archetype mixes among defenders.

Findings so far: the tables replicate across seasons (mean r ~0.93) but add nothing to predicting team
results (leave-season-out backtest), and matchups are not random (coaches send rim protectors to bigs),
so read them as descriptions of who guards whom, not as causal counters.
"""

import numpy as np
import pandas as pd
import psycopg
from scipy import sparse
from scipy.sparse.linalg import lsqr

MIN_POSS = 5          # pairs with fewer partial possessions are noise
RIDGE = 1.0
PERMUTATIONS = 100
SEED = 0
SCALE = 100           # effects are reported per 100 partial possessions


def load_pairs(conn: psycopg.Connection, season: str) -> pd.DataFrame:
    rows = []
    for (body,) in conn.execute("SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueSeasonMatchups'"
                                " AND status = 'ok' AND params->>'season' = %s", (season,)):
        rs = body["resultSets"][0]
        rows += [dict(zip(rs["headers"], r)) for r in rs["rowSet"]]
    if not rows:
        return pd.DataFrame(columns=["o", "d", "poss", "pts"])
    d = pd.DataFrame(rows).rename(columns={"OFF_PLAYER_ID": "o", "DEF_PLAYER_ID": "d",
                                           "PARTIAL_POSS": "poss", "PLAYER_PTS": "pts"})
    return d.groupby(["o", "d"], as_index=False)[["poss", "pts"]].sum().query("poss >= @MIN_POSS")


def _weights(conn: psycopg.Connection, season: str, side: str) -> dict[int, dict[str, float]]:
    return dict(conn.execute("SELECT player_id, weights FROM feat.player_role WHERE season = %s AND side = %s",
                             (season, side)).fetchall())


def build(conn: psycopg.Connection, season: str):
    d = load_pairs(conn, season)
    wo, wd = _weights(conn, season, "offense"), _weights(conn, season, "defense")
    d = d[d.o.isin(wo) & d.d.isin(wd)].reset_index(drop=True)
    d["y"] = d.pts / d.poss
    ko = sorted({k for w in wo.values() for k in w}, key=int)
    kd = sorted({k for w in wd.values() for k in w}, key=int)
    O = np.array([[wo[o].get(k, 0.0) for k in ko] for o in d.o])
    D = np.array([[wd[x].get(k, 0.0) for k in kd] for x in d.d])
    return d, O, D, [int(k) for k in ko], [int(k) for k in kd]


def fit_table(d: pd.DataFrame, O: np.ndarray, D: np.ndarray) -> np.ndarray:
    """Doubly centred offence-archetype x defence-archetype table, points per partial possession."""
    n = len(d)
    oi, di = pd.factorize(d.o)[0], pd.factorize(d.d)[0]
    Xo = sparse.csr_matrix((np.ones(n), (np.arange(n), oi)))
    Xd = sparse.csr_matrix((np.ones(n), (np.arange(n), di)))
    inter = np.einsum("ni,nj->nij", O, D).reshape(n, -1)
    k = Xo.shape[1] + Xd.shape[1]
    X = sparse.hstack([Xo, Xd, sparse.csr_matrix(inter)]).tocsr()
    w = np.sqrt(d.poss.to_numpy())
    pen = sparse.hstack([sparse.csr_matrix((inter.shape[1], k)), sparse.identity(inter.shape[1]) * np.sqrt(RIDGE)])
    coef = lsqr(sparse.vstack([sparse.diags(w) @ X, pen]),
                np.concatenate([w * d.y.to_numpy(), np.zeros(inter.shape[1])]),
                atol=1e-10, btol=1e-10, iter_lim=30000)[0][k:]
    g = coef.reshape(O.shape[1], D.shape[1])
    return g - g.mean(1, keepdims=True) - g.mean(0, keepdims=True) + g.mean()


def permutation_p(d, O, D, observed: np.ndarray, rng) -> float:
    ids = d.d.unique()
    first = {x: D[(d.d == x).to_numpy()][0] for x in ids}
    spread = lambda g: float((g ** 2).sum())
    hits = 0
    for _ in range(PERMUTATIONS):
        shuffled = dict(zip(ids, rng.permutation(len(ids))))
        Dp = np.array([first[ids[shuffled[x]]] for x in d.d])
        hits += spread(fit_table(d, O, Dp)) >= spread(observed)
    return (1 + hits) / (1 + PERMUTATIONS)


def compute(conn: psycopg.Connection) -> dict:
    seasons = [r[0] for r in conn.execute(
        "SELECT DISTINCT params->>'season' FROM raw.raw_response WHERE endpoint = 'LeagueSeasonMatchups'"
        " AND status = 'ok' ORDER BY 1")]
    rng = np.random.default_rng(SEED)
    tables, meta = {}, {}
    for season in seasons:
        d, O, D, ko, kd = build(conn, season)
        if len(d) < 1000:
            continue
        g = fit_table(d, O, D)
        tables[season] = (g * SCALE, ko, kd)
        meta[season] = (len(d), int(d.poss.sum()), float(d.pts.sum() / d.poss.sum() * SCALE),
                        permutation_p(d, O, D, g, rng))
    if not tables:
        return {"seasons": 0}
    ko, kd = next(iter(tables.values()))[1:]
    stack = np.array([t[0] for t in tables.values()])
    mean, sd = stack.mean(0), stack.std(0)
    corr = [np.corrcoef(stack[i].ravel(), stack[j].ravel())[0, 1]
            for i in range(len(stack)) for j in range(i + 1, len(stack))]
    with conn.transaction():
        conn.execute("DELETE FROM feat.role_matchup")
        conn.execute("DELETE FROM feat.role_matchup_meta")
        for season, (g, _, _) in tables.items():
            for i, o in enumerate(ko):
                for j, x in enumerate(kd):
                    conn.execute("INSERT INTO feat.role_matchup (season, off_type, def_type, effect) VALUES (%s,%s,%s,%s)",
                                 (season, o, x, float(g[i, j])))
            conn.execute("INSERT INTO feat.role_matchup_meta (season, n_pairs, n_poss, mean_ppp, p_value)"
                         " VALUES (%s,%s,%s,%s,%s)", (season, *meta[season]))
        for i, o in enumerate(ko):
            for j, x in enumerate(kd):
                conn.execute("INSERT INTO feat.role_matchup (season, off_type, def_type, effect, spread)"
                             " VALUES ('all',%s,%s,%s,%s)", (o, x, float(mean[i, j]), float(sd[i, j])))
        conn.execute("INSERT INTO feat.role_matchup_meta (season, n_pairs, n_poss, mean_ppp, season_corr)"
                     " VALUES ('all',%s,%s,%s,%s)",
                     (sum(m[0] for m in meta.values()), sum(m[1] for m in meta.values()),
                      float(np.mean([m[2] for m in meta.values()])), float(np.mean(corr)) if corr else None))
    return {"seasons": len(tables), "season_corr": round(float(np.mean(corr)), 2) if corr else None}
