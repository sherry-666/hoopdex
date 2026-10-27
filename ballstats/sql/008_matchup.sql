-- How offensive systems fare against defensive systems once team quality is removed (ballstats/matchup.py).

CREATE TABLE IF NOT EXISTS feat.style_matchup (
    off_style      integer NOT NULL,           -- feat.team_style.style_id of the scoring team
    def_tag        text    NOT NULL,           -- feat.team_profile.defense_tag of the defending team
    raw_effect     double precision NOT NULL,  -- points per game above / below what the two teams' own levels predict
    effect         double precision NOT NULL,  -- the same, shrunk toward zero by how noisy it is
    se             double precision NOT NULL,  -- bootstrap standard error of raw_effect
    n              integer NOT NULL,           -- team games in the cell
    off_teams      integer NOT NULL DEFAULT 0, -- distinct team-seasons behind the offensive system (few = one team's habits)
    model_version  text    NOT NULL,
    PRIMARY KEY (off_style, def_tag)
);

ALTER TABLE feat.style_matchup ADD COLUMN IF NOT EXISTS off_teams integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS feat.matchup_meta (
    model_version  text PRIMARY KEY,
    seasons        text[] NOT NULL,
    n_games        integer NOT NULL,
    p_value        double precision NOT NULL,  -- permutation test: is there any matchup structure at all
    season_corr    double precision,           -- do the cells agree between the first and the last season fitted
    tau            double precision NOT NULL,  -- sd of true cell effects, points per game
    fitted_at      timestamptz NOT NULL DEFAULT now()
);
