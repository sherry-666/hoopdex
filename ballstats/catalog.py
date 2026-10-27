"""Which requests make up one season's collection.

Three groups:
  season  - league-wide aggregates, a few calls each; refetched when stale
  games   - per-game box scores and play-by-play; fetched once per finished game
  players - per-player tracking dashboards; refetched when stale
"""

from dataclasses import dataclass

from nba_api.stats.static import teams

SEASON_MAX_AGE_H = 20.0  # aggregates change nightly
# League-wide box / advanced totals (what ratings and per-36 come from): one request each, so
# refetched often enough that a finished game shows up within hours.
TOTALS_MAX_AGE_H = 3.0

PLAYER_STATS_MEASURES = ["Base", "Advanced", "Misc", "Scoring", "Usage", "Defense"]
PT_MEASURES = [
    "SpeedDistance", "Rebounding", "Possessions", "CatchShoot", "PullUpShot",
    "Defense", "Drives", "Passing", "ElbowTouch", "PostTouch", "PaintTouch",
    "Efficiency",
]
PLAY_TYPES = [
    "Transition", "Isolation", "PRBallHandler", "PRRollman", "Postup", "Spotup",
    "Handoff", "Cut", "OffScreen", "OffRebound", "Misc",
]
DEFENSE_CATEGORIES = [
    "Overall", "3 Pointers", "2 Pointers", "Less Than 6Ft", "Less Than 10Ft",
    "Greater Than 15Ft",
]
# Bucket labels as stats.nba.com spells them on its shot dashboards.
PT_SHOT_BUCKETS = {
    "close_def_dist_range_nullable": [
        "0-2 Feet - Very Tight", "2-4 Feet - Tight", "4-6 Feet - Open",
        "6+ Feet - Wide Open",
    ],
    "dribble_range_nullable": [
        "0 Dribbles", "1 Dribble", "2 Dribbles", "3-6 Dribbles", "7+ Dribbles",
    ],
    "touch_time_range_nullable": [
        "Touch < 2 Seconds", "Touch 2-6 Seconds", "Touch 6+ Seconds",
    ],
    "shot_clock_range_nullable": [
        "24-22", "22-18 Very Early", "18-15 Early", "15-7 Average", "7-4 Late",
        "4-0 Very Late",
    ],
    "general_range_nullable": ["Catch and Shoot", "Pullups", "Less Than 10 ft"],
}
GAME_ENDPOINTS = [
    "PlayByPlayV3", "BoxScoreTraditionalV3", "BoxScoreAdvancedV3",
    "BoxScoreMiscV3", "BoxScoreScoringV3", "BoxScoreMatchupsV3", "BoxScoreHustleV2",
]


@dataclass(frozen=True)
class Job:
    endpoint: str
    params: dict
    max_age_h: float | None = SEASON_MAX_AGE_H


def game_finder_job(season: str, season_type: str) -> Job:
    return Job("LeagueGameFinder", {
        "player_or_team_abbreviation": "T", "league_id_nullable": "00",
        "season_nullable": season, "season_type_nullable": season_type,
    }, max_age_h=2.0)


def season_jobs(season: str, season_type: str) -> list[Job]:
    common = {"season": season, "season_type_all_star": season_type}
    jobs = [
        Job("CommonAllPlayers", {"season": season, "league_id": "00",
                                 "is_only_current_season": 1}),
        Job("LeagueDashPlayerBioStats", {**common, "league_id": "00",
                                         "per_mode_simple": "Totals"}),
        Job("LeagueHustleStatsPlayer", {**common, "per_mode_time": "Totals"}),
        # PlayerID=0/TeamID=0 returns every shot in the league for the season.
        Job("ShotChartDetail", {"team_id": 0, "player_id": 0,
                                "context_measure_simple": "FGA",
                                "season_nullable": season,
                                "season_type_all_star": season_type}),
        Job("LeagueDashPlayerShotLocations", {**common, "distance_range": "By Zone",
                                              "per_mode_detailed": "Totals"}),
    ]
    jobs += [Job("LeagueDashPlayerStats", {**common, "per_mode_detailed": "Totals",
                                           "measure_type_detailed_defense": m}, TOTALS_MAX_AGE_H)
             for m in PLAYER_STATS_MEASURES]
    jobs += [Job("LeagueDashPlayerClutch", {**common, "per_mode_detailed": "Totals",
                                            "measure_type_detailed_defense": m})
             for m in ["Base", "Advanced"]]
    jobs += [Job("LeagueDashPtStats", {**common, "per_mode_simple": "Totals",
                                       "player_or_team": "Player", "pt_measure_type": m})
             for m in PT_MEASURES]
    jobs += [Job("SynergyPlayTypes", {"season": season, "season_type_all_star": season_type,
                                      "league_id": "00", "per_mode_simple": "Totals",
                                      "player_or_team_abbreviation": "P",
                                      "play_type_nullable": pt, "type_grouping_nullable": side})
             for pt in PLAY_TYPES for side in ["offensive", "defensive"]]
    jobs += [Job("LeagueDashPtDefend", {**common, "league_id": "00",
                                        "per_mode_simple": "Totals", "defense_category": c})
             for c in DEFENSE_CATEGORIES]
    jobs += [Job("LeagueDashPlayerPtShot", {**common, "league_id": "00",
                                            "per_mode_simple": "Totals", param: bucket})
             for param, buckets in PT_SHOT_BUCKETS.items() for bucket in buckets]
    jobs += [Job("TeamPlayerOnOffSummary", {**common, "team_id": t["id"],
                                            "per_mode_detailed": "Totals",
                                            "measure_type_detailed_defense": "Base"})
             for t in teams.get_teams()]
    return jobs


