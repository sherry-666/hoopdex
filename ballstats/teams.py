"""Team styles: how a roster is built, from the roles of its rotation.

Per team and season, the rotation is its NUM_ROTATION players with the most minutes
(a traded player counts for the team he finished with). The team's style is the
minutes-weighted average of their archetype mixes, offense and defense.

Team-building styles come from k-means on the offensive mix, standardized and fitted
on complete seasons, then applied to every season. Like player roles they are a
continuum (silhouette ~0.19), so a style means "closest to", not a strict faction.
The defensive tag is the defensive archetype the rotation leans on most versus the league.

Team ratings (OVR, offense, defense; centred on 80) blend two halves, each a z-score
against that season's teams:
  roster   the rotation's minutes-weighted player OVR / offense / defense ratings
  results  the team's actual net / offensive / defensive rating per 100 possessions
           (from TeamPlayerOnOffSummary: any player's on-court plus off-court minutes)
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
TEAM_MID, TEAM_SD = 80.0, 6.0
ROSTER_SHARE = 0.5          # the rest comes from actual results
DEFENSE_TAGS = {"护框": "护框型防守", "抢断干扰": "侵略型防守", "外线防投手": "外线封堵型防守", "追防与被针对": "追防型防守"}


def _style_names(version: str) -> dict[int, dict]:
    path = resources.files("ballstats") / "team_styles.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    entry = data.get(version, {})
    return {int(k): v for k, v in entry.items()}


def _team_results(conn: psycopg.Connection) -> pd.DataFrame:
    """Offensive and defensive rating per 100 possessions for every team season."""
    out = []
    for params, body in conn.execute("SELECT params, body FROM raw.raw_response WHERE endpoint = 'TeamPlayerOnOffSummary'"
                                     " AND status = 'ok'"):
        sets = {rs["name"]: [dict(zip(rs["headers"], r)) for r in rs["rowSet"]] for rs in body["resultSets"]}
        on = {r["VS_PLAYER_ID"]: r for r in sets.get("PlayersOnCourtTeamPlayerOnOffSummary", [])}
        off = {r["VS_PLAYER_ID"]: r for r in sets.get("PlayersOffCourtTeamPlayerOnOffSummary", [])}
        both = [p for p in on if p in off]
        if not both:
            continue
        p = max(both, key=lambda p: on[p]["MIN"] or 0)    # any player works; his on + off is the whole season
        a, b = on[p], off[p]
        total = (a["MIN"] or 0) + (b["MIN"] or 0)
        rating = {k: ((a["MIN"] or 0) * (a[k] or 0) + (b["MIN"] or 0) * (b[k] or 0)) / total for k in ("OFF_RATING", "DEF_RATING")}
        out.append({"season": params["season"], "team": a["TEAM_ABBREVIATION"],
                    "ortg": rating["OFF_RATING"], "drtg": rating["DEF_RATING"]})
    return pd.DataFrame(out, columns=["season", "team", "ortg", "drtg"])


def _team_ratings(T: pd.DataFrame) -> pd.DataFrame:
    """Team OVR / offense / defense: half roster, half results, z-scored within each season."""
    zs = lambda c: T.groupby("season")[c].transform(lambda v: (v - v.mean()) / v.std())
    results = {"ovr": T["ortg"] - T["drtg"], "off": T["ortg"], "def": -T["drtg"]}
    out = pd.DataFrame(index=T.index)
    for k, res in results.items():
        T[f"_res_{k}"] = res
        z = ROSTER_SHARE * zs(f"roster_{k}") + (1 - ROSTER_SHARE) * zs(f"_res_{k}").fillna(zs(f"roster_{k}"))
        T["_z"] = z
        z = zs("_z")
        out[f"rating_{k}"] = np.clip(np.round(TEAM_MID + TEAM_SD * z), 50, 99)
    T.drop(columns=[c for c in T.columns if c.startswith("_")], inplace=True)
    return out


def compute(conn: psycopg.Connection) -> dict:
    rows = conn.execute(
        """
        SELECT s.season, s.team, s.player_id, s.name, s.minutes, r.side, r.weights, r.style_label,
               rt.ovr, rt.off, rt.def
        FROM feat.player_stats s
        JOIN feat.player_role r USING (season, player_id)
        LEFT JOIN feat.player_rating rt USING (season, player_id)
        WHERE s.season <> 'career' AND s.team IS NOT NULL
        """).fetchall()
    df = pd.DataFrame(rows, columns=["season", "team", "pid", "name", "min", "side", "w", "style", "ovr", "off", "def"])
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
        roster = {k: float(np.average(ovr[k], weights=ovr["min"])) if len(ovr) else np.nan for k in ("ovr", "off", "def")}
        teams.append({**{f"roster_{k}": v for k, v in roster.items()},
            "season": season, "team": team, "minutes": float(minutes.sum()),
            "off": mixes["offense"], "def": mixes["defense"],
            "avg_ovr": float(np.average(ovr.ovr, weights=ovr["min"])) if len(ovr) else None,
            "core": [{"player_id": int(r.pid), "name": r["name"], "minutes": int(r["min"]), "style": r["style"],
                      "ovr": None if pd.isna(r.ovr) else int(r.ovr), "off": None if pd.isna(r["off"]) else int(r["off"]),
                      "def": None if pd.isna(r["def"]) else int(r["def"])} for _, r in off.iterrows()],
        })
    T = pd.DataFrame(teams)
    T = T.merge(_team_results(conn), on=["season", "team"], how="left")
    T = pd.concat([T, _team_ratings(T)], axis=1)
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
                " rotation_minutes, core, model_version, ovr, off, def, ortg, drtg) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (t.season, t.team, int(t.style_id), DEFENSE_TAGS.get(tag, tag),
                 Jsonb({n: round(float(v), 4) for n, v in zip(off_names, t["off"])}),
                 Jsonb({n: round(float(v), 4) for n, v in zip(def_names, t["def"])}),
                 Jsonb({n: round(float(v), 2) for n, v in zip(off_names, Zo[i])}),
                 None if t.avg_ovr is None else round(t.avg_ovr, 1), round(t.minutes), Jsonb(t.core), version,
                 *(None if pd.isna(t[f"rating_{k}"]) else int(t[f"rating_{k}"]) for k in ("ovr", "off", "def")),
                 *(None if pd.isna(t[k]) else round(float(t[k]), 1) for k in ("ortg", "drtg"))))
    return {"team_seasons": len(T), "fit_on": fit_seasons, "model_version": version, "named": bool(names)}
