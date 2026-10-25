"""Player roles in two layers, per side (offense / defense):

  family     a hard label from k-means on the style space. Only the coarse split is
             real structure: offense 3 families, defense 2 (bootstrap ARI 0.97 / 0.98).
  archetypes the extreme "pure" styles found by archetypal analysis; every player is a
             convex mix of them (weights sum to 1). Player styles form a continuum, so
             a mix describes them better than a single fine-grained label.

Pipeline: style features -> standardize (clipped) -> PCA -> families + archetypes.
Only players with at least MIN_MINUTES fit the model; everyone else is projected
onto it and flagged as low confidence.
"""

import json
from dataclasses import dataclass, field
from importlib import resources

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Jsonb
from scipy.optimize import nnls
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

MIN_MINUTES = 500
PCA_VARIANCE = 0.85
SEED = 0
Z_CLIP = 3.0
N_FAMILIES = {"offense": 3, "defense": 2}
N_ARCHETYPES = {"offense": 7, "defense": 4}
AA_ITERS = 60
MIXED_BELOW = 0.5   # a top weight under this reads as "A + B" rather than one style


@dataclass
class SideFit:
    side: str                      # "offense" | "defense"
    model_version: str
    in_fit: pd.Series              # player -> used to fit
    embedding: pd.DataFrame        # player x PCA component
    families: pd.Series            # player -> family id
    family_profiles: pd.DataFrame  # family x feature, mean z of its fit players
    weights: pd.DataFrame          # player x archetype, rows sum to 1
    archetype_profiles: pd.DataFrame  # archetype x feature, the archetype's z-scores
    reference_season: str = ""     # season the model was fit on (names are keyed by it)
    # Fitted pieces, kept so other seasons can be projected onto the same model.
    columns: list = field(default_factory=list)
    medians: pd.Series | None = None
    scaler: StandardScaler | None = None
    pca: PCA | None = None
    kmeans: KMeans | None = None
    archetypes: np.ndarray | None = None


def _simplex_nnls(basis: np.ndarray, y: np.ndarray, penalty: float = 200.0) -> np.ndarray:
    """min ||basis @ w - y|| with w >= 0 and sum(w) = 1, via an appended penalty row."""
    a = np.vstack([basis, penalty * np.ones(basis.shape[1])])
    return nnls(a, np.append(y, penalty), maxiter=2000)[0]


def _archetypes(X: np.ndarray, k: int) -> np.ndarray:
    """Archetypal analysis (Cutler & Breiman): k points in the data's convex hull
    that best reconstruct every row as a convex mix of them."""
    rng = np.random.default_rng(SEED)
    Z = X[rng.choice(len(X), k, replace=False)].copy()
    for _ in range(AA_ITERS):
        A = np.array([_simplex_nnls(Z.T, x) for x in X])
        Z_free = np.linalg.lstsq(A, X, rcond=None)[0]
        Z = np.array([_simplex_nnls(X.T, z) for z in Z_free]) @ X
    return Z


def fit_side(side: str, X: pd.DataFrame, minutes: pd.Series, season: str = "") -> SideFit:
    X = X.loc[:, X.notna().mean() > 0.5]          # drop features most players lack
    in_fit = (minutes.reindex(X.index) >= MIN_MINUTES) & X.notna().mean(axis=1).ge(0.8)
    medians = X[in_fit].median()
    X = X.fillna(medians)

    scaler = StandardScaler().fit(X[in_fit])
    # Clip so one extreme stat (e.g. a league-leading charges rate) can't
    # define a type of its own.
    Z = pd.DataFrame(scaler.transform(X), index=X.index, columns=X.columns).clip(-Z_CLIP, Z_CLIP)
    pca = PCA(n_components=PCA_VARIANCE, random_state=SEED).fit(Z[in_fit])
    P = pca.transform(Z)
    fit_mask = in_fit.to_numpy()

    km = KMeans(N_FAMILIES[side], n_init=10, random_state=SEED).fit(P[fit_mask])
    families = pd.Series(km.predict(P), index=X.index)
    family_profiles = Z[in_fit].groupby(families[in_fit]).mean()

    archetypes = _archetypes(P[fit_mask], N_ARCHETYPES[side])
    weights = pd.DataFrame([_simplex_nnls(archetypes.T, p) for p in P], index=X.index)
    weights = weights.div(weights.sum(axis=1), axis=0)
    archetype_profiles = pd.DataFrame(pca.inverse_transform(archetypes), columns=X.columns)

    version = (f"aa-v1-{side}-f{N_FAMILIES[side]}-a{N_ARCHETYPES[side]}"
               f"-pca{pca.n_components_}-x{len(X.columns)}")
    return SideFit(side, version, in_fit, pd.DataFrame(P, index=X.index), families,
                   family_profiles, weights, archetype_profiles, season,
                   list(X.columns), medians, scaler, pca, km, archetypes)


