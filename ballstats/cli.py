import argparse
import datetime as dt
import logging
import sys

from nba_api.stats.static import teams as nba_teams

from ballstats import catalog, db
from ballstats.collector import Collector, RunStopped, result_rows

log = logging.getLogger("ballstats")
GROUPS = ("season", "games", "players")
OPTIONAL_GROUPS = ("careers", "history", "teams", "lineups", "honors")   # run only when asked for
HISTORY_FROM = 1996   # first season with advanced stats on stats.nba.com
MATCHUP_MIN_MINUTES = 100   # players with fewer minutes are not asked for their matchups
TEAMS_FROM = 2015     # first season with Synergy play types


def current_season(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    start = today.year if today.month >= 10 else today.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def run_jobs(collector: Collector, jobs: list[catalog.Job], label: str, refresh: bool) -> None:
    log.info("%s: %d requests", label, len(jobs))
    for i, job in enumerate(jobs, 1):
        collector.fetch(job.endpoint, job.params, max_age_h=job.max_age_h, refresh=refresh)
        if i % 25 == 0 or i == len(jobs):
            log.info("%s: %d/%d  %s", label, i, len(jobs), collector.stats)


def cmd_collect(args) -> int:
    """Exit codes: 0 done, 1 no game list, 2 some requests failed, 3 stopped early (budget / refused)."""
    conn = db.connect()
    db.init_schema(conn)
    collector = Collector(conn)
    args.stats = collector.stats
    try:
        return collect_season(args, conn, collector)
    except RunStopped as e:
        log.warning("stopped early: %s; %s", e, collector.stats)
        return 3


def collect_season(args, conn, collector) -> int:
    groups = set(args.groups.split(","))

    finder = catalog.game_finder_job(args.season, args.season_type)
    body = collector.fetch(finder.endpoint, finder.params, max_age_h=finder.max_age_h)
    if body is None:
        log.error("could not load the game list; is stats.nba.com reachable?")
        return 1
    # Team-level rows: two per game; WL is empty until the game is final.
    game_ids = sorted({r["GAME_ID"] for r in result_rows(body) if r.get("WL")})
    log.info("%s %s: %d finished games", args.season, args.season_type, len(game_ids))

    if "season" in groups:
        run_jobs(collector, catalog.season_jobs(args.season, args.season_type),
                 "season", args.refresh)
    if "games" in groups:
        run_jobs(collector, catalog.game_jobs(game_ids), "games", args.refresh)
    if "players" in groups:
        base = collector.fetch("LeagueDashPlayerStats", {
            "season": args.season, "season_type_all_star": args.season_type,
            "per_mode_detailed": "Totals", "measure_type_detailed_defense": "Base",
        }, max_age_h=catalog.SEASON_MAX_AGE_H)
        roster = sorted({(r["TEAM_ID"], r["PLAYER_ID"]) for r in result_rows(base or {})})
        run_jobs(collector, catalog.player_jobs(args.season, args.season_type, roster),
                 "players", args.refresh)
    if "matchups" in groups:
        base = collector.fetch("LeagueDashPlayerStats", {
            "season": args.season, "season_type_all_star": args.season_type,
            "per_mode_detailed": "Totals", "measure_type_detailed_defense": "Base",
        }, max_age_h=catalog.SEASON_MAX_AGE_H)
        # Players with real minutes; the rest barely appear in anyone's matchups.
        shooters = sorted({r["PLAYER_ID"] for r in result_rows(base or {}) if (r.get("MIN") or 0) >= MATCHUP_MIN_MINUTES})
        run_jobs(collector, catalog.matchup_jobs(args.season, args.season_type, shooters), "matchups", args.refresh)
    if "lineups" in groups:
        run_jobs(collector, catalog.lineup_jobs(args.season, args.season_type), "lineups", args.refresh)
        five = collector.fetch("LeagueDashLineups", catalog.lineup_jobs(args.season, args.season_type)[1].params)
        teams = sorted({r["TEAM_ID"] for r in result_rows(five or {})})
        run_jobs(collector, catalog.team_pair_jobs(args.season, args.season_type, teams), "pairs", args.refresh)
    if "history" in groups:
        start = int(args.season[:4])
        seasons = [f"{y}-{(y + 1) % 100:02d}" for y in range(HISTORY_FROM, start + 1)]
        run_jobs(collector, catalog.history_jobs(seasons, args.season), "history", args.refresh)
    if "teams" in groups:
        start = int(args.season[:4])
        seasons = [f"{y}-{(y + 1) % 100:02d}" for y in range(TEAMS_FROM, start + 1)]
        run_jobs(collector, catalog.team_jobs(seasons, args.season), "teams", args.refresh)
    if "careers" in groups:
        # Everyone on this season's league list plus everyone the app already shows.
        allp = collector.fetch("CommonAllPlayers", {"season": args.season, "league_id": "00",
                                                    "is_only_current_season": 1}, max_age_h=catalog.SEASON_MAX_AGE_H)
        ids = {r["PERSON_ID"] for r in result_rows(allp or {})}
        ids |= {r[0] for r in conn.execute("SELECT DISTINCT player_id FROM feat.player_stats")}
        run_jobs(collector, catalog.career_jobs(sorted(ids)), "careers", args.refresh)

    if "honors" in groups:
        ids = {r[0] for r in conn.execute("SELECT player_id FROM core.player")}
        team_ids = sorted(t["id"] for t in nba_teams.get_teams())
        run_jobs(collector, catalog.honor_jobs(sorted(ids), team_ids), "honors", args.refresh)

    log.info("done: %s", collector.stats)
    return 0 if collector.stats["failed"] == 0 else 2


def cmd_status(args) -> int:
    conn = db.connect()
    rows = conn.execute(
        """
        SELECT endpoint,
               count(*) FILTER (WHERE status = 'ok')    AS ok,
               count(*) FILTER (WHERE status = 'error') AS error,
               max(fetched_at)                          AS last_fetch
        FROM raw.raw_response
        WHERE params ->> 'season' = %(s)s OR params ->> 'season_nullable' = %(s)s
           OR params ? 'game_id'
        GROUP BY endpoint ORDER BY endpoint
        """,
        {"s": args.season},
    ).fetchall()
    print(f"{'endpoint':32} {'ok':>6} {'error':>6}  last fetch")
    for endpoint, ok, error, last in rows:
        print(f"{endpoint:32} {ok:>6} {error:>6}  {last:%Y-%m-%d %H:%M}")
    return 0


def cmd_roles(args) -> int:
    from ballstats import features, roles, views  # heavy imports only when needed

    conn = db.connect()
    db.init_schema(conn)
    if args.all:
        seasons = [r[0] for r in conn.execute(
            "SELECT DISTINCT params->>'season' FROM raw.raw_response WHERE endpoint = 'LeagueDashPtStats'"
            " AND status = 'ok' ORDER BY 1")]
        reference = args.reference or args.season
        print(f"rebuilding {seasons} on the {reference} model:", views.rebuild_all(conn, reference, seasons))
        return 0
    info, off, de = features.build(conn, args.season)
    reference = args.reference or args.season
    if reference != args.season:
        # Fit on the reference season, then project this season onto that model so the
        # roles carry the same meaning; the explorer views stay with the reference season.
        ref_info, ref_off, ref_de = features.build(conn, reference)
        for side, X, ref_X in (("offense", off, ref_off), ("defense", de, ref_de)):
            fit = roles.project(roles.fit_side(side, ref_X, ref_info["min"], reference), X, info["min"])
            print(f"{side}: projected {len(fit.weights)} players of {args.season} onto {fit.model_version} ({reference}),"
                  f" {int(fit.in_fit.sum())} with {roles.MIN_MINUTES}+ minutes")
            if not args.dry_run:
                roles.store(conn, args.season, fit)
    else:
        for side, X in (("offense", off), ("defense", de)):
            fit = roles.fit_side(side, X, info["min"], args.season)
            print(roles.report(fit, info, args.season))
            print()
            if not args.dry_run:
                roles.store(conn, args.season, fit)
                views.store_side(conn, args.season, fit, X, info["min"])
    if not args.dry_run:
        views.store_stats(conn, args.season, info, off, de)
        from ballstats import blend
        print("blend:", blend.blend_roles(conn))
    return 0


def cmd_ratings(args) -> int:
    from ballstats import ratings

    conn = db.connect()
    db.init_schema(conn)
    print("ratings:", ratings.compute(conn))
    print("box totals:", ratings.store_box(conn))
    return 0


def cmd_teams(args) -> int:
    from ballstats import teams

    conn = db.connect()
    db.init_schema(conn)
    print("teams:", teams.compute(conn))
    return 0


def cmd_parse(args) -> int:
    from ballstats import core

    conn = db.connect()
    db.init_schema(conn)
    print("careers:", core.parse_careers(conn))
    print("honors:", core.parse_honors(conn))
    return 0


def cmd_matchup(args) -> int:
    from ballstats import matchup

    conn = db.connect()
    db.init_schema(conn)
    print("matchup:", matchup.compute(conn))
    return 0


def cmd_player_matchup(args) -> int:
    from ballstats import player_matchup

    conn = db.connect()
    db.init_schema(conn)
    print("player-matchup:", player_matchup.compute(conn))
    return 0


def cmd_role_synergy(args) -> int:
    from ballstats import lineup_synergy

    conn = db.connect()
    db.init_schema(conn)
    print("role-synergy:", lineup_synergy.compute(conn))
    return 0


def cmd_live_update(args) -> int:
    from ballstats import live

    conn = db.connect()
    db.init_schema(conn)
    print("live-update:", live.update(conn, args.days))
    return 0


def cmd_schedule_update(args) -> int:
    from ballstats import live

    conn = db.connect()
    db.init_schema(conn)
    print("schedule-update:", live.update_light(conn))
    return 0


def cmd_snapshot(args) -> int:
    from ballstats import predict

    conn = db.connect()
    db.init_schema(conn)
    print("snapshot:", predict.snapshot(conn), "games")
    return 0


def cmd_daily_update(args) -> int:
    """The nightly nba stats refresh: collect the season so far, then rebuild what is derived from it.

    Cheap when nothing is new (requests already cached are skipped). Stops before touching `feat` if
    the collection did not fully succeed, e.g. when stats.nba.com refuses this host.
    """
    from ballstats import blend

    reference = args.reference or blend.previous(args.season)
    conn = db.connect()
    db.init_schema(conn)
    have = conn.execute(
        "SELECT count(*) FROM raw.raw_response WHERE endpoint = 'LeagueDashPtStats' AND status = 'ok'"
        " AND params->>'season' = %s", (reference,)).fetchone()[0]
    conn.close()
    if not have:
        log.error("raw data for %s is missing; load it first (scripts/push_db.sh raw feat), "
                  "otherwise every past season would be refetched", reference)
        return 1

    collect = argparse.Namespace(season=args.season, season_type="Regular Season", refresh=False,
                                 groups="season,games,players,history,teams")
    code = cmd_collect(collect)
    if code == 3:   # not an error for an hourly job: the cache keeps the progress
        log.info("collection not finished; resuming next run. feat left as it was")
        return 0
    if code:
        log.error("collection incomplete (exit %d); feat left as it was", code)
        return code
    if not collect.stats["fetched"]:
        log.info("nothing new on stats.nba.com; feat is up to date")
        return 0
    cmd_roles(argparse.Namespace(season=args.season, reference=reference, all=False, dry_run=False))
    cmd_ratings(args)
    cmd_teams(args)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ballstats")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create the raw schema")

    collect = sub.add_parser("collect", help="fetch one season into raw.raw_response")
    collect.add_argument("--season", default=current_season())
    collect.add_argument("--season-type", default="Regular Season",
                         choices=["Regular Season", "Playoffs", "PlayIn"])
    collect.add_argument("--groups", default=",".join(GROUPS),
                         help=f"comma-separated subset of {','.join(GROUPS + OPTIONAL_GROUPS)}")
    collect.add_argument("--refresh", action="store_true",
                         help="refetch even requests that are cached and fresh")

    status = sub.add_parser("status", help="per-endpoint counts for a season")
    status.add_argument("--season", default=current_season())

    sub.add_parser("parse", help="parse raw responses into the core tables (players, seasons, careers)")
    sub.add_parser("ratings", help="compute season OVR and peak / career ratings")
    sub.add_parser("teams", help="team style profiles and offensive systems (after roles and ratings)")

    sub.add_parser("player-matchup", help="offensive x defensive player-type matchups from LeagueSeasonMatchups (after roles and collect --groups matchups)")
    sub.add_parser("role-synergy", help="offensive role pairs that play better or worse together (after roles and collect --groups lineups)")
    sub.add_parser("matchup", help="offence x defence system matchups with team quality removed (after teams and live-update)")

    live_p = sub.add_parser("live-update", help="finished games and the injury report from ESPN (the daily cron job)")
    live_p.add_argument("--days", type=int, default=3, help="look back this many days for games not stored yet")

    sub.add_parser("schedule-update", help="schedule and scores, injury report and standings from ESPN (the hourly cron job)")

    sub.add_parser("snapshot", help="store today's game predictions with every input, for fitting later (the noon cron job)")

    daily_p = sub.add_parser("daily-update", help="nba stats refresh of the current season, then roles / ratings / teams (the nightly job)")
    daily_p.add_argument("--season", default=current_season())
    daily_p.add_argument("--reference", help="role model season (default: the previous season)")

    roles_p = sub.add_parser("roles", help="fit role families and archetype mixes for a season")
    roles_p.add_argument("--season", default=current_season())
    roles_p.add_argument("--reference", help="fit on this season and project --season onto it")
    roles_p.add_argument("--all", action="store_true",
                         help="every season with tracking data on the --reference model, plus the career view")
    roles_p.add_argument("--dry-run", action="store_true", help="print the report, store nothing")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)

    if args.command == "init-db":
        print("applied:", ", ".join(db.init_schema(db.connect())))
        return 0
    if args.command == "collect":
        return cmd_collect(args)
    if args.command == "roles":
        return cmd_roles(args)
    if args.command == "parse":
        return cmd_parse(args)
    if args.command == "ratings":
        return cmd_ratings(args)
    if args.command == "schedule-update":
        return cmd_schedule_update(args)
    if args.command == "snapshot":
        return cmd_snapshot(args)
    if args.command == "live-update":
        return cmd_live_update(args)
    if args.command == "teams":
        return cmd_teams(args)
    if args.command == "daily-update":
        return cmd_daily_update(args)
    if args.command == "matchup":
        return cmd_matchup(args)
    if args.command == "role-synergy":
        return cmd_role_synergy(args)
    if args.command == "player-matchup":
        return cmd_player_matchup(args)
    return cmd_status(args)
