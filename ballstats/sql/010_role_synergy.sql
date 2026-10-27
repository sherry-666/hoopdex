-- Which role pairs play better or worse together than the two players' own levels predict
-- (ballstats/lineup_synergy.py). One row per side and unordered pair of archetypes.

CREATE TABLE IF NOT EXISTS feat.role_synergy (
    side     text    NOT NULL DEFAULT 'offense',  -- 'offense' | 'defense'
    type_a   integer NOT NULL,           -- feat.role_type.type_id of that side, type_a <= type_b
    type_b   integer NOT NULL,
    effect   double precision NOT NULL,  -- rating points per 100 possessions of the pair on court (higher = better)
    se       double precision NOT NULL,  -- bootstrap over team-seasons
    PRIMARY KEY (side, type_a, type_b)
);

CREATE TABLE IF NOT EXISTS feat.role_synergy_meta (
    side       text NOT NULL DEFAULT 'offense',
    n_pairs    integer NOT NULL,
    n_poss     integer NOT NULL,
    cv_gain    double precision NOT NULL,  -- held-out error reduction from the role terms (0 = no better predictions)
    seasons    text[] NOT NULL,
    fitted_at  timestamptz NOT NULL DEFAULT now()
);

-- Tables made before the side column existed.
ALTER TABLE feat.role_synergy ADD COLUMN IF NOT EXISTS side text NOT NULL DEFAULT 'offense';
ALTER TABLE feat.role_synergy_meta ADD COLUMN IF NOT EXISTS side text NOT NULL DEFAULT 'offense';
DO $$ BEGIN
    IF (SELECT count(*) FROM information_schema.key_column_usage
        WHERE table_schema = 'feat' AND constraint_name = 'role_synergy_pkey') < 3 THEN
        ALTER TABLE feat.role_synergy DROP CONSTRAINT role_synergy_pkey;
        ALTER TABLE feat.role_synergy ADD PRIMARY KEY (side, type_a, type_b);
    END IF;
END $$;
