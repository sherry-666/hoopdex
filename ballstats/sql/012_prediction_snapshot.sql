-- The model's prediction for each game as it stood on one day (the daily snapshot cron), with every input and
-- component, so the coefficients (INJURY_AMP, C_ROSTER, ...) can later be fitted against the final scores.
CREATE TABLE IF NOT EXISTS live.prediction_snapshot (
    game_id        text NOT NULL,
    snapshot_date  date NOT NULL,         -- US Eastern day the snapshot was taken
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
    prediction     jsonb NOT NULL,        -- the full /api/predict payload
    PRIMARY KEY (game_id, snapshot_date)
);
