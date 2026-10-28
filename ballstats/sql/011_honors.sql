-- Honors from stats.nba.com PlayerAwards and TeamDetails (core.parse_honors).

-- One row per award received. Weekly and monthly awards repeat, so there is no key.
CREATE TABLE IF NOT EXISTS core.player_award (
    player_id    bigint NOT NULL,
    award        text   NOT NULL,      -- 'NBA Most Valuable Player', 'All-NBA', ...
    season       text,                 -- '2012-13'
    team_number  text,                 -- All-NBA / All-Defensive / All-Rookie: 1st or 2nd (3rd) team
    team_id      bigint                -- team he won it with, where the feed names one
);
CREATE INDEX IF NOT EXISTS player_award_player ON core.player_award (player_id);

-- Team honors: kind is champion / conference / division (year = the season's closing year, opponent = Finals loser),
-- retired (a retired number) or hof (a Hall of Famer who played for the team).
CREATE TABLE IF NOT EXISTS core.team_honor (
    team         text   NOT NULL,      -- abbreviation
    kind         text   NOT NULL CHECK (kind IN ('champion', 'conference', 'division', 'retired', 'hof')),
    year         integer,
    opponent     text,
    player_id    bigint,
    player       text,
    jersey       text,
    seasons      text                  -- seasons with the team, as the feed spells them
);
CREATE INDEX IF NOT EXISTS team_honor_team ON core.team_honor (team);
