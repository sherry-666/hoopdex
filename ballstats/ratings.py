"""Overall rating (OVR, out of 99) per player season, plus peak and career ratings.

Version 1 is a box-score estimate, available for every season since 1996-97 from
league-wide totals. It will be replaced by the impact model (RAPM + prior) once that
exists. Per season:

  1. Three components, each a z-score against that season's players with 500+ minutes:
       contribution   PIE, the NBA's share-of-game-events estimate         weight 0.40
       scoring        usage x (TS% - league TS%) + 0.3 x (usage - league
                      usage): efficiency on volume, plus credit for volume  weight 0.40
       on-court       team net rating with him on the floor, shrunk by
                      minutes toward 0 (it is noisy and team-dependent)      weight 0.20
  2. The weighted sum is re-standardized, then pulled toward replacement level
     (-1.0) by sample size: weight = minutes / (minutes + 250).
  3. OVR = 77 + 6.5 x z, clipped to 40..99. A median 500-minute player lands near 75,
     +2 sd at 90, +3.4 sd at 99: roughly the NBA 2K spread.

Box-score estimates favour efficient rim-running bigs (rebounds and easy shots);
the RAPM-based version should correct most of that.

Peak = best average over three qualifying (500+ minute) seasons in a row.
Career = 0.7 x peak + 0.3 x the minutes-weighted average over qualifying seasons.
"""

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from ballstats import blend
from ballstats.collector import result_rows

MODEL_VERSION = "ovr-box-v3"
MIN_MINUTES = 500
MIN_QUALIFIED = 100         # below this many 500-minute players, borrow a prior season's baseline
WEIGHTS = {"contribution": 0.40, "scoring": 0.40, "on_court": 0.20}
OFF_WEIGHTS = {"scoring": 0.45, "playmaking": 0.25, "off_rebounding": 0.10, "on_court": 0.20}
DEF_WEIGHTS = {"steals": 0.20, "blocks": 0.15, "def_rebounding": 0.15, "on_court": 0.50}
# From 2015-16 on, tracking data adds how much worse opponents shoot against him than they normally do.
DEF_WEIGHTS_TRACKED = {"contest": 0.25, "steals": 0.15, "blocks": 0.10, "def_rebounding": 0.10, "on_court": 0.35,
                      "charges": 0.05}
SCALES = {"ovr": WEIGHTS, "off": OFF_WEIGHTS, "def": DEF_WEIGHTS_TRACKED}
CONTEST_SHRINK_FGA = 500    # the opponent-FG% edge keeps d_fga / (d_fga + this) of its value
USAGE_CREDIT = 0.3          # scoring credit per point of usage above league average
TEAM_SHARE = 0.3            # on-court off/def: vs his own team, plus this share of the team's edge on the league
TOV_PENALTY = 0.5           # playmaking = assist % - this x turnover ratio
NET_SHRINK_MIN = 1000       # on-court net rating keeps minutes / (minutes + this) of its value
RELIABILITY_MIN = 250       # rating keeps minutes / (minutes + this) of its distance from replacement
REPLACEMENT_Z = -1.0
SCALE_MID, SCALE_SD = 77.0, 6.5
PEAK_WINDOW = 3
CAREER_PEAK_WEIGHT = 0.7


def load_hustle(conn: psycopg.Connection, season: str) -> pd.DataFrame | None:
    row = conn.execute(
        "SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueHustleStatsPlayer' AND status = 'ok'"
        " AND params->>'season' = %s", (season,)).fetchone()
    return pd.DataFrame(result_rows(row[0])).set_index("PLAYER_ID") if row else None


