"""Style features for role clustering, built from raw season aggregates.

Only "what a player does" goes in here (shot mix, play-type frequency, touch
profile, who-they-guard proxies), never "how well" (percentages), so that an
inefficient ball handler still clusters with ball handlers.
"""

import numpy as np
import pandas as pd
import psycopg

from ballstats.collector import result_rows

PER36 = 36.0
SYNERGY_PSEUDO_POSS = 50.0


def _load(conn: psycopg.Connection, endpoint: str, season: str, set_name=None, **params) -> pd.DataFrame:
    sql = ("SELECT body FROM raw.raw_response WHERE endpoint = %s AND status = 'ok'"
           " AND coalesce(params->>'season', params->>'season_nullable') = %s")
    args = [endpoint, season]
    for key, value in params.items():
        sql += f" AND params->>'{key}' = %s"
        args.append(value)
    row = conn.execute(sql, args).fetchone()
    if row is None:
        raise LookupError(f"no raw data for {endpoint} {season} {params}")
    return pd.DataFrame(result_rows(row[0], set_name))


def _per36(count: pd.Series, minutes: pd.Series) -> pd.Series:
    return count / minutes.where(minutes > 0) * PER36


def _shot_zones(conn, season: str) -> pd.DataFrame:
    shots = _load(conn, "ShotChartDetail", season, "Shot_Chart_Detail")
    dist = np.hypot(shots["LOC_X"], shots["LOC_Y"]) / 10.0
    three = shots["SHOT_TYPE"].str.startswith("3")
    corner = shots["SHOT_ZONE_BASIC"].str.contains("Corner")
    zone = np.select(
        [~three & (dist <= 4), ~three & (dist < 14), ~three,
         three & corner, three & (dist < 28), three & (dist <= 36)],
        ["rim", "short_mid", "long_mid", "corner3", "atb3", "deep3"],
        default="heave",
    )
    counts = pd.crosstab(shots["PLAYER_ID"], zone).drop(columns="heave", errors="ignore")
    shares = counts.div(counts.sum(axis=1), axis=0).add_prefix("shot_")
    return shares


def _synergy(conn, season: str, side: str) -> pd.DataFrame:
    frames = []
    rows = conn.execute(
        "SELECT params->>'play_type_nullable', body FROM raw.raw_response"
        " WHERE endpoint = 'SynergyPlayTypes' AND status = 'ok'"
        " AND params->>'season' = %s AND params->>'type_grouping_nullable' = %s",
        (season, side),
    ).fetchall()
    for play_type, body in rows:
        df = pd.DataFrame(result_rows(body))
        if df.empty:
            continue
        # A traded player has one row per team; weight by possessions.
        poss = df.groupby("PLAYER_ID")["POSS"].sum().rename(play_type)
        frames.append(poss)
    if not frames:
        return pd.DataFrame()
    poss = pd.concat(frames, axis=1).fillna(0)
    poss = poss.drop(columns="Misc", errors="ignore")
    # Shrink toward the league mix: a player with 20 tracked possessions
    # should not get a 40% post-up share from 8 of them.
    league = poss.sum() / poss.values.sum()
    shares = (poss + SYNERGY_PSEUDO_POSS * league).div(poss.sum(axis=1) + SYNERGY_PSEUDO_POSS, axis=0)
    prefix = "off_pt_" if side == "offensive" else "def_pt_"
    return shares.add_prefix(prefix)


