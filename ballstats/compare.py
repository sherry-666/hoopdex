"""Side-by-side facts about the two teams of a game, shown next to the prediction (not part of it).

  body     minutes-weighted height and age of the rotation (the NUM_ROTATION players with the most minutes among
           those who can play on the game day), plus who of the usual rotation is missing.
  splits   points scored / allowed per 100 possessions in the venue this game is played at: the home team's home
           games, the away team's road games, from the box scores before the game day. Possessions are estimated as
           FGA + 0.44 FTA - OREB + TOV, averaged over the two teams of each game.
"""

import datetime as dt

import psycopg
from psycopg.rows import dict_row, tuple_row

from ballstats import blend, predict, teams

CM_PER_INCH = 2.54


def _availability(conn: psycopg.Connection, away: str, home: str, day: dt.date) -> dict[int, float]:
    """Who can play on the day: the stored snapshot's injury list when the game has one (a finished game keeps what was
    known before it), else today's injury report."""
    snap = conn.execute("SELECT injuries FROM live.prediction_snapshot WHERE home = %s AND away = %s AND game_date = %s",
                        (home, away, day)).fetchone()
    if snap:
        return {int(i["player_id"]): float(i["available"]) for i in snap["injuries"]}
    return {r["player_id"]: predict.can_play(r["status"], r["return_date"], day) for r in conn.execute(
        "SELECT DISTINCT ON (player_id) player_id, status, return_date FROM live.injury WHERE player_id IS NOT NULL"
        " ORDER BY player_id, reported_at DESC NULLS LAST")}


def _body(conn: psycopg.Connection, season: str, team: str, avail: dict[int, float]) -> dict:
    rows = conn.execute(
        "SELECT s.player_id, s.name, s.minutes, (s.stats ->> 'height_cm')::float AS height_cm,"
        " (SELECT p.age FROM core.player_season p WHERE p.player_id = s.player_id AND p.season = s.season"
        "  AND p.season_type = 'regular' ORDER BY (p.team = s.team) DESC, (p.team = 'TOT') DESC LIMIT 1) AS age"
        " FROM feat.player_stats s WHERE s.season = %s AND s.team = %s AND s.minutes > 0 ORDER BY s.minutes DESC",
        (season, team)).fetchall()

    def mean(group: list[dict], key: str) -> float | None:
        have = [r for r in group if r[key] is not None]
        w = sum(r["minutes"] for r in have)
        return round(sum(r[key] * r["minutes"] for r in have) / w, 1) if w else None

    usual = rows[:teams.NUM_ROTATION]
    able = [r for r in rows if avail.get(r["player_id"], 1.0) > 0][:teams.NUM_ROTATION]
    return {
        "height_cm": mean(able, "height_cm"), "age": mean(able, "age"),
        "height_cm_healthy": mean(usual, "height_cm"), "age_healthy": mean(usual, "age"),
        "missing": [r["name"] for r in usual if avail.get(r["player_id"], 1.0) <= 0],
    }


def _splits(conn: psycopg.Connection, season: str, team: str, day: dt.date) -> dict:
    """The team's home and road games before `day`: games, points scored / allowed and pace per 100 possessions."""
    rows = conn.execute(
        """
        WITH tg AS (
            SELECT game_id, team, opp, home, max(team_score) AS pts, max(opp_score) AS opp_pts,
                   sum(coalesce(fga, 0) + 0.44 * coalesce(fta, 0) - coalesce(oreb, 0) + coalesce(tov, 0)) AS poss
            FROM live.player_game
            WHERE season = %(season)s AND season_type = 2 AND dnp_reason IS NULL AND game_date < %(day)s
              AND game_id IN (SELECT game_id FROM live.player_game WHERE team = %(team)s AND season = %(season)s)
            GROUP BY game_id, team, opp, home)
        SELECT a.home, count(*) AS games, sum(a.pts) AS pts, sum(a.opp_pts) AS opp_pts, sum((a.poss + b.poss) / 2) AS poss
        FROM tg a JOIN tg b ON a.game_id = b.game_id AND a.team = b.opp
        WHERE a.team = %(team)s GROUP BY a.home
        """, {"season": season, "day": day, "team": team}).fetchall()
    out = {}
    for r in rows:
        poss = float(r["poss"])
        out["home" if r["home"] else "road"] = {
            "games": r["games"], "ppg": round(r["pts"] / r["games"], 1), "opp_ppg": round(r["opp_pts"] / r["games"], 1),
            "ortg": round(100 * r["pts"] / poss, 1), "drtg": round(100 * r["opp_pts"] / poss, 1),
            "pace": round(poss / r["games"], 1)}
    return out


def compare(conn: psycopg.Connection, away: str, home: str, day: dt.date) -> dict:
    saved, conn.row_factory = conn.row_factory, tuple_row
    try:
        season = blend.ongoing_season(conn) or conn.execute("SELECT max(season) FROM feat.team_profile").fetchone()[0]
        conn.row_factory = dict_row
        avail = _availability(conn, away, home, day)
        return {"date": day.isoformat(), "season": season,
                "body": {t: _body(conn, season, t, avail) for t in (away, home)},
                "splits": {t: _splits(conn, season, t, day) for t in (away, home)}}
    finally:
        conn.row_factory = saved
