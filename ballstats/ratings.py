"""Overall rating (OVR, out of 99) per player season, plus peak and career ratings.

Version 1 is a box-score estimate, available for every season since 1996-97 from
league-wide totals. It will be replaced by the impact model (RAPM + prior) once that
exists. Per season:

  1. Offense and defense ratings, each a weighted sum of z-scores against that season's players
     with 500+ minutes (components below), standardized again.
  2. OVR = 0.5 x offense + 0.3 x defense + 0.2 x PIE (the NBA's share-of-game-events estimate,
     which also carries fouls and turnovers), standardized once more. On-court results enter
     through both sides, about 20% of OVR in all.
  3. Each is pulled toward replacement level (-1.0) by sample size:
     weight = minutes / (minutes + 250).
  4. Rating = 77 + 6.5 x z, clipped to 40..99. A median 500-minute player lands near 75,
     +2 sd at 90, +3.4 sd at 99: roughly the NBA 2K spread.

  Offense: scoring (usage x (TS% - league TS%) + 0.3 x (load - league load), load = usage +
  0.5 x assist %), playmaking, offensive rebounding, on-court offense. Defense: steals, blocks,
  defensive rebounding, on-court defense, and from 2015-16 the opponents' FG% against him vs
  their norm and charges drawn.

Box-score estimates favour efficient rim-running bigs (rebounds and easy shots);
the RAPM-based version should correct most of that.

Recent-form adjustment (newest season only): the same box-score model is run on the last 30 days,
against the season's baseline, giving a recent z per scale. If it differs from the season rating's z
by more than FORM_DEADBAND sd, the rating moves by FORM_WEIGHT x evidence x the excess beyond the
deadband, up for a hot streak and down for a slump, at most FORM_CAP sd (about 5 points).
Evidence = recent minutes / (recent minutes + FORM_MIN), so it takes many minutes to move far; under
FORM_FLOOR_MIN minutes nothing moves. Peak and career ratings use the unadjusted values.

Peak = best average over three qualifying (500+ minute) seasons in a row.
Career = 0.7 x peak + 0.3 x the minutes-weighted average over qualifying seasons.
"""

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from ballstats import blend
from ballstats.collector import result_rows

MODEL_VERSION = "ovr-box-v4"
MIN_MINUTES = 500
MIN_QUALIFIED = 100         # below this many 500-minute players, borrow a prior season's baseline
OVR_WEIGHTS = {"offense": 0.50, "defense": 0.30, "contribution": 0.20}   # contribution: PIE, which also covers fouls and turnovers
OFF_WEIGHTS = {"scoring": 0.45, "playmaking": 0.25, "off_rebounding": 0.10, "on_court": 0.20}
DEF_WEIGHTS = {"steals": 0.20, "blocks": 0.15, "def_rebounding": 0.15, "on_court": 0.50}
# From 2015-16 on, tracking data adds how much worse opponents shoot against him than they normally do.
DEF_WEIGHTS_TRACKED = {"contest": 0.25, "steals": 0.15, "blocks": 0.10, "def_rebounding": 0.10, "on_court": 0.35,
                      "charges": 0.05}
SCALES = {"ovr": OVR_WEIGHTS, "off": OFF_WEIGHTS, "def": DEF_WEIGHTS_TRACKED}
CONTEST_SHRINK_FGA = 500    # the opponent-FG% edge keeps d_fga / (d_fga + this) of its value
USAGE_CREDIT = 0.3          # scoring credit per point of offensive load above league average
AST_LOAD = 0.5              # offensive load = usage + this x assist %: setting up teammates uses possessions too
TEAM_SHARE = 0.3            # on-court off/def: vs his own team, plus this share of the team's edge on the league
TOV_PENALTY = 0.5           # playmaking = assist % - this x turnover ratio
NET_SHRINK_MIN = 1000       # on-court net rating keeps minutes / (minutes + this) of its value
RELIABILITY_MIN = 250       # rating keeps minutes / (minutes + this) of its distance from replacement
REPLACEMENT_Z = -1.0
SCALE_MID, SCALE_SD = 77.0, 6.5
FORM_DEADBAND = 0.5         # recent vs season gap (sd) that counts as noise
FORM_WEIGHT = 0.8           # share of the gap beyond the deadband that moves the rating, at full evidence
FORM_MIN = 200              # evidence = recent minutes / (recent minutes + this)
FORM_FLOOR_MIN = 100        # fewer recent minutes than this: no adjustment
FORM_CAP = 0.8              # largest move, in sd (x SCALE_SD points)
PEAK_WINDOW = 3
CAREER_PEAK_WEIGHT = 0.7


def load_hustle(conn: psycopg.Connection, season: str) -> pd.DataFrame | None:
    row = conn.execute(
        "SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueHustleStatsPlayer' AND status = 'ok'"
        " AND params->>'season' = %s", (season,)).fetchone()
    return pd.DataFrame(result_rows(row[0])).set_index("PLAYER_ID") if row else None


