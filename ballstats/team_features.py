"""How a team runs its offense, from team-level data (2015-16 on).

One row per team season, from four sources collected by `collect --groups teams`:
  Synergy play types        share of possessions in each play type
  tracking dashboards       passes, drives and touches per 100 possessions; seconds and
                            dribbles per touch; catch-and-shoot vs pull-up share of shots
  team stats (Advanced,     pace, assisted share of baskets, fast-break / paint / midrange
  Scoring)                  share of points
  shot locations            share of shots at the rim, in the paint, midrange, corner 3,
                            above-the-break 3

The league drifts year to year (far more threes than in 2015), so callers standardize
within each season: a team's style is relative to its own league.
"""

import pandas as pd
import psycopg

from ballstats.catalog import PLAY_TYPES
from ballstats.collector import result_rows

PLAY_TYPE_FEATURES = [pt for pt in PLAY_TYPES if pt != "Misc"]
# Shot-location zones in the order stats.nba.com returns them (FGM, FGA, FG% each).
ZONES = ["rim", "paint", "mid", "left_corner3", "right_corner3", "above_break3", "backcourt", "corner3"]

FEATURE_LABELS = {
    **{f"pt_{pt}": label for pt, label in zip(PLAY_TYPE_FEATURES, [
        "转换进攻", "单打", "挡拆持球", "挡拆顺下", "背身", "定点投篮", "手递手", "空切", "绕掩护", "二次进攻"])},
    "passes_100": "传球 / 百回合", "drives_100": "突破 / 百回合", "sec_per_touch": "每次触球秒数",
    "drib_per_touch": "每次触球运球", "elbow_100": "肘区触球 / 百回合", "post_100": "低位触球 / 百回合",
    "paint_100": "禁区触球 / 百回合", "cs_share": "接球投篮占比", "pullup_share": "急停跳投占比",
    "pace": "节奏", "ast_fgm": "助攻得分占比", "fb_pts": "快攻得分占比", "paint_pts": "禁区得分占比",
    "mid_pts": "中距离得分占比", "fg3a_rate": "三分出手占比",
    "rim_share": "篮下出手占比", "paint_share": "禁区非篮下出手", "mid_share": "中距离出手占比",
    "corner3_share": "底角三分出手", "atb3_share": "弧顶三分出手",
}


def _rows(conn, endpoint: str, where: str, args: tuple = ()) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = {}
    for params, body in conn.execute(
            f"SELECT params, body FROM raw.raw_response WHERE endpoint = %s AND status = 'ok' AND {where}",
            (endpoint, *args)):
        tag = params.get("play_type_nullable") or params.get("pt_measure_type") or params.get("measure_type_detailed_defense") or ""
        out[(params["season"], tag)] = result_rows(body)
    return out


def build(conn: psycopg.Connection) -> pd.DataFrame:
    """Raw (unstandardized) features, indexed by (season, team abbreviation)."""
    synergy = _rows(conn, "SynergyPlayTypes", "params->>'player_or_team_abbreviation' = 'T'"
                    " AND params->>'type_grouping_nullable' = 'offensive'")
    tracking = _rows(conn, "LeagueDashPtStats", "params->>'player_or_team' = 'Team'")
    stats = _rows(conn, "LeagueDashTeamStats", "true")
    shots = {params["season"]: body["resultSets"]["rowSet"] for params, body in conn.execute(
        "SELECT params, body FROM raw.raw_response WHERE endpoint = 'LeagueDashTeamShotLocations' AND status = 'ok'")}

    seasons = sorted({s for s, _ in synergy})
    frames = []
    for season in seasons:
        if not all((season, pt) in synergy for pt in PLAY_TYPE_FEATURES):
            continue
        abbr = {r["TEAM_ID"]: r["TEAM_ABBREVIATION"] for r in synergy[(season, "Transition")]}
        f = pd.DataFrame(index=sorted(abbr))
        play = pd.DataFrame({pt: pd.Series({r["TEAM_ID"]: r["POSS"] for r in synergy[(season, pt)]})
                             for pt in PLAY_TYPE_FEATURES}).reindex(f.index).fillna(0)
        play = play.div(play.sum(axis=1), axis=0)          # shares of play-typed possessions
        for pt in PLAY_TYPE_FEATURES:
            f[f"pt_{pt}"] = play[pt]

        def by_id(rows: list[dict]) -> pd.DataFrame:
            return pd.DataFrame(rows).set_index("TEAM_ID").reindex(f.index)

        adv = by_id(stats.get((season, "Advanced"), []))
        base = by_id(stats.get((season, "Base"), []))
        scoring = by_id(stats.get((season, "Scoring"), []))
        poss = adv["POSS"]
        t = {m: by_id(tracking[(season, m)]) for m in ("Passing", "Drives", "Possessions", "CatchShoot", "PullUpShot")
             if (season, m) in tracking}
        if len(t) < 5:
            continue
        f["passes_100"] = t["Passing"]["PASSES_MADE"] / poss * 100
        f["drives_100"] = t["Drives"]["DRIVES"] / poss * 100
        f["sec_per_touch"] = t["Possessions"]["AVG_SEC_PER_TOUCH"]
        f["drib_per_touch"] = t["Possessions"]["AVG_DRIB_PER_TOUCH"]
        f["elbow_100"] = t["Possessions"]["ELBOW_TOUCHES"] / poss * 100
        f["post_100"] = t["Possessions"]["POST_TOUCHES"] / poss * 100
        f["paint_100"] = t["Possessions"]["PAINT_TOUCHES"] / poss * 100
        f["cs_share"] = t["CatchShoot"]["CATCH_SHOOT_FGA"] / base["FGA"]
        f["pullup_share"] = t["PullUpShot"]["PULL_UP_FGA"] / base["FGA"]
        f["gp"] = adv["GP"]
        f["pace"] = adv["PACE"]
        f["ast_fgm"] = scoring["PCT_AST_FGM"]
        f["fb_pts"] = scoring["PCT_PTS_FB"]
        f["paint_pts"] = scoring["PCT_PTS_PAINT"]
        f["mid_pts"] = scoring["PCT_PTS_2PT_MR"]
        f["fg3a_rate"] = scoring["PCT_FGA_3PT"]
        if season in shots:
            fga = pd.DataFrame({row[0]: {z: row[3 + 3 * i] for i, z in enumerate(ZONES)} for row in shots[season]}).T
            fga = fga.reindex(f.index)
            total = fga[["rim", "paint", "mid", "left_corner3", "right_corner3", "above_break3"]].sum(axis=1)
            f["rim_share"] = fga["rim"] / total
            f["paint_share"] = fga["paint"] / total
            f["mid_share"] = fga["mid"] / total
            f["corner3_share"] = (fga["left_corner3"] + fga["right_corner3"]) / total
            f["atb3_share"] = fga["above_break3"] / total
        f.index = pd.MultiIndex.from_tuples([(season, abbr[i]) for i in f.index], names=["season", "team"])
        frames.append(f)
    return pd.concat(frames).astype(float) if frames else pd.DataFrame()


FEATURES = list(FEATURE_LABELS)


def standardize(f: pd.DataFrame) -> pd.DataFrame:
    """z-scores of the style features within each season."""
    cols = [c for c in FEATURES if c in f.columns]
    return f[cols].groupby(level="season").transform(lambda v: (v - v.mean()) / v.std())