def _season_table(conn: psycopg.Connection, season: str) -> pd.DataFrame | None:
    def load(measure: str) -> pd.DataFrame | None:
        row = conn.execute(
            "SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueDashPlayerStats' AND status = 'ok'"
            " AND params->>'season' = %s AND params->>'measure_type_detailed_defense' = %s"
            " AND params->>'per_mode_detailed' = 'Totals'", (season, measure)).fetchone()
        return pd.DataFrame(result_rows(row[0])).set_index("PLAYER_ID") if row else None

    base, adv = load("Base"), load("Advanced")
    if base is None or adv is None or base.empty:
        return None
    hustle = load_hustle(conn, season)
    dfd = conn.execute(
        "SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueDashPtDefend' AND status = 'ok'"
        " AND params->>'season' = %s AND params->>'defense_category' = 'Overall'", (season,)).fetchone()
    t = pd.DataFrame({
        "name": base["PLAYER_NAME"], "team": base["TEAM_ABBREVIATION"], "gp": base["GP"], "minutes": base["MIN"],
        "pie": adv["PIE"], "ts": adv["TS_PCT"], "usg": adv["USG_PCT"], "net": adv["NET_RATING"],
        "ortg": adv["OFF_RATING"], "drtg": adv["DEF_RATING"], "ast_pct": adv["AST_PCT"], "tov_pct": adv["TM_TOV_PCT"],
        "oreb_pct": adv["OREB_PCT"], "dreb_pct": adv["DREB_PCT"],
        "stl_36": base["STL"] * 36 / base["MIN"].clip(lower=1), "blk_36": base["BLK"] * 36 / base["MIN"].clip(lower=1),
    })
    t = t.dropna(subset=["pie", "ts", "usg", "net", "ortg", "drtg", "minutes"]).fillna(0.0)
    # Opponents' shooting against him vs their norm (negative = he holds them down). A defender listed
    # twice keeps the line with more games. NaN everywhere when the season has no tracking data.
    t["d_fga"] = t["d_pm"] = np.nan
    if dfd:
        d = pd.DataFrame(result_rows(dfd[0])).sort_values("GP", ascending=False).drop_duplicates("CLOSE_DEF_PERSON_ID")
        d = d.set_index("CLOSE_DEF_PERSON_ID")
        t["d_fga"] = d["D_FGA"].reindex(t.index).fillna(0.0)
        t["d_pm"] = d["PCT_PLUSMINUS"].reindex(t.index).fillna(0.0)
    t["charges_36"] = 0.0
    if hustle is not None:
        t["charges_36"] = (hustle["CHARGES_DRAWN"].reindex(t.index) * 36 / t["minutes"].clip(lower=1)).fillna(0.0)
    # Team ratings as the minutes-weighted average of its players' on-court ratings (a traded
    # player counts for the team he finished with).
    for k in ("ortg", "drtg"):
        w = t[k] * t["minutes"]
        t[f"team_{k}"] = w.groupby(t["team"]).transform("sum") / t["minutes"].groupby(t["team"]).transform("sum")
    return t


def _shrink(v: pd.Series, minutes: pd.Series) -> pd.Series:
    return v * minutes / (minutes + NET_SHRINK_MIN)


def _components(t: pd.DataFrame, lg: dict[str, float]) -> dict[str, pd.DataFrame]:
    """Raw component values per scale; lg holds league averages of the baseline season."""
    m = t["minutes"]
    return {
        "ovr": pd.DataFrame({
            "contribution": t["pie"],
            "scoring": (t["usg"] * (t["ts"] - lg["ts"]) + USAGE_CREDIT * (t["usg"] - lg["usg"])) * 100,
            "on_court": _shrink(t["net"], m),
        }),
        "off": pd.DataFrame({
            "scoring": (t["usg"] * (t["ts"] - lg["ts"]) + USAGE_CREDIT * (t["usg"] - lg["usg"])) * 100,
            "playmaking": t["ast_pct"] * 100 - TOV_PENALTY * t["tov_pct"],
            "off_rebounding": t["oreb_pct"],
            "on_court": _shrink(t["ortg"] - t["team_ortg"] + TEAM_SHARE * (t["team_ortg"] - lg["ortg"]), m),
        }),
        "def": pd.DataFrame({
            "contest": -t["d_pm"].fillna(0.0) * t["d_fga"].fillna(0.0) / (t["d_fga"].fillna(0.0) + CONTEST_SHRINK_FGA),
            "charges": t["charges_36"],
            "steals": t["stl_36"],
            "blocks": t["blk_36"],
            "def_rebounding": t["dreb_pct"],
            "on_court": _shrink(t["team_drtg"] - t["drtg"] + TEAM_SHARE * (lg["drtg"] - t["team_drtg"]), m),
        }),
    }


