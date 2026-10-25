-- Overall ratings (ballstats/ratings.py).

CREATE TABLE IF NOT EXISTS feat.player_rating (
    season           text    NOT NULL,
    player_id        bigint  NOT NULL,
    name             text    NOT NULL,
    team             text,
    gp               integer NOT NULL,
    minutes          double precision NOT NULL,
    ovr              integer NOT NULL,          -- 40..99
    z                double precision NOT NULL, -- after the sample-size pull toward replacement
    qualified        boolean NOT NULL,          -- 500+ minutes
    baseline_season  text    NOT NULL,          -- season whose qualified players set the scale
    detail           jsonb   NOT NULL,          -- component z-scores and the raw inputs behind them
    model_version    text    NOT NULL,
    PRIMARY KEY (season, player_id)
);

CREATE TABLE IF NOT EXISTS feat.player_career_rating (
    player_id          bigint PRIMARY KEY,
    peak               double precision NOT NULL,  -- best 3 qualifying seasons in a row
    peak_from          text NOT NULL,
    peak_to            text NOT NULL,
    avg_ovr            double precision NOT NULL,  -- minutes-weighted over qualifying seasons
    career             double precision NOT NULL,  -- 0.7 peak + 0.3 average
    seasons            integer NOT NULL,           -- seasons rated
    qualified_seasons  integer NOT NULL,
    model_version      text NOT NULL
);
