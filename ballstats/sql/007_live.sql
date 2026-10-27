-- live layer: refreshed daily by `ballstats live-update` (ballstats/live.py) from ESPN's public
-- feeds, which unlike stats.nba.com answer cloud IPs. Kept apart from raw / feat so that
-- scripts/push_db.sh (which replaces those schemas) never wipes it.
CREATE SCHEMA IF NOT EXISTS live;

-- Current injury report: a full snapshot, so a player who recovers drops out on the next run.
CREATE TABLE IF NOT EXISTS live.injury (
    espn_id       bigint PRIMARY KEY,     -- ESPN's injury record id
    player_id     bigint,                 -- NBA person id, matched by name; null if unmatched
    name          text NOT NULL,
    team          text,
    status        text NOT NULL,          -- Out, Day-To-Day
    body_part     text,                   -- Foot, Knee, ...
    detail        text,                   -- Fracture, Soreness, ...
    side          text,
    return_date   date,                   -- ESPN's estimate, when it gives one
    short_comment text,
    long_comment  text,
    reported_at   timestamptz,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS injury_player_idx ON live.injury (player_id);

-- One row per player per finished game; players who sat out have dnp_reason instead of stats.
CREATE TABLE IF NOT EXISTS live.player_game (
    player_id    bigint NOT NULL,
    game_id      text   NOT NULL,         -- ESPN event id
    game_date    date   NOT NULL,         -- US Eastern calendar date
    season       text   NOT NULL,
    team         text   NOT NULL,
    opp          text   NOT NULL,
    home         boolean NOT NULL,
    team_score   integer,
    opp_score    integer,
    started      boolean,
    dnp_reason   text,
    min integer, pts integer, reb integer, ast integer, stl integer, blk integer, tov integer, pf integer,
    fgm integer, fga integer, fg3m integer, fg3a integer, ftm integer, fta integer,
    oreb integer, dreb integer, plus_minus integer,
    PRIMARY KEY (player_id, game_id)
);
ALTER TABLE live.player_game ADD COLUMN IF NOT EXISTS season_type smallint;   -- ESPN: 2 regular season, 3 playoffs
CREATE INDEX IF NOT EXISTS player_game_date_idx ON live.player_game (player_id, game_date DESC);

CREATE TABLE IF NOT EXISTS live.update_log (
    id          bigserial PRIMARY KEY,
    ran_at      timestamptz NOT NULL DEFAULT now(),
    games       integer,
    injuries    integer,
    unmatched   text[]
);

-- Regular-season standings per season, from ESPN's standings feed. Past seasons are final;
-- the current one is refreshed on every run. rank is the position within the conference.
CREATE TABLE IF NOT EXISTS live.standing (
    season       text NOT NULL,
    team         text NOT NULL,
    conf         text NOT NULL CHECK (conf IN ('East', 'West')),
    rank         integer NOT NULL,
    wins         integer NOT NULL,
    losses       integer NOT NULL,
    win_pct      double precision,
    games_behind double precision,
    home         text, road text, conf_record text, last10 text, streak text,
    pts_for      double precision,       -- per game
    pts_against  double precision,
    clincher     text,                   -- z / y / x / e: clinched best record / division / playoffs / eliminated
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (season, team)
);
ALTER TABLE live.standing ADD COLUMN IF NOT EXISTS v smallint;   -- ranking logic version, see live.STANDINGS_V
