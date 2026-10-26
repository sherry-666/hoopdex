-- Team offensive systems and profiles (ballstats/teams.py).

CREATE TABLE IF NOT EXISTS feat.team_style (
    style_id       integer PRIMARY KEY,
    name           text,
    description    text,
    centroid       jsonb NOT NULL,     -- {offensive archetype: z} of the style's centre
    model_version  text  NOT NULL
);

CREATE TABLE IF NOT EXISTS feat.team_profile (
    season            text    NOT NULL,
    team              text    NOT NULL,
    style_id          integer NOT NULL,
    defense_tag       text    NOT NULL,
    off_mix           jsonb   NOT NULL,   -- {archetype: minutes-weighted share} over the rotation
    def_mix           jsonb   NOT NULL,
    off_z             jsonb   NOT NULL,   -- offensive mix vs the league, in sd
    avg_ovr           double precision,
    rotation_minutes  integer NOT NULL,
    core              jsonb   NOT NULL,   -- the rotation, most minutes first
    model_version     text    NOT NULL,
    PRIMARY KEY (season, team)
);

-- Team ratings (teams.py): half rotation player ratings, half actual results; centred on 80.
ALTER TABLE feat.team_profile ADD COLUMN IF NOT EXISTS ovr integer;
ALTER TABLE feat.team_profile ADD COLUMN IF NOT EXISTS off integer;
ALTER TABLE feat.team_profile ADD COLUMN IF NOT EXISTS def integer;
ALTER TABLE feat.team_profile ADD COLUMN IF NOT EXISTS ortg double precision;  -- points scored per 100 possessions
ALTER TABLE feat.team_profile ADD COLUMN IF NOT EXISTS drtg double precision;  -- points allowed per 100 possessions

-- Offensive system style of every team season since 2015-16 (teams.py, team_features.py).
CREATE TABLE IF NOT EXISTS feat.team_system (
    season         text    NOT NULL,
    team           text    NOT NULL,
    style_id       integer NOT NULL,
    features       jsonb   NOT NULL,   -- {feature: z within the season}
    model_version  text    NOT NULL,
    PRIMARY KEY (season, team)
);
