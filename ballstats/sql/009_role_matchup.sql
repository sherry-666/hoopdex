-- Player-type matchups: how an offensive archetype scores against a defensive archetype once both
-- players' own levels are removed (ballstats/player_matchup.py). season = 'all' is the mean over seasons.

CREATE TABLE IF NOT EXISTS feat.role_matchup (
    season      text    NOT NULL,
    off_type    integer NOT NULL,           -- feat.role_type.type_id, side = 'offense'
    def_type    integer NOT NULL,           -- feat.role_type.type_id, side = 'defense'
    effect      double precision NOT NULL,  -- points per 100 partial possessions above / below the players' own levels
    spread      double precision,           -- sd of the effect across seasons ('all' row only)
    PRIMARY KEY (season, off_type, def_type)
);

CREATE TABLE IF NOT EXISTS feat.role_matchup_meta (
    season       text PRIMARY KEY,
    n_pairs      integer NOT NULL,          -- (offensive player, defender) pairs
    n_poss       integer NOT NULL,          -- partial possessions behind them
    mean_ppp     double precision NOT NULL, -- points per 100 partial possessions, the scale of the effects
    p_value      double precision,          -- permutation test: any structure at all (null for 'all')
    season_corr  double precision,          -- 'all' row: mean correlation of the tables between seasons
    fitted_at    timestamptz NOT NULL DEFAULT now()
);
