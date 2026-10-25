-- core layer: cleaned facts parsed from raw responses (ballstats/core.py).
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.player (
    player_id     bigint PRIMARY KEY,
    name          text NOT NULL,
    first_season  text,                 -- first and last NBA regular season played
    last_season   text,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- One row per player, season, season type and team stint. A player traded mid-season
-- has one row per team plus a 'TOT' row with his combined line.
CREATE TABLE IF NOT EXISTS core.player_season (
    player_id    bigint  NOT NULL,
    season       text    NOT NULL,      -- '2025-26'
    season_type  text    NOT NULL CHECK (season_type IN ('regular', 'playoffs')),
    team         text    NOT NULL,      -- abbreviation, or 'TOT'
    team_id      bigint,
    age          integer,
    gp integer, gs integer, min double precision,
    fgm integer, fga integer, fg3m integer, fg3a integer, ftm integer, fta integer,
    oreb integer, dreb integer, reb integer, ast integer, stl integer, blk integer,
    tov integer, pf integer, pts integer,
    PRIMARY KEY (player_id, season, season_type, team)
);

-- Career totals per season type, as stats.nba.com reports them.
CREATE TABLE IF NOT EXISTS core.player_career (
    player_id    bigint  NOT NULL,
    season_type  text    NOT NULL CHECK (season_type IN ('regular', 'playoffs')),
    gp integer, gs integer, min double precision,
    fgm integer, fga integer, fg3m integer, fg3a integer, ftm integer, fta integer,
    oreb integer, dreb integer, reb integer, ast integer, stl integer, blk integer,
    tov integer, pf integer, pts integer,
    PRIMARY KEY (player_id, season_type)
);