def build(conn: psycopg.Connection, season: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (info, offense, defense), all indexed by PLAYER_ID."""
    base = _load(conn, "LeagueDashPlayerStats", season, measure_type_detailed_defense="Base").set_index("PLAYER_ID")
    adv = _load(conn, "LeagueDashPlayerStats", season, measure_type_detailed_defense="Advanced").set_index("PLAYER_ID")
    scoring = _load(conn, "LeagueDashPlayerStats", season, measure_type_detailed_defense="Scoring").set_index("PLAYER_ID")
    bio = _load(conn, "LeagueDashPlayerBioStats", season).set_index("PLAYER_ID")
    hustle = _load(conn, "LeagueHustleStatsPlayer", season).set_index("PLAYER_ID")
    pt = {m: _load(conn, "LeagueDashPtStats", season, pt_measure_type=m).set_index("PLAYER_ID")
          for m in ["Possessions", "Drives", "CatchShoot", "PullUpShot", "Defense", "SpeedDistance"]}
    dfd = {c: _load(conn, "LeagueDashPtDefend", season, defense_category=c).set_index("CLOSE_DEF_PERSON_ID")
           for c in ["Overall", "3 Pointers", "Less Than 6Ft"]}

    minutes = base["MIN"]
    info = pd.DataFrame({
        "name": base["PLAYER_NAME"], "team": base["TEAM_ABBREVIATION"], "gp": base["GP"],
        "min": minutes, "height_in": bio["PLAYER_HEIGHT_INCHES"].reindex(base.index),
        # Outcome stats: shown next to roles, never used for clustering.
        "pts_36": _per36(base["PTS"], minutes), "reb_36": _per36(base["REB"], minutes),
        "ast_36": _per36(base["AST"], minutes), "fg3a_36": _per36(base["FG3A"], minutes),
        "ts_pct": adv["TS_PCT"], "fg3_pct": base["FG3_PCT"],
    })

    touches = pt["Possessions"]["TOUCHES"].reindex(base.index)
    fga = base["FGA"].where(base["FGA"] > 0)
    off = pd.DataFrame(index=base.index)
    off = off.join(_shot_zones(conn, season))
    off["fta_rate"] = base["FTA"] / fga
    off["usg_pct"] = adv["USG_PCT"]
    off["ast_pct"] = adv["AST_PCT"]
    off["uast_fgm_pct"] = scoring["PCT_UAST_FGM"]
    off["oreb_pct"] = adv["OREB_PCT"]
    off["drives_36"] = _per36(pt["Drives"]["DRIVES"], minutes)
    off["touches_36"] = _per36(touches, minutes)
    off["sec_per_touch"] = pt["Possessions"]["AVG_SEC_PER_TOUCH"]
    off["drib_per_touch"] = pt["Possessions"]["AVG_DRIB_PER_TOUCH"]
    off["elbow_touch_share"] = pt["Possessions"]["ELBOW_TOUCHES"] / touches.where(touches > 0)
    off["post_touch_share"] = pt["Possessions"]["POST_TOUCHES"] / touches.where(touches > 0)
    off["paint_touch_share"] = pt["Possessions"]["PAINT_TOUCHES"] / touches.where(touches > 0)
    off["cs_fga_share"] = pt["CatchShoot"]["CATCH_SHOOT_FGA"] / fga
    off["pullup_fga_share"] = pt["PullUpShot"]["PULL_UP_FGA"] / fga
    off["screen_ast_36"] = _per36(hustle["SCREEN_ASSISTS"], minutes)
    off["height_in"] = info["height_in"]
    off = off.join(_synergy(conn, season, "offensive"))

    d_fga = dfd["Overall"]["D_FGA"]
    de = pd.DataFrame(index=base.index)
    de["height_in"] = info["height_in"]
    de["weight_lb"] = pd.to_numeric(bio["PLAYER_WEIGHT"], errors="coerce").reindex(base.index)
    de["blk_36"] = _per36(base["BLK"], minutes)
    de["stl_36"] = _per36(base["STL"], minutes)
    de["dreb_pct"] = adv["DREB_PCT"]
    de["rim_dfga_36"] = _per36(pt["Defense"]["DEF_RIM_FGA"], minutes)
    de["deflections_36"] = _per36(hustle["DEFLECTIONS"], minutes)
    de["charges_36"] = _per36(hustle["CHARGES_DRAWN"], minutes)
    contests = hustle["CONTESTED_SHOTS"].where(hustle["CONTESTED_SHOTS"] > 0)
    de["contest3_share"] = hustle["CONTESTED_SHOTS_3PT"] / contests
    de["contests_36"] = _per36(hustle["CONTESTED_SHOTS"], minutes)
    de["dfga3_share"] = dfd["3 Pointers"]["FG3A"] / d_fga.where(d_fga > 0)
    de["dfga_lt6_share"] = dfd["Less Than 6Ft"]["FGA_LT_06"] / d_fga.where(d_fga > 0)
    de["speed_def"] = pt["SpeedDistance"]["AVG_SPEED_DEF"]
    de = de.join(_synergy(conn, season, "defensive"))
    return info, off, de
