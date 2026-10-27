"""Derived views of the role model that the web app reads:

  feat.player_view   per player and side: 2D map position (t-SNE) and scores on the
                     cluster-view axes (f1-f3 varimax factors, l1-l3 LDA axes)
  feat.role_axis     what each of those axes means
  feat.player_stats  per player: raw style and outcome values in readable units
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Jsonb
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.manifold import TSNE

MIN_SHOWN = 100     # players under this many minutes get no views at all
EARLY_SEASON_MIN = 20   # the cutoff instead, while fewer than 200 players have reached MIN_SHOWN
N_FACTORS = 3
FEATURE_LABELS = {
    "shot_rim": "篮下出手占比", "shot_short_mid": "短中距离占比", "shot_long_mid": "长中距离占比",
    "shot_corner3": "底角三分占比", "shot_atb3": "弧顶三分占比", "shot_deep3": "超远三分占比",
    "fta_rate": "罚球出手率", "usg_pct": "使用率", "ast_pct": "助攻率", "uast_fgm_pct": "非助攻进球占比",
    "oreb_pct": "进攻篮板率", "drives_36": "突破 / 36 分钟", "touches_36": "触球 / 36 分钟",
    "sec_per_touch": "每次触球秒数", "drib_per_touch": "每次触球运球", "elbow_touch_share": "肘区触球占比",
    "post_touch_share": "低位触球占比", "paint_touch_share": "油漆区触球占比",
    "cs_fga_share": "接球投占比", "pullup_fga_share": "急停投占比", "screen_ast_36": "掩护助攻 / 36",
    "height_in": "身高", "weight_lb": "体重",
    "off_pt_Transition": "快攻", "off_pt_Isolation": "单打", "off_pt_PRBallHandler": "挡拆持球",
    "off_pt_PRRollman": "挡拆顺下", "off_pt_Postup": "背身", "off_pt_Spotup": "定点",
    "off_pt_Handoff": "手递手", "off_pt_Cut": "空切", "off_pt_OffScreen": "绕掩护", "off_pt_OffRebound": "补篮",
    "blk_36": "盖帽 / 36", "stl_36": "抢断 / 36", "dreb_pct": "防守篮板率", "rim_dfga_36": "篮下被投 / 36",
    "deflections_36": "干扰传球 / 36", "charges_36": "造进攻犯规 / 36", "contest3_share": "干扰中三分占比",
    "contests_36": "干扰出手 / 36", "dfga3_share": "被投中三分占比", "dfga_lt6_share": "被投中 6ft 内占比",
    "speed_def": "防守移动速度",
    "def_pt_Transition": "防快攻", "def_pt_Isolation": "防单打", "def_pt_PRBallHandler": "防挡拆持球",
    "def_pt_PRRollman": "防挡拆顺下", "def_pt_Postup": "防背身", "def_pt_Spotup": "防定点",
    "def_pt_Handoff": "防手递手", "def_pt_Cut": "防空切", "def_pt_OffScreen": "防绕掩护",
    "def_pt_OffRebound": "防补篮",
}
# Names for the varimax factors (sorted by variance, signs oriented so the largest
# loading is positive), written after reading their loadings for 2025-26.
FACTOR_NAMES = {
    "offense": ["持球创造指数（低 = 接球投射）", "内线终结指数", "低位组织指数"],
    "defense": ["外线指数（低 = 护框）", "追防指数（低 = 挡拆大个）", "抢断干扰指数"],
}


def min_shown(minutes: pd.Series) -> int:
    """MIN_SHOWN, or EARLY_SEASON_MIN while fewer than 200 players have reached it."""
    return MIN_SHOWN if (minutes >= MIN_SHOWN).sum() >= 200 else EARLY_SEASON_MIN


def shown_players(fit, minutes: pd.Series) -> list:
    cutoff = min_shown(minutes)
    return [p for p in fit.weights.index if minutes.get(p, 0) >= cutoff]


def _varimax(L: np.ndarray, iters: int = 200, tol: float = 1e-8) -> np.ndarray:
    p, k = L.shape
    R, d = np.eye(k), 0.0
    for _ in range(iters):
        Lr = L @ R
        u, s, vt = np.linalg.svd(L.T @ (Lr ** 3 - Lr @ np.diag((Lr ** 2).sum(0)) / p))
        R = u @ vt
        if s.sum() < d * (1 + tol):
            break
        d = s.sum()
    return L @ R


def map_coords(fit, shown: list) -> pd.DataFrame:
    xy = TSNE(n_components=2, perplexity=30, init="pca", random_state=0) \
        .fit_transform(fit.embedding.loc[shown].to_numpy())
    return pd.DataFrame(xy, index=shown, columns=["x", "y"])


@dataclass
class AxisModel:
    """Cluster-view axes fitted on one season and applied to any other, so a position
    means the same thing in every season: f1-f3 varimax factors (readable), l1-l3 LDA
    on the top archetype (most separated). Scores are z-scaled on the fitting season."""
    cols: list
    med: pd.Series
    mu: pd.Series
    sd: pd.Series
    proj: np.ndarray
    f_mean: np.ndarray
    f_sd: np.ndarray
    lda: LinearDiscriminantAnalysis
    e_mean: np.ndarray
    e_sd: np.ndarray
    meta: list = field(default_factory=list)

    def _z(self, X: pd.DataFrame, rows: list) -> np.ndarray:
        return ((X.reindex(index=rows, columns=self.cols).fillna(self.med) - self.mu) / self.sd).clip(-3, 3).to_numpy()

    def scores(self, X: pd.DataFrame, rows: list) -> pd.DataFrame:
        Z = self._z(X, rows)
        F = (Z @ self.proj - self.f_mean) / self.f_sd
        E = (self.lda.transform(Z) - self.e_mean) / self.e_sd
        return pd.DataFrame(np.hstack([F, E]), index=rows,
                            columns=[f"f{j + 1}" for j in range(N_FACTORS)] + [f"l{j + 1}" for j in range(N_FACTORS)])


def fit_axes(side: str, X: pd.DataFrame, fit) -> AxisModel:
    ids = list(fit.in_fit[fit.in_fit].index)
    cols = list(fit.archetype_profiles.columns)
    ref = X.loc[ids, cols]
    med = ref.median()
    mu, sd = ref.fillna(med).mean(), ref.fillna(med).std()
    Zf = ((ref.fillna(med) - mu) / sd).clip(-3, 3).to_numpy()

    _, s, vt = np.linalg.svd(Zf - Zf.mean(0), full_matrices=False)
    L = _varimax(vt[:N_FACTORS].T * s[:N_FACTORS] / np.sqrt(len(Zf)))
    L = L[:, np.argsort(-(L ** 2).sum(0))]
    L *= np.sign(L[np.abs(L).argmax(0), range(N_FACTORS)])
    proj = np.linalg.pinv(L).T
    F_fit = Zf @ proj

    y = fit.weights.loc[ids].idxmax(axis=1).to_numpy()
    lda = LinearDiscriminantAnalysis(n_components=N_FACTORS).fit(Zf, y)
    E_fit = lda.transform(Zf)

    label = lambda c: FEATURE_LABELS.get(c, c)
    meta = []
    for method, loads, names in (
        ("factor", L, FACTOR_NAMES[side]),
        ("lda", lda.scalings_[:, :N_FACTORS], [f"判别轴 {j + 1}" for j in range(N_FACTORS)]),
    ):
        for j in range(N_FACTORS):
            load = pd.Series(loads[:, j], index=cols).sort_values()
            meta.append({"method": method, "axis": f"{method[0]}{j + 1}", "name": names[j],
                         "high": "、".join(label(c) for c in load.index[::-1][:4]),
                         "low": "、".join(label(c) for c in load.index[:3])})
    return AxisModel(cols, med, mu, sd, proj, F_fit.mean(0), F_fit.std(0), lda, E_fit.mean(0), E_fit.std(0), meta)


def cluster_axes(side: str, X: pd.DataFrame, fit, shown: list) -> tuple[pd.DataFrame, list[dict]]:
    """Axes fitted on this season and applied to its own players (export script)."""
    am = fit_axes(side, X, fit)
    return am.scores(X, shown), am.meta


def stat_values(info: pd.DataFrame, off: pd.DataFrame, de: pd.DataFrame) -> pd.DataFrame:
    """Raw values in readable units: shares as 0-1, counts per 36, cm and kg."""
    raw = off.join(de.drop(columns=["height_in"]), how="outer")
    raw["height_cm"] = raw.pop("height_in") * 2.54
    raw["weight_kg"] = raw.pop("weight_lb") * 0.4536
    for col in ["pts_36", "reb_36", "ast_36", "fg3a_36", "ts_pct", "fg3_pct"]:
        raw[col] = info[col]
    return raw


def store_side(conn: psycopg.Connection, season: str, fit, X: pd.DataFrame, minutes: pd.Series,
               axes: AxisModel | None = None) -> None:
    shown = shown_players(fit, minutes)
    axes = axes or fit_axes(fit.side, X, fit)
    _store_view(conn, season, fit.side, map_coords(fit, shown), axes.scores(X, shown), axes.meta)


def _store_view(conn, season: str, side: str, xy: pd.DataFrame, scores: pd.DataFrame, meta: list) -> None:
    shown = list(xy.index)
    with conn.transaction():
        conn.execute("DELETE FROM feat.player_view WHERE season = %s AND side = %s", (season, side))
        conn.execute("DELETE FROM feat.role_axis WHERE season = %s AND side = %s", (season, side))
        for m in meta:
            conn.execute(
                "INSERT INTO feat.role_axis (season, side, method, axis, name, high, low)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (season, side, m["method"], m["axis"], m["name"], m["high"], m["low"]),
            )
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO feat.player_view (season, player_id, side, x, y, f1, f2, f3, l1, l2, l3)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(season, int(p), side, *(round(float(v), 4) for v in (*xy.loc[p], *scores.loc[p])))
                 for p in shown],
            )


def store_stats(conn: psycopg.Connection, season: str, info: pd.DataFrame,
                off: pd.DataFrame, de: pd.DataFrame) -> None:
    raw = stat_values(info, off, de)
    # Early in a season almost nobody has MIN_SHOWN minutes yet; keep anyone who has played a bit.
    cutoff = min_shown(info["min"])
    ids = [p for p in raw.index if info.at[p, "min"] >= cutoff] if len(info) else []
    with conn.transaction():
        conn.execute("DELETE FROM feat.player_stats WHERE season = %s", (season,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO feat.player_stats (season, player_id, name, team, gp, minutes, stats)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [(season, int(p), info.at[p, "name"], info.at[p, "team"], int(info.at[p, "gp"]),
                  int(round(info.at[p, "min"])),
                  Jsonb({c: (None if pd.isna(v) else round(float(v), 4)) for c, v in raw.loc[p].items()}))
                 for p in ids],
            )


CAREER = "career"   # the season key under which career-wide views are stored


def rebuild_all(conn: psycopg.Connection, reference: str, seasons: list[str]) -> dict:
    """Fit the role model and the cluster axes on the reference season, apply both to every
    season, and add a career view: each player's per-season style averaged by minutes.
    Averaging is valid because every season lives in the same model space."""
    from ballstats import features, roles

    data = {s: features.build(conn, s) for s in seasons}
    counts = {}
    for side, idx in (("offense", 1), ("defense", 2)):
        ref_info, X_ref = data[reference][0], data[reference][idx]
        ref_fit = roles.fit_side(side, X_ref, ref_info["min"], reference)
        axes = fit_axes(side, X_ref, ref_fit)
        per_season = []
        for s in seasons:
            info, X = data[s][0], data[s][idx]
            fit = ref_fit if s == reference else roles.project(ref_fit, X, info["min"])
            roles.store(conn, s, fit)
            store_side(conn, s, fit, X, info["min"], axes)
            per_season.append((s, fit, X, info))
        counts[side] = _store_career_side(conn, side, ref_fit, axes, per_season)
    for s in seasons:
        store_stats(conn, s, *data[s])
    counts["career_stats"] = _store_career_stats(conn, data)
    from ballstats import blend
    counts["blend"] = blend.blend_roles(conn)
    return counts


def _store_career_side(conn, side: str, ref_fit, axes: AxisModel, per_season: list) -> int:
    from ballstats import roles

    acc: dict = {}
    for _season, fit, X, info in per_season:
        shown = shown_players(fit, info["min"])
        scores = axes.scores(X, shown)
        for p in shown:
            a = acc.setdefault(p, {"w": [], "emb": [], "mix": [], "sc": [], "qualified": False})
            a["w"].append(float(info.at[p, "min"]))
            a["emb"].append(fit.embedding.loc[p].to_numpy())
            a["mix"].append(fit.weights.loc[p].to_numpy())
            a["sc"].append(scores.loc[p].to_numpy())
            a["qualified"] |= bool(fit.in_fit.get(p, False))
    pids = list(acc)
    avg = lambda key: np.vstack([np.average(acc[p][key], axis=0, weights=acc[p]["w"]) for p in pids])
    emb, mix, sc = avg("emb"), avg("mix"), avg("sc")
    mix = mix / mix.sum(axis=1, keepdims=True)
    career_fit = roles.SideFit(
        side, ref_fit.model_version, pd.Series([acc[p]["qualified"] for p in pids], index=pids),
        pd.DataFrame(emb, index=pids), pd.Series(ref_fit.kmeans.predict(emb), index=pids),
        ref_fit.family_profiles, pd.DataFrame(mix, index=pids, columns=ref_fit.weights.columns),
        ref_fit.archetype_profiles, ref_fit.reference_season)
    roles.store(conn, CAREER, career_fit)
    xy = TSNE(n_components=2, perplexity=30, init="pca", random_state=0).fit_transform(emb)
    _store_view(conn, CAREER, side, pd.DataFrame(xy, index=pids, columns=["x", "y"]),
                pd.DataFrame(sc, index=pids, columns=[f"f{j + 1}" for j in range(N_FACTORS)] + [f"l{j + 1}" for j in range(N_FACTORS)]),
                axes.meta)
    return len(pids)


def _store_career_stats(conn, data: dict) -> int:
    """Minutes-weighted average of each stat over the seasons a player is shown in."""
    frames = []
    for s in sorted(data):
        info, off, de = data[s]
        raw = stat_values(info, off, de)
        cutoff = min_shown(info["min"])
        keep = [p for p in raw.index if info.at[p, "min"] >= cutoff]
        f = raw.loc[keep].copy()
        f["_min"], f["_gp"], f["_name"], f["_team"], f["_season"] = (
            info.loc[keep, "min"], info.loc[keep, "gp"], info.loc[keep, "name"], info.loc[keep, "team"], s)
        frames.append(f)
    allf = pd.concat(frames)
    stat_cols = [c for c in allf.columns if not c.startswith("_")]
    rows = []
    for pid, g in allf.groupby(level=0):
        latest = g.sort_values("_season").iloc[-1]
        stats = {}
        for c in stat_cols:
            ok = g[c].notna()
            stats[c] = round(float(np.average(g.loc[ok, c], weights=g.loc[ok, "_min"])), 4) if ok.any() else None
        rows.append((CAREER, int(pid), latest["_name"], latest["_team"], int(g["_gp"].sum()),
                     int(round(g["_min"].sum())), Jsonb(stats)))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM feat.player_stats WHERE season = %s", (CAREER,))
        cur.executemany("INSERT INTO feat.player_stats (season, player_id, name, team, gp, minutes, stats)"
                        " VALUES (%s,%s,%s,%s,%s,%s,%s)", rows)
    return len(rows)
