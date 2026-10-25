"""Parse raw responses into the core layer.

So far: player identity, season-by-season box-score totals and career totals,
from PlayerCareerStats (one raw row per player).
"""

import logging

import psycopg

from ballstats.collector import result_rows

log = logging.getLogger(__name__)

STATS = ["gp", "gs", "min", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
         "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf", "pts"]
SEASON_SETS = {"regular": "SeasonTotalsRegularSeason", "playoffs": "SeasonTotalsPostSeason"}
CAREER_SETS = {"regular": "CareerTotalsRegularSeason", "playoffs": "CareerTotalsPostSeason"}


def _num(v):
    return None if v is None or v == "" else v


def _names(conn: psycopg.Connection) -> dict[int, str]:
    """Best available display name per player: league player lists, then feat stats."""
    names: dict[int, str] = {}
    for (body,) in conn.execute("SELECT body FROM raw.raw_response WHERE endpoint = 'CommonAllPlayers' AND status = 'ok'"):
        for r in result_rows(body):
            names[r["PERSON_ID"]] = r["DISPLAY_FIRST_LAST"]
    for pid, name in conn.execute("SELECT DISTINCT ON (player_id) player_id, name FROM feat.player_stats ORDER BY player_id, season DESC"):
        names.setdefault(pid, name)
    return names


def parse_careers(conn: psycopg.Connection) -> dict[str, int]:
    names = _names(conn)
    seasons, careers, players = [], [], []
    for pid, body in conn.execute("SELECT (params->>'player_id')::bigint, body FROM raw.raw_response"
                                  " WHERE endpoint = 'PlayerCareerStats' AND status = 'ok'"):
        regular_seasons = []
        for stype, set_name in SEASON_SETS.items():
            for r in result_rows(body, set_name):
                seasons.append((pid, r["SEASON_ID"], stype, r["TEAM_ABBREVIATION"] or "TOT", _num(r["TEAM_ID"]),
                                int(r["PLAYER_AGE"]) if r["PLAYER_AGE"] else None,
                                *(_num(r[s.upper()]) for s in STATS)))
                if stype == "regular":
                    regular_seasons.append(r["SEASON_ID"])
        for stype, set_name in CAREER_SETS.items():
            for r in result_rows(body, set_name):
                careers.append((pid, stype, *(_num(r[s.upper()]) for s in STATS)))
        if pid in names:
            players.append((pid, names[pid], min(regular_seasons, default=None), max(regular_seasons, default=None)))
        else:
            log.warning("no name for player %s", pid)

    cols = ", ".join(STATS)
    marks = ", ".join(["%s"] * len(STATS))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("TRUNCATE core.player_season, core.player_career")
        cur.executemany(
            f"INSERT INTO core.player_season (player_id, season, season_type, team, team_id, age, {cols})"
            f" VALUES (%s, %s, %s, %s, %s, %s, {marks}) ON CONFLICT DO NOTHING", seasons)
        cur.executemany(
            f"INSERT INTO core.player_career (player_id, season_type, {cols}) VALUES (%s, %s, {marks})", careers)
        cur.executemany(
            "INSERT INTO core.player (player_id, name, first_season, last_season, updated_at)"
            " VALUES (%s, %s, %s, %s, now()) ON CONFLICT (player_id) DO UPDATE SET name = EXCLUDED.name,"
            " first_season = EXCLUDED.first_season, last_season = EXCLUDED.last_season, updated_at = now()", players)
    return {"players": len(players), "season_rows": len(seasons), "career_rows": len(careers)}
