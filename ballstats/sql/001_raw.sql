-- raw layer: one row per (endpoint, request params), holding the latest response
-- verbatim so the core layer can be re-parsed without re-fetching.
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.raw_response (
    endpoint     text        NOT NULL,
    params_hash  text        NOT NULL,
    params       jsonb       NOT NULL,
    status       text        NOT NULL CHECK (status IN ('ok', 'error')),
    body         jsonb,
    error        text,
    attempts     integer     NOT NULL DEFAULT 0,
    fetched_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (endpoint, params_hash)
);

CREATE INDEX IF NOT EXISTS raw_response_status_idx ON raw.raw_response (status);
CREATE INDEX IF NOT EXISTS raw_response_season_idx ON raw.raw_response ((params ->> 'season'));