def recent_window_start(conn: psycopg.Connection, season: str) -> str | None:
    """Start date of the newest stored recent-form window of the season, if any."""
    row = conn.execute(
        "SELECT params->>'date_from_nullable' FROM raw.raw_response WHERE endpoint = 'LeagueDashPlayerStats'"
        " AND status = 'ok' AND params->>'season' = %s AND params ? 'date_from_nullable'"
        " ORDER BY fetched_at DESC LIMIT 1", (season,)).fetchone()
    return row[0] if row else None


def _season_table(conn: psycopg.Connection, season: str, since: str | None = None) -> pd.DataFrame | None:
    """One season's player table; with `since`, the window from that date on (no tracking data then)."""
    def load(measure: str) -> pd.DataFrame | None:
        row = conn.execute(
            "SELECT body FROM raw.raw_response WHERE endpoint = 'LeagueDashPlayerStats' AND status = 'ok'"
            " AND params->>'season' = %s AND params->>'measure_type_detailed_defense' = %s"
            " AND params->>'per_mode_detailed' = 'Totals' AND coalesce(params->>'date_from_nullable', '') = %s",
            (season, measure, since or "")).fetchone()
        return pd.DataFrame(result_rows(row[0])).set_index("PLAYER_ID") if row else None

    base, adv = load("Base"), load("Advanced")
    if base is None or adv is None or base.empty:
        return None
    hustle = None if since else load_hustle(conn, season)
    dfd = None if since else conn.execute(
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


def _scoring(t: pd.DataFrame, lg: dict[str, float]) -> pd.Series:
    """Efficiency on volume, plus credit for offensive load (usage and the possessions he spends on assists)."""
    load, lg_load = t["usg"] + AST_LOAD * t["ast_pct"], lg["usg"] + AST_LOAD * lg["ast_pct"]
    return (t["usg"] * (t["ts"] - lg["ts"]) + USAGE_CREDIT * (load - lg_load)) * 100


def _components(t: pd.DataFrame, lg: dict[str, float]) -> dict[str, pd.DataFrame]:
    """Raw component values per scale; lg holds league averages of the baseline season."""
    m = t["minutes"]
    return {
        "ovr": pd.DataFrame({"contribution": t["pie"]}),
        "off": pd.DataFrame({
            "scoring": _scoring(t, lg),
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
    lg = {k: float(np.average(ref[k], weights=ref["minutes"])) for k in ("ts", "usg", "ortg", "drtg", "ast_pct")}
    ref_c, mine = _components(ref, lg), _components(t, lg)
    reliability = t["minutes"] / (t["minutes"] + RELIABILITY_MIN)
    out = t[["name", "team", "gp", "minutes"]].copy()
    tracked = bool(t["d_fga"].notna().any() and ref["d_fga"].notna().any())
    zc_mine, zc_ref = {}, {}
    for scale in ("off", "def", "ovr"):
        weights = DEF_WEIGHTS if scale == "def" and not tracked else SCALES[scale]
        mean, sd = ref_c[scale].mean(), ref_c[scale].std()
        z = (mine[scale] - mean) / sd
        if scale == "ovr":
            # Overall: offense, defense and PIE (the catch-all for fouls, turnovers and the like), each as a z-score.
            z = z.assign(offense=zc_mine["off"], defense=zc_mine["def"])
            ref_z = ((ref_c[scale] - mean) / sd).assign(offense=zc_ref["off"], defense=zc_ref["def"])
            ref_combo = sum(ref_z[k] * w for k, w in weights.items())
        else:
            ref_combo = sum(((ref_c[scale][k] - mean[k]) / sd[k]) * w for k, w in weights.items())
        zc = (sum(z[k] * w for k, w in weights.items()) - ref_combo.mean()) / ref_combo.std()
        zc_mine[scale], zc_ref[scale] = zc, (ref_combo - ref_combo.mean()) / ref_combo.std()
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


def form_adjustment(r: pd.DataFrame, recent: pd.DataFrame) -> pd.DataFrame:
    """Per player in both tables: the recent-form move of each scale, in sd, plus the recent minutes and evidence.
    r holds the season's ratings, recent the same model run on the last 30 days."""
    idx = r.index.intersection(recent.index)
    minutes = recent.loc[idx, "minutes"]
    evidence = (minutes / (minutes + FORM_MIN)).where(minutes >= FORM_FLOOR_MIN, 0.0)
    out = pd.DataFrame({"recent_minutes": minutes, "recent_gp": recent.loc[idx, "gp"], "evidence": evidence})
    for scale in SCALES:
        gap = recent.loc[idx, f"zc_{scale}"] - r.loc[idx, f"z_{scale}"]
        excess = np.sign(gap) * (gap.abs() - FORM_DEADBAND).clip(lower=0)
        out[scale] = (FORM_WEIGHT * evidence * excess).clip(-FORM_CAP, FORM_CAP)
        out[f"recent_{scale}"] = np.clip(np.round(SCALE_MID + SCALE_SD * recent.loc[idx, f"zc_{scale}"]), 40, 99).astype(int)
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
        " AND NOT params ? 'date_from_nullable'"
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
        form = since = None
        if s == newest and (since := recent_window_start(conn, s)) and (rec := _season_table(conn, s, since)) is not None:
            form = form_adjustment(r, season_ratings(rec, tables[base_season]))
            r = r.copy()    # hist keeps the unadjusted ratings
            for scale in SCALES:
                r[f"base_{scale}"] = r[scale]
                z = r[f"z_{scale}"].add(form[scale], fill_value=0.0)
                r[f"z_{scale}"] = z
                r[scale] = np.clip(np.round(SCALE_MID + SCALE_SD * z), 40, 99).astype(int)
        for pid, x in r.iterrows():
            raw = t.loc[pid]
            detail = {
                "contribution": x["ovr.contribution"], "offense": x["ovr.offense"], "defense": x["ovr.defense"],
                "reliability": x["reliability"], "pie": raw["pie"], "ts": raw["ts"], "usg": raw["usg"],
                "net": raw["net"], "league_ts": x["league_ts"],
                "off": {**{k: x[f"off.{k}"] for k in OFF_WEIGHTS}, "ortg": raw["ortg"], "league_ortg": x["league_ortg"],
                        "ast_pct": raw["ast_pct"], "tov_pct": raw["tov_pct"], "oreb_pct": raw["oreb_pct"]},
                "def": {**{k: x[f"def.{k}"] for k in (DEF_WEIGHTS_TRACKED if x["tracked"] else DEF_WEIGHTS)},
                        "drtg": raw["drtg"], "league_drtg": x["league_drtg"],
                        "stl_36": raw["stl_36"], "blk_36": raw["blk_36"], "dreb_pct": raw["dreb_pct"],
                        **({"d_fga": raw["d_fga"], "d_pm": raw["d_pm"], "charges_36": raw["charges_36"]} if x["tracked"] else {})},
            }
            if form is not None and pid in form.index and form.loc[pid, "evidence"] > 0:
                f = form.loc[pid]
                detail["form"] = {"minutes": f["recent_minutes"], "gp": f["recent_gp"],
                                  "evidence": f["evidence"],
                                  **{f"recent_{k}": int(f[f"recent_{k}"]) for k in SCALES},
                                  **{f"adj_{k}": f[k] * SCALE_SD for k in SCALES},
                                  **{f"base_{k}": int(x[f"base_{k}"]) for k in SCALES}}
            if pd.notna(x.get("blend_weight", np.nan)):
                detail["blend"] = {"weight": x["blend_weight"], **{f"own_{k}": x[f"own_{k}"] for k in SCALES},
                                   **{f"prior_{k}": x[f"prior_{k}"] for k in SCALES}}
                detail_prior = prior_labels[pid]
            else:
                detail_prior = None
            rows.append((s, int(pid), x["name"], x["team"], int(x["gp"]), float(x["minutes"]), int(x["ovr"]),
                         round(float(x["z_ovr"]), 3), int(x["off"]), int(x["def"]),
                         bool(x["minutes"] >= MIN_MINUTES), base_season,
                         Jsonb({**_rounded(detail), **({"blend_prior": detail_prior} if detail_prior else {}),
                               **({"form_from": since} if "form" in detail else {})}), MODEL_VERSION,
                         int(x.get("base_ovr", x["ovr"])), int(x.get("base_off", x["off"])), int(x.get("base_def", x["def"]))))

    df = pd.DataFrame(rows, columns=["season", "player_id", "name", "team", "gp", "minutes", "ovr", "z", "off", "def",
                                     "qualified", "baseline_season", "detail", "model_version",
                                     "ovr_base", "off_base", "def_base"])
    careers = []
    for pid, g in df.sort_values("season").groupby("player_id"):
        q = g[g["qualified"]]
        pool = q if len(q) else g
        peak, frm, to, avg, career = _career(pool, "ovr_base")     # careers ignore the recent-form adjustment
        off, de = _career(pool, "off_base"), _career(pool, "def_base")
        careers.append((int(pid), peak, frm, to, avg, career, off[4], off[0], de[4], de[0],
                        len(g), len(q), MODEL_VERSION))

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE feat.player_rating, feat.player_career_rating")
        cur.executemany(
            "INSERT INTO feat.player_rating (season, player_id, name, team, gp, minutes, ovr, z, off, def, qualified,"
            " baseline_season, detail, model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [r[:14] for r in rows])
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
            " AND NOT params ? 'date_from_nullable'"
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
