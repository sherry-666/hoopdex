-- feat layer: features and model outputs.
CREATE SCHEMA IF NOT EXISTS feat;

-- The first role model (flat GMM roles) stored role_id/probs. Its rows are derived
-- data, so drop that shape and let the families + archetypes model refill it.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'feat' AND table_name = 'player_role' AND column_name = 'role_id') THEN
        DROP TABLE feat.player_role;
    END IF;
END $$;

-- One row per player, season and side: a hard family plus a mix of archetypes.
CREATE TABLE IF NOT EXISTS feat.player_role (
    season              text        NOT NULL,
    player_id           bigint      NOT NULL,
    side                text        NOT NULL CHECK (side IN ('offense', 'defense')),
    family_id           integer     NOT NULL,
    family_name         text,
    top_archetype_id    integer     NOT NULL,
    top_archetype_name  text,
    top_weight          double precision NOT NULL,
    style_label         text        NOT NULL,   -- top archetype, or "A + B" when no archetype has half
    weights             jsonb       NOT NULL,   -- {archetype_id: weight}, sums to 1
    in_fit              boolean     NOT NULL,   -- false = under the minutes threshold, projected only
    model_version       text        NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (season, player_id, side)
);

-- The families and archetypes themselves, with their feature profiles (z-scores).
CREATE TABLE IF NOT EXISTS feat.role_type (
    season         text        NOT NULL,
    side           text        NOT NULL CHECK (side IN ('offense', 'defense')),
    level          text        NOT NULL CHECK (level IN ('family', 'archetype')),
    type_id        integer     NOT NULL,
    name           text,
    n_fit          integer     NOT NULL,   -- fit players whose family / top archetype this is
    profile        jsonb       NOT NULL,   -- {feature: z}
    model_version  text        NOT NULL,
    PRIMARY KEY (season, side, level, type_id)
);

-- Transition values for the season in progress (blend.py): the season's own mix and how
-- much of it the stored weights carry; null when not blended.
ALTER TABLE feat.player_role ADD COLUMN IF NOT EXISTS raw_weights jsonb;
ALTER TABLE feat.player_role ADD COLUMN IF NOT EXISTS blend_weight double precision;
ALTER TABLE feat.player_role ADD COLUMN IF NOT EXISTS prior_season text;