def season_ratings(t: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Rate every player of table t against the qualified players of baseline (t itself,
    or an earlier season while t is still early), on all three scales."""
    ref = baseline[baseline["minutes"] >= MIN_MINUTES]
    lg = {k: float(np.average(ref[k], weights=ref["minutes"])) for k in ("ts", "usg", "ortg", "drtg")}
    ref_c, mine = _components(ref, lg), _components(t, lg)
    reliability = t["minutes"] / (t["minutes"] + RELIABILITY_MIN)
    out = t[["name", "team", "gp", "minutes"]].copy()
    tracked = bool(t["d_fga"].notna().any() and ref["d_fga"].notna().any())
    for scale, weights in SCALES.items():
        if scale == "def" and not tracked:
            weights = DEF_WEIGHTS
        mean, sd = ref_c[scale].mean(), ref_c[scale].std()
        z = (mine[scale] - mean) / sd
        ref_combo = sum(((ref_c[scale][k] - mean[k]) / sd[k]) * w for k, w in weights.items())
        zc = (sum(z[k] * w for k, w in weights.items()) - ref_combo.mean()) / ref_combo.std()
        z_adj = reliability * zc + (1 - reliability) * REPLACEMENT_Z
        out[scale] = np.clip(np.round(SCALE_MID + SCALE_SD * z_adj), 40, 99).astype(int)
        out[f"z_{scale}"] = z_adj
        out[f"zc_{scale}"] = zc
        for k in weights:
            out[f"{scale}.{k}"] = z[k]
    out["reliability"] = reliability
    out["tracked"] = tracked
    for k, v in lg.items():
        out[f"league_{k}"] = v
    return out


def _rounded(d: dict) -> dict:
    return {k: _rounded(v) if isinstance(v, dict) else round(float(v), 4) for k, v in d.items()}


def _career(pool: pd.DataFrame, col: str) -> tuple[float, str, str, float, float]:
    """(peak, peak_from, peak_to, average, career) of one rating column over a player's seasons."""
    vals = pool[col].to_numpy(dtype=float)
    if len(vals) >= PEAK_WINDOW:
        means = np.convolve(vals, np.ones(PEAK_WINDOW) / PEAK_WINDOW, mode="valid")
        i = int(means.argmax())
        peak, frm, to = float(means[i]), pool["season"].iloc[i], pool["season"].iloc[i + PEAK_WINDOW - 1]
    else:
        peak, frm, to = float(vals.mean()), pool["season"].iloc[0], pool["season"].iloc[-1]
    avg = float(np.average(vals, weights=pool["minutes"]))
    career = CAREER_PEAK_WEIGHT * peak + (1 - CAREER_PEAK_WEIGHT) * avg
    return round(peak, 1), frm, to, round(avg, 1), round(career, 1)


def compute(conn: psycopg.Connection) -> dict[str, int]:
    seasons = [r[0] for r in conn.execute(
        "SELECT DISTINCT params->>'season' FROM raw.raw_response WHERE endpoint = 'LeagueDashPlayerStats'"
        " AND status = 'ok' AND params->>'measure_type_detailed_defense' = 'Advanced'"
        " AND params->>'per_mode_detailed' = 'Totals' ORDER BY 1")]
    tables = {s: t for s in seasons if (t := _season_table(conn, s)) is not None}
    rows, last_complete, hist = [], None, {}
    newest = max(tables)
    for s in sorted(tables):
        t = tables[s]
        complete = (t["minutes"] >= MIN_MINUTES).sum() >= MIN_QUALIFIED
        if complete:
            last_complete = s
        base_season = s if complete or last_complete is None else last_complete
        r = season_ratings(t, tables[base_season])
        # The season in progress: blend each returning player with the seasons before it (blend.py).
        priors = [(p, d) for p, d in blend.prior_seasons(s) if p in hist]
        prior_labels = {}
        if s == newest and t["gp"].max() < blend.ONGOING_MAX_GP and priors:
            # Each prior season counts by minutes played x decay, so a missed or short season fades out;
            # looking back stops at the first season with 500+ minutes.
            mins = pd.DataFrame({p: hist[p]["minutes"].reindex(r.index) for p, _ in priors}).fillna(0)
            enough = (mins >= MIN_MINUTES).astype(int)
            pw = mins * [d for _, d in priors] * ((enough.cumsum(axis=1) - enough) == 0)   # stop after a full season
            blended = pw.index[pw.sum(axis=1) > 0]
            w = r.loc[blended, "minutes"].map(blend.player_weight)
            r["blend_weight"] = np.nan
            r.loc[blended, "blend_weight"] = w
            to_scale = lambda z: np.clip(np.round(SCALE_MID + SCALE_SD * z), 40, 99)
            for scale in SCALES:
                prior_z = sum(hist[p][f"z_{scale}"].reindex(blended).fillna(0) * pw.loc[blended, p]
                              for p, _ in priors) / pw.loc[blended].sum(axis=1)
                r[f"own_{scale}"] = to_scale(r[f"zc_{scale}"])           # this season alone, unshrunk
                r[f"prior_{scale}"] = np.nan
                r.loc[blended, f"prior_{scale}"] = to_scale(prior_z)
                z = w * r.loc[blended, f"zc_{scale}"] + (1 - w) * prior_z
                r.loc[blended, f"z_{scale}"] = z
                r.loc[blended, scale] = np.clip(np.round(SCALE_MID + SCALE_SD * z), 40, 99).astype(int)
            prior_labels = {pid: ", ".join(p for p, _ in priors if pw.loc[pid, p] > 0) for pid in blended}
        hist[s] = r
        for pid, x in r.iterrows():
            raw = t.loc[pid]
            detail = {
                "contribution": x["ovr.contribution"], "scoring": x["ovr.scoring"], "on_court": x["ovr.on_court"],
                "reliability": x["reliability"], "pie": raw["pie"], "ts": raw["ts"], "usg": raw["usg"],
                "net": raw["net"], "league_ts": x["league_ts"],
                "off": {**{k: x[f"off.{k}"] for k in OFF_WEIGHTS}, "ortg": raw["ortg"], "league_ortg": x["league_ortg"],
                        "ast_pct": raw["ast_pct"], "tov_pct": raw["tov_pct"], "oreb_pct": raw["oreb_pct"]},
                "def": {**{k: x[f"def.{k}"] for k in (DEF_WEIGHTS_TRACKED if x["tracked"] else DEF_WEIGHTS)},
                        "drtg": raw["drtg"], "league_drtg": x["league_drtg"],
                        "stl_36": raw["stl_36"], "blk_36": raw["blk_36"], "dreb_pct": raw["dreb_pct"],
                        **({"d_fga": raw["d_fga"], "d_pm": raw["d_pm"], "charges_36": raw["charges_36"]} if x["tracked"] else {})},
            }
            if pd.notna(x.get("blend_weight", np.nan)):
                detail["blend"] = {"weight": x["blend_weight"], **{f"own_{k}": x[f"own_{k}"] for k in SCALES},
                                   **{f"prior_{k}": x[f"prior_{k}"] for k in SCALES}}
                detail_prior = prior_labels[pid]
            else:
                detail_prior = None
            rows.append((s, int(pid), x["name"], x["team"], int(x["gp"]), float(x["minutes"]), int(x["ovr"]),
                         round(float(x["z_ovr"]), 3), int(x["off"]), int(x["def"]),
                         bool(x["minutes"] >= MIN_MINUTES), base_season,
                         Jsonb({**_rounded(detail), **({"blend_prior": detail_prior} if detail_prior else {})}), MODEL_VERSION))

    df = pd.DataFrame(rows, columns=["season", "player_id", "name", "team", "gp", "minutes", "ovr", "z", "off", "def",
                                     "qualified", "baseline_season", "detail", "model_version"])
    careers = []
    for pid, g in df.sort_values("season").groupby("player_id"):
        q = g[g["qualified"]]
        pool = q if len(q) else g
        peak, frm, to, avg, career = _career(pool, "ovr")
        off, de = _career(pool, "off"), _career(pool, "def")
        careers.append((int(pid), peak, frm, to, avg, career, off[4], off[0], de[4], de[0],
                        len(g), len(q), MODEL_VERSION))

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE feat.player_rating, feat.player_career_rating")
        cur.executemany(
            "INSERT INTO feat.player_rating (season, player_id, name, team, gp, minutes, ovr, z, off, def, qualified,"
            " baseline_season, detail, model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
        cur.executemany(
            "INSERT INTO feat.player_career_rating (player_id, peak, peak_from, peak_to, avg_ovr, career,"
            " off_career, off_peak, def_career, def_peak, seasons, qualified_seasons, model_version)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", careers)
    return {"seasons": len(tables), "season_ratings": len(rows), "careers": len(careers)}


BOX_COLS = {"gp": "GP", "min": "MIN", "pts": "PTS", "reb": "REB", "ast": "AST", "stl": "STL", "blk": "BLK",
            "fgm": "FGM", "fga": "FGA", "fg3m": "FG3M", "fg3a": "FG3A", "ftm": "FTM", "fta": "FTA"}


def store_box(conn: psycopg.Connection) -> int:
    """Copy every season's league-wide Base totals into feat.player_season_box."""
    rows = []
    for season, body in conn.execute(
            "SELECT params->>'season', body FROM raw.raw_response WHERE endpoint = 'LeagueDashPlayerStats'"
            " AND status = 'ok' AND params->>'measure_type_detailed_defense' = 'Base'"
            " AND params->>'per_mode_detailed' = 'Totals' AND params->>'season_type_all_star' = 'Regular Season'").fetchall():
        for r in result_rows(body):
            rows.append((season, r["PLAYER_ID"], r["PLAYER_NAME"], r["TEAM_ABBREVIATION"],
                         *(r.get(c) for c in BOX_COLS.values())))
    with conn.transaction():
        conn.execute("DELETE FROM feat.player_season_box")
        with conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO feat.player_season_box (season, player_id, name, team, {', '.join(BOX_COLS)})"
                f" VALUES ({', '.join(['%s'] * (4 + len(BOX_COLS)))})", rows)
    return len(rows)
