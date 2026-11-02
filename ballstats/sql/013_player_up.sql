-- Fans' "Up" taps on a player page (live schema, so push_db.sh never wipes it).
CREATE TABLE IF NOT EXISTS live.player_up (
    player_id bigint PRIMARY KEY,
    ups       bigint NOT NULL DEFAULT 0
);
