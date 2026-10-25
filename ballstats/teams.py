"""Team styles: how a roster is built, from the roles of its rotation.

Per team and season, the rotation is its NUM_ROTATION players with the most minutes
(a traded player counts for the team he finished with). The team's style is the
minutes-weighted average of their archetype mixes, offense and defense.

Team-building styles come from k-means on the offensive mix, standardized and fitted
on complete seasons, then applied to every season. Like player roles they are a
continuum (silhouette ~0.19), so a style means "closest to", not a strict faction.
The defensive tag is the defensive archetype the rotation leans on most versus the league.
"""

import json
from importlib import resources

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Jsonb
from sklearn.cluster import KMeans

NUM_ROTATION = 9
N_STYLES = 5
SEED = 0
MIN_TEAM_MINUTES = 1500     # a season counts as complete for fitting once rotations reach this
DEFENSE_TAGS = {"护框": "护框型防守", "抢断干扰": "侵略型防守", "外线防投手": "外线封堵型防守", "追防与被针对": "追防型防守"}


def _style_names(version: str) -> dict[int, dict]:
    path = resources.files("ballstats") / "team_styles.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    entry = data.get(version, {})
    return {int(k): v for k, v in entry.items()}


def compute(conn: psycopg.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT s.season, s.team, s.player_id, s.name, s.minutes, r.side, r.weights, r.style_label,
               rt.ovr
        FROM feat.player_stats s
        JOIN feat.player_role r USING (season, player_id)
        LEFT JOIN feat.player_rating rt USING (season, player_id)
        WHERE s.season <> 'career' AND s.team IS NOT NULL
        """).fetchall()
    df = pd.DataFrame(rows, columns=["season", "team", "pid", "name", "min", "side", "w", "style", "ovr"])
    arch = {side: {int(t): n for t, n in conn.execute(
        "SELECT DISTINCT type_id, name FROM feat.role_type WHERE side = %s AND level = 'archetype'", (side,))}
        for side in ("offense", "defense")}

    teams = []
    for (season, team), g in df.groupby(["season", "team"]):
        off = g[g.side == "offense"].sort_values("min", ascending=False).head(NUM_ROTATION)
        ids, minutes = list(off.pid), off.set_index("pid")["min"]
        mixes = {}
        for side in ("offense", "defense"):
            gg = g[(g.side == side) & g.pid.isin(ids)].set_index("pid").loc[ids]
            W = np.array([[w.get(str(i), 0.0) for i in sorted(arch[side])] for w in gg.w])
            mixes[side] = np.average(W, axis=0, weights=minutes.loc[ids])
        ovr = off.dropna(subset=["ovr"])
        teams.append({
            "season": season, "team": team, "minutes": float(minutes.sum()),
            "off": mixes["offense"], "def": mixes["defense"],
            "avg_ovr": float(np.average(ovr.ovr, weights=ovr["min"])) if len(ovr) else None,
            "core": [{"player_id": int(r.pid), "name": r["name"], "minutes": int(r["min"]), "style": r["style"],
                      "ovr": None if pd.isna(r.ovr) else int(r.ovr)} for _, r in off.iterrows()],
        })
    T = pd.DataFrame(teams)
    complete = T.groupby("season")["minutes"].median()
    fit_seasons = sorted(complete[complete >= MIN_TEAM_MINUTES].index)
    fit_mask = T.season.isin(fit_seasons).to_numpy()
    off, de = np.vstack(T["off"]), np.vstack(T["def"])
    o_mu, o_sd = off[fit_mask].mean(0), off[fit_mask].std(0)
    d_mu, d_sd = de[fit_mask].mean(0), de[fit_mask].std(0)
    Zo, Zd = (off - o_mu) / o_sd, (de - d_mu) / d_sd
    km = KMeans(N_STYLES, n_init=20, random_state=SEED).fit(Zo[fit_mask])
    T["style_id"] = km.predict(Zo)
    version = f"team-v1-k{N_STYLES}-{'+'.join(fit_seasons)}"
    names = _style_names(version)

    off_names = [arch["offense"][i] for i in sorted(arch["offense"])]
    def_names = [arch["defense"][i] for i in sorted(arch["defense"])]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE feat.team_profile, feat.team_style")
        for k, center in enumerate(km.cluster_centers_):
            info = names.get(k, {})
            cur.execute(
                "INSERT INTO feat.team_style (style_id, name, description, centroid, model_version) VALUES (%s,%s,%s,%s,%s)",
                (k, info.get("name"), info.get("description"),
                 Jsonb({n: round(float(v), 2) for n, v in zip(off_names, center)}), version))
        for i, t in T.iterrows():
            tag = def_names[int(np.argmax(Zd[i]))]
            cur.execute(
                "INSERT INTO feat.team_profile (season, team, style_id, defense_tag, off_mix, def_mix, off_z, avg_ovr,"
                " rotation_minutes, core, model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (t.season, t.team, int(t.style_id), DEFENSE_TAGS.get(tag, tag),
                 Jsonb({n: round(float(v), 4) for n, v in zip(off_names, t["off"])}),
                 Jsonb({n: round(float(v), 4) for n, v in zip(def_names, t["def"])}),
                 Jsonb({n: round(float(v), 2) for n, v in zip(off_names, Zo[i])}),
                 None if t.avg_ovr is None else round(t.avg_ovr, 1), round(t.minutes), Jsonb(t.core), version))
    return {"team_seasons": len(T), "fit_on": fit_seasons, "model_version": version, "named": bool(names)}
