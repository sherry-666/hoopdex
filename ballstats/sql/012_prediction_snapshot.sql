-- The model's prediction for each game (the daily snapshot cron), with every input and
-- component, so the coefficients (INJURY_AMP, C_ROSTER, ...) can later be fitted against the final scores.
CREATE TABLE IF NOT EXISTS live.prediction_snapshot (
    game_id        text PRIMARY KEY,      -- one row per game: each noon run updates it until the game is final
    snapshot_date  date NOT NULL,         -- US Eastern day of the latest snapshot
    taken_at       timestamptz NOT NULL DEFAULT now(),
    game_date      date NOT NULL,
    season         text NOT NULL,
    home           text NOT NULL,
    away           text NOT NULL,
    margin         real NOT NULL,         -- predicted home margin
    home_win       real NOT NULL,
    components     jsonb NOT NULL,        -- home_edge, roster, form, rest, matchup, fit, injury_hit per team
    inputs         jsonb NOT NULL,        -- rotation ratings (healthy / on the day / effective), form, back-to-back, constants
    injuries       jsonb NOT NULL,        -- both teams' reported players: status, return date, availability factor, rating, minutes
    prediction     jsonb NOT NULL         -- the full /api/predict payload
);

-- Earlier versions kept a row per (game, day): keep each game's latest and key the table on the game.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'live.prediction_snapshot'::regclass
               AND contype = 'p' AND array_length(conkey, 1) = 2) THEN
        DELETE FROM live.prediction_snapshot s USING live.prediction_snapshot n
         WHERE s.game_id = n.game_id AND s.snapshot_date < n.snapshot_date;
        ALTER TABLE live.prediction_snapshot DROP CONSTRAINT prediction_snapshot_pkey;
        ALTER TABLE live.prediction_snapshot ADD PRIMARY KEY (game_id);
    END IF;
END $$;