def game_jobs(game_ids: list[str]) -> list[Job]:
    # A finished game's box score does not change, so it is cached for good.
    return [Job(ep, {"game_id": gid}, max_age_h=None)
            for gid in game_ids for ep in GAME_ENDPOINTS]


def history_jobs(seasons: list[str], current: str) -> list[Job]:
    """League-wide box and advanced totals for each season: every player, one request
    per measure. Finished seasons never change, so they are cached for good."""
    return [Job("LeagueDashPlayerStats", {"season": s, "season_type_all_star": "Regular Season",
                                          "per_mode_detailed": "Totals", "measure_type_detailed_defense": m},
                max_age_h=TOTALS_MAX_AGE_H if s == current else None)
            for s in seasons for m in ("Base", "Advanced")]


TEAM_PT_MEASURES = ["Passing", "Drives", "Possessions", "CatchShoot", "PullUpShot",
                    "ElbowTouch", "PostTouch", "PaintTouch"]


def team_jobs(seasons: list[str], current: str) -> list[Job]:
    """Team-level offense per season: Synergy play types, tracking dashboards, pace and
    scoring mix, and shot zones. Synergy starts in 2015-16. Finished seasons are cached for good."""
    jobs = []
    for s in seasons:
        age = SEASON_MAX_AGE_H if s == current else None
        common = {"season": s, "season_type_all_star": "Regular Season"}
        jobs += [Job("SynergyPlayTypes", {**common, "league_id": "00", "per_mode_simple": "Totals",
                                          "player_or_team_abbreviation": "T", "play_type_nullable": pt,
                                          "type_grouping_nullable": "offensive"}, age)
                 for pt in PLAY_TYPES]
        jobs += [Job("LeagueDashPtStats", {**common, "per_mode_simple": "Totals", "player_or_team": "Team",
                                           "pt_measure_type": m}, age)
                 for m in TEAM_PT_MEASURES]
        jobs += [Job("LeagueDashTeamStats", {**common, "per_mode_detailed": "Totals",
                                             "measure_type_detailed_defense": m}, age)
                 for m in ("Base", "Advanced", "Scoring")]
        jobs.append(Job("LeagueDashTeamShotLocations", {**common, "distance_range": "By Zone",
                                                        "per_mode_detailed": "Totals"}, age))
    return jobs


def career_jobs(player_ids: list[int]) -> list[Job]:
    # Season-by-season totals for a player's whole career (regular season and playoffs).
    # Refetched when stale because active players add games every night.
    return [Job("PlayerCareerStats", {"player_id": pid, "per_mode36": "Totals", "league_id_nullable": "00"})
            for pid in player_ids]


def lineup_jobs(season: str, season_type: str) -> list[Job]:
    """Every 5-man and 2-man unit's totals, in the Base and the Advanced (ratings, pace) measure types."""
    return [Job("LeagueDashLineups", {"season": season, "season_type_all_star": season_type, "per_mode_detailed": "Totals",
                                      "group_quantity": quantity, "measure_type_detailed_defense": measure})
            for quantity in (5, 2) for measure in ("Base", "Advanced")]


def team_pair_jobs(season: str, season_type: str, team_ids: list[int]) -> list[Job]:
    """2-man units per team: the league-wide list stops at 2000 rows, which drops most of the pairs."""
    return [Job("LeagueDashLineups", {"season": season, "season_type_all_star": season_type, "per_mode_detailed": "Totals",
                                      "group_quantity": 2, "measure_type_detailed_defense": "Advanced", "team_id_nullable": team})
            for team in team_ids]


def matchup_jobs(season: str, season_type: str, player_ids: list[int]) -> list[Job]:
    """Every defender each of these players faced, with possessions, points and shots (from 2017-18 on)."""
    return [Job("LeagueSeasonMatchups", {"season": season, "season_type_playoffs": season_type,
                                         "per_mode_simple": "Totals", "off_player_id_nullable": pid})
            for pid in player_ids]


def player_jobs(season: str, season_type: str, roster: list[tuple[int, int]]) -> list[Job]:
    common = {"season": season, "season_type_all_star": season_type,
              "per_mode_simple": "Totals"}
    return [Job(ep, {**common, "team_id": team_id, "player_id": player_id})
            for team_id, player_id in roster
            for ep in ["PlayerDashPtPass", "PlayerDashPtReb"]]