def project(fit: SideFit, X: pd.DataFrame, minutes: pd.Series) -> SideFit:
    """Place another season's players on a fitted model: same scaling, PCA,
    families and archetypes, so roles mean the same thing across seasons.
    in_fit here means "enough minutes to trust", not "used to fit"."""
    reliable = (minutes.reindex(X.index) >= MIN_MINUTES) & X.reindex(columns=fit.columns).notna().mean(axis=1).ge(0.8)
    Xn = X.reindex(columns=fit.columns).fillna(fit.medians)
    Z = pd.DataFrame(fit.scaler.transform(Xn), index=Xn.index, columns=fit.columns).clip(-Z_CLIP, Z_CLIP)
    P = fit.pca.transform(Z)
    weights = pd.DataFrame([_simplex_nnls(fit.archetypes.T, p) for p in P], index=Xn.index)
    weights = weights.div(weights.sum(axis=1), axis=0)
    return SideFit(fit.side, fit.model_version, reliable, pd.DataFrame(P, index=Xn.index),
                   pd.Series(fit.kmeans.predict(P), index=Xn.index), fit.family_profiles, weights,
                   fit.archetype_profiles, fit.reference_season, fit.columns, fit.medians,
                   fit.scaler, fit.pca, fit.kmeans, fit.archetypes)


def type_names(season: str, fit: SideFit) -> tuple[dict[int, str], dict[int, str]]:
    """(family names, archetype names) for a fitted model, written after
    inspecting it. Empty when the file describes a different model version."""
    path = resources.files("ballstats") / "role_names.json"
    names = json.loads(path.read_text()) if path.is_file() else {}
    entry = names.get(fit.reference_season or season, {}).get(fit.side, {})
    if entry.get("model_version") != fit.model_version:
        return {}, {}
    as_int = lambda d: {int(k): v for k, v in d.items()}
    return as_int(entry.get("families", {})), as_int(entry.get("archetypes", {}))


def style_label(weights: pd.Series, archetype_names: dict[int, str]) -> str:
    name = lambda i: archetype_names.get(int(i), f"原型 {i}")
    top = weights.sort_values(ascending=False)
    if top.iloc[0] >= MIXED_BELOW:
        return name(top.index[0])
    return f"{name(top.index[0])} + {name(top.index[1])}"


def store(conn: psycopg.Connection, season: str, fit: SideFit) -> None:
    fam_names, arch_names = type_names(season, fit)
    with conn.transaction():
        conn.execute("DELETE FROM feat.player_role WHERE season = %s AND side = %s", (season, fit.side))
        conn.execute("DELETE FROM feat.role_type WHERE season = %s AND side = %s", (season, fit.side))
        for level, profiles, names, members in (
            ("family", fit.family_profiles, fam_names, fit.families[fit.in_fit].value_counts()),
            ("archetype", fit.archetype_profiles, arch_names,
             fit.weights[fit.in_fit].idxmax(axis=1).value_counts()),
        ):
            for type_id, row in profiles.iterrows():
                conn.execute(
                    "INSERT INTO feat.role_type (season, side, level, type_id, name, n_fit, profile,"
                    " model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (season, fit.side, level, int(type_id), names.get(int(type_id)),
                     int(members.get(type_id, 0)),
                     Jsonb({f: round(float(v), 3) for f, v in row.items()}), fit.model_version),
                )
        for pid, w in fit.weights.iterrows():
            top = int(w.idxmax())
            fam = int(fit.families[pid])
            conn.execute(
                "INSERT INTO feat.player_role (season, player_id, side, family_id, family_name,"
                " top_archetype_id, top_archetype_name, top_weight, style_label, weights, in_fit,"
                " model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (season, int(pid), fit.side, fam, fam_names.get(fam), top, arch_names.get(top),
                 float(w.max()), style_label(w, arch_names),
                 Jsonb({str(k): round(float(v), 4) for k, v in w.items()}),
                 bool(fit.in_fit.get(pid, False)), fit.model_version),
            )


def report(fit: SideFit, info: pd.DataFrame, season: str, examples: int = 6) -> str:
    fam_names, arch_names = type_names(season, fit)
    fit_ids = fit.in_fit[fit.in_fit].index
    top_w = fit.weights.loc[fit_ids].max(axis=1)
    lines = [f"== {fit.side}: {len(fit_ids)} players in fit, model {fit.model_version}",
             f"   {top_w.ge(0.7).mean():.0%} of players are >=70% one archetype;"
             f" mean top weight {top_w.mean():.2f}"]
    by_minutes = info.loc[fit_ids].sort_values("min", ascending=False)
    for fam, row in fit.family_profiles.iterrows():
        z = row.sort_values()[::-1]
        members = by_minutes[fit.families.loc[by_minutes.index] == fam]
        lines.append(f"\n family [{fam}] {fam_names.get(int(fam), '(unnamed)')}  n={len(members)}")
        lines.append("   high: " + ", ".join(f"{f} {v:+.1f}" for f, v in z[:5].items()))
        lines.append("   e.g.  " + ", ".join(members["name"].head(examples)))
    for a, row in fit.archetype_profiles.iterrows():
        z = row.sort_values()[::-1]
        purest = fit.weights.loc[fit_ids, a].sort_values(ascending=False).head(examples)
        lines.append(f"\n archetype [{a}] {arch_names.get(int(a), '(unnamed)')}")
        lines.append("   high:    " + ", ".join(f"{f} {v:+.1f}" for f, v in z[:5].items()))
        lines.append("   purest:  " + ", ".join(f"{info.at[p, 'name']} {w:.0%}" for p, w in purest.items()))
    return "\n".join(lines)
