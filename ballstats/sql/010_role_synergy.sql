-- Which offensive role pairs play better or worse together than the two players' own levels predict
-- (ballstats/lineup_synergy.py). One row per unordered pair of offensive archetypes.

CREATE TABLE IF NOT EXISTS feat.role_synergy (
    type_a   integer NOT NULL,           -- feat.role_type.type_id, side = 'offense', type_a <= type_b
    type_b   integer NOT NULL,
    effect   double precision NOT NULL,  -- net rating points per 100 possessions of the pair on court
    se       double precision NOT NULL,  -- bootstrap over team-seasons
    PRIMARY KEY (type_a, type_b)
);

CREATE TABLE IF NOT EXISTS feat.role_synergy_meta (
    n_pairs    integer NOT NULL,
    n_poss     integer NOT NULL,
    cv_gain    double precision NOT NULL,  -- held-out error reduction from the role terms (0 = no better predictions)
    seasons    text[] NOT NULL,
    fitted_at  timestamptz NOT NULL DEFAULT now()
);
