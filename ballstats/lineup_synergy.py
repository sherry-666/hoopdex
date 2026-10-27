"""Role synergy: do two kinds of offensive player play better together than their own levels predict?

Unit: a pair of teammates in a season (LeagueDashLineups, 2-man units, at least MIN_POSS possessions
together) and the team's net rating while both are on court. Each player-season has its own level (ridge
fixed effect), which also soaks up team quality; on top sits one term per unordered pair of offensive
archetypes, from the two players' archetype mixes (feat.player_role weights).

The terms are small and do not improve held-out predictions (cv_gain ~ 0), so the table describes
tendencies (two spot-up shooters overlap, a ball handler pairs well with a big) and is not a predictor.
Standard errors resample team-seasons, because pairs of one team share players.
"""

import itertools

import numpy as np
import psycopg
from scipy import sparse

MIN_POSS = 200
PLAYER_RIDGE = 1000.0
PAIR_RIDGE = 1000.0
BOOTSTRAPS = 40
FOLDS = 5
SEED = 0


def load(conn: psycopg.Connection):
    """Pair rows (season, team, a, b, poss, net rating) and each player's offensive archetype weights."""
    seasons = [r[0] for r in conn.execute(
        "SELECT DISTINCT params->>'season' FROM raw.raw_response WHERE endpoint = 'LeagueDashLineups' AND status = 'ok'"
        " AND params->>'group_quantity' = '2' ORDER BY 1")]
    keys = sorted({int(k) for (w,) in conn.execute("SELECT weights FROM feat.player_role WHERE side = 'offense'") for k in w})
    weights, rows = {}, []
    for season in seasons:
        weights[season] = {p: np.array([w.get(str(k), 0.0) for k in keys]) for p, w in conn.execute(
            "SELECT player_id, weights FROM feat.player_role WHERE season = %s AND side = 'offense'", (season,))}
        seen = set()
        for (body,) in conn.execute(
                "SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueDashLineups' AND status = 'ok' AND params->>'season' = %s"
                " AND params->>'group_quantity' = '2' AND params->>'measure_type_detailed_defense' = 'Advanced'", (season,)):
            rs = body["resultSets"][0]
            for r in rs["rowSet"]:
                d = dict(zip(rs["headers"], r))
                a, b = (int(x) for x in d["GROUP_ID"].strip("-").split("-"))
                if (d["TEAM_ID"], a, b) in seen or d["POSS"] < MIN_POSS or a not in weights[season] or b not in weights[season]:
                    continue                  # the league-wide and per-team requests overlap
                seen.add((d["TEAM_ID"], a, b))
                rows.append((season, d["TEAM_ID"], a, b, d["POSS"], d["NET_RATING"]))
    return seasons, keys, weights, rows


def design(rows, weights, n_types: int):
    n = len(rows)
    ids = {}
    for season, _, a, b, _, _ in rows:
        for p in (a, b):
            ids.setdefault((season, p), len(ids))
    cols = np.array([ids[(s, p)] for s, _, a, b, _, _ in rows for p in (a, b)])
    F = sparse.csr_matrix((np.ones(2 * n), (np.repeat(np.arange(n), 2), cols)), shape=(n, len(ids)))
    pairs = list(itertools.combinations_with_replacement(range(n_types), 2))
    C = np.zeros((n, len(pairs)))
    for i, (season, _, a, b, _, _) in enumerate(rows):
        u, v = weights[season][a], weights[season][b]
        for j, (x, y) in enumerate(pairs):
            C[i, j] = u[x] * v[y] + (u[y] * v[x] if x != y else 0.0)
    w = np.array([r[4] for r in rows], float)
    C -= np.average(C, axis=0, weights=w)
    y = np.array([r[5] for r in rows], float)
    return F, C, y - np.average(y, weights=w), w, pairs


def fit(F, C, y, w, idx):
    """Pair-type coefficients from the rows in idx, and the player levels (for held-out prediction)."""
    Ft, Ct, wt = F[idx], C[idx], w[idx]
    D = sparse.diags(wt)
    cross = (Ft.T @ D @ sparse.csr_matrix(Ct)).toarray()
    A = np.block([[(Ft.T @ D @ Ft).toarray() + PLAYER_RIDGE * np.eye(F.shape[1]), cross],
                  [cross.T, Ct.T @ (Ct * wt[:, None]) + PAIR_RIDGE * np.eye(C.shape[1])]])
    b = np.linalg.solve(A, np.concatenate([Ft.T @ (wt * y[idx]), Ct.T @ (wt * y[idx])]))
    return b[:F.shape[1]], b[F.shape[1]:]


def cv_gain(F, C, y, w) -> float:
    """Share of held-out squared error removed by the pair terms, against player levels alone."""
    fold = np.random.default_rng(SEED).integers(0, FOLDS, len(y))
    base = full = 0.0
    for f in range(FOLDS):
        tr, te = np.flatnonzero(fold != f), np.flatnonzero(fold == f)
        bf, bc = fit(F, C, y, w, tr)
        zero, _ = fit(F, np.zeros_like(C), y, w, tr)
        base += (w[te] * (y[te] - F[te] @ zero) ** 2).sum()
        full += (w[te] * (y[te] - F[te] @ bf - C[te] @ bc) ** 2).sum()
    return float(1 - full / base)


def compute(conn: psycopg.Connection) -> dict:
    seasons, keys, weights, rows = load(conn)
    if not rows:
        return {"pairs": 0}
    F, C, y, w, pairs = design(rows, weights, len(keys))
    effect = fit(F, C, y, w, np.arange(len(y)))[1]
    by_team: dict[tuple, list[int]] = {}
    for i, r in enumerate(rows):
        by_team.setdefault((r[0], r[1]), []).append(i)
    clusters = [np.array(v) for v in by_team.values()]
    rng = np.random.default_rng(SEED)
    boots = np.array([fit(F, C, y, w, np.concatenate([clusters[i] for i in rng.integers(0, len(clusters), len(clusters))]))[1]
                      for _ in range(BOOTSTRAPS)])
    se = boots.std(axis=0)
    gain = cv_gain(F, C, y, w)
    with conn.transaction():
        conn.execute("DELETE FROM feat.role_synergy")
        conn.execute("DELETE FROM feat.role_synergy_meta")
        for j, (x, z) in enumerate(pairs):
            conn.execute("INSERT INTO feat.role_synergy (type_a, type_b, effect, se) VALUES (%s,%s,%s,%s)",
                         (keys[x], keys[z], float(effect[j]), float(se[j])))
        conn.execute("INSERT INTO feat.role_synergy_meta (n_pairs, n_poss, cv_gain, seasons) VALUES (%s,%s,%s,%s)",
                     (len(rows), int(w.sum()), gain, seasons))
    return {"pairs": len(rows), "cv_gain": round(gain, 4), "max_z": round(float(np.abs(effect / se).max()), 1)}
