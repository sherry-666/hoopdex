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

from ballstats.collector import result_rows

MODEL_VERSION = "ovr-box-v1"
MIN_MINUTES = 500
MIN_QUALIFIED = 100         # below this many 500-minute players, borrow a prior season's baseline
WEIGHTS = {"contribution": 0.40, "scoring": 0.40, "on_court": 0.20}
USAGE_CREDIT = 0.3          # scoring credit per point of usage above league average
NET_SHRINK_MIN = 1000       # on-court net rating keeps minutes / (minutes + this) of its value
RELIABILITY_MIN = 250       # rating keeps minutes / (minutes + this) of its distance from replacement
REPLACEMENT_Z = -1.0
SCALE_MID, SCALE_SD = 77.0, 6.5
PEAK_WINDOW = 3
CAREER_PEAK_WEIGHT = 0.7


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
    t = pd.DataFrame({
        "name": base["PLAYER_NAME"], "team": base["TEAM_ABBREVIATION"], "gp": base["GP"], "minutes": base["MIN"],
        "pie": adv["PIE"], "ts": adv["TS_PCT"], "usg": adv["USG_PCT"], "net": adv["NET_RATING"],
    })
    return t.dropna(subset=["pie", "ts", "usg", "net", "minutes"])


def _components(t: pd.DataFrame, league_ts: float, league_usg: float) -> pd.DataFrame:
    return pd.DataFrame({
        "contribution": t["pie"],
        "scoring": (t["usg"] * (t["ts"] - league_ts) + USAGE_CREDIT * (t["usg"] - league_usg)) * 100,
        "on_court": t["net"] * t["minutes"] / (t["minutes"] + NET_SHRINK_MIN),
    }, index=t.index)


def season_ratings(t: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Rate every player of table t against the qualified players of baseline (t itself,
    or an earlier season while t is still early)."""
    ref = baseline[baseline["minutes"] >= MIN_MINUTES]
    league_ts = float(np.average(ref["ts"], weights=ref["minutes"]))
    league_usg = float(np.average(ref["usg"], weights=ref["minutes"]))
    ref_c = _components(ref, league_ts, league_usg)
    mean, sd = ref_c.mean(), ref_c.std()
    z = (_components(t, league_ts, league_usg) - mean) / sd
    combo = sum(z[k] * w for k, w in WEIGHTS.items())
    ref_combo = sum(((ref_c[k] - mean[k]) / sd[k]) * w for k, w in WEIGHTS.items())
    zc = (combo - ref_combo.mean()) / ref_combo.std()
    reliability = t["minutes"] / (t["minutes"] + RELIABILITY_MIN)
    z_adj = reliability * zc + (1 - reliability) * REPLACEMENT_Z
    out = t[["name", "team", "gp", "minutes"]].copy()
    out["ovr"] = np.clip(np.round(SCALE_MID + SCALE_SD * z_adj), 40, 99).astype(int)
    out["z"] = z_adj
    for k in WEIGHTS:
        out[f"z_{k}"] = z[k]
    out["reliability"] = reliability
    out["league_ts"] = league_ts
    return out


def compute(conn: psycopg.Connection) -> dict[str, int]:
    seasons = [r[0] for r in conn.execute(
        "SELECT DISTINCT params->>'season' FROM raw.raw_response WHERE endpoint = 'LeagueDashPlayerStats'"
        " AND status = 'ok' AND params->>'measure_type_detailed_defense' = 'Advanced'"
        " AND params->>'per_mode_detailed' = 'Totals' ORDER BY 1")]
    tables = {s: t for s in seasons if (t := _season_table(conn, s)) is not None}
    rows, last_complete = [], None
    for s in sorted(tables):
        t = tables[s]
        complete = (t["minutes"] >= MIN_MINUTES).sum() >= MIN_QUALIFIED
        if complete:
            last_complete = s
        base_season = s if complete or last_complete is None else last_complete
        r = season_ratings(t, tables[base_season])
        for pid, x in r.iterrows():
            rows.append((s, int(pid), x["name"], x["team"], int(x["gp"]), float(x["minutes"]), int(x["ovr"]),
                         round(float(x["z"]), 3), bool(x["minutes"] >= MIN_MINUTES), base_season,
                         Jsonb({"contribution": round(float(x["z_contribution"]), 2), "scoring": round(float(x["z_scoring"]), 2),
                                "on_court": round(float(x["z_on_court"]), 2), "reliability": round(float(x["reliability"]), 3),
                                "pie": round(float(t.at[pid, "pie"]), 4), "ts": round(float(t.at[pid, "ts"]), 4),
                                "usg": round(float(t.at[pid, "usg"]), 4), "net": round(float(t.at[pid, "net"]), 1),
                                "league_ts": round(float(x["league_ts"]), 4)}),
                         MODEL_VERSION))

    df = pd.DataFrame(rows, columns=["season", "player_id", "name", "team", "gp", "minutes", "ovr", "z",
                                     "qualified", "baseline_season", "detail", "model_version"])
    careers = []
    for pid, g in df.sort_values("season").groupby("player_id"):
        q = g[g["qualified"]]
        pool = q if len(q) else g
        ovrs = pool["ovr"].to_numpy(dtype=float)
        if len(ovrs) >= PEAK_WINDOW:
            means = np.convolve(ovrs, np.ones(PEAK_WINDOW) / PEAK_WINDOW, mode="valid")
            i = int(means.argmax())
            peak, frm, to = float(means[i]), pool["season"].iloc[i], pool["season"].iloc[i + PEAK_WINDOW - 1]
        else:
            peak, frm, to = float(ovrs.mean()), pool["season"].iloc[0], pool["season"].iloc[-1]
        avg = float(np.average(ovrs, weights=pool["minutes"]))
        career = CAREER_PEAK_WEIGHT * peak + (1 - CAREER_PEAK_WEIGHT) * avg
        careers.append((int(pid), round(peak, 1), frm, to, round(avg, 1), round(career, 1),
                        len(g), len(q), MODEL_VERSION))

    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE feat.player_rating, feat.player_career_rating")
        cur.executemany(
            "INSERT INTO feat.player_rating (season, player_id, name, team, gp, minutes, ovr, z, qualified,"
            " baseline_season, detail, model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", rows)
        cur.executemany(
            "INSERT INTO feat.player_career_rating (player_id, peak, peak_from, peak_to, avg_ovr, career,"
            " seasons, qualified_seasons, model_version) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", careers)
    return {"seasons": len(tables), "season_ratings": len(rows), "careers": len(careers)}
