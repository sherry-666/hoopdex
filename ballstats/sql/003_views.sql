-- Views of the role model that the web app reads (see ballstats/views.py).

CREATE TABLE IF NOT EXISTS feat.player_view (
    season     text    NOT NULL,
    player_id  bigint  NOT NULL,
    side       text    NOT NULL CHECK (side IN ('offense', 'defense')),
    x          double precision NOT NULL,   -- t-SNE map position
    y          double precision NOT NULL,
    f1         double precision NOT NULL,   -- varimax factor scores (z)
    f2         double precision NOT NULL,
    f3         double precision NOT NULL,
    l1         double precision NOT NULL,   -- LDA axis scores (z)
    l2         double precision NOT NULL,
    l3         double precision NOT NULL,
    PRIMARY KEY (season, player_id, side)
);

CREATE TABLE IF NOT EXISTS feat.role_axis (
    season  text NOT NULL,
    side    text NOT NULL CHECK (side IN ('offense', 'defense')),
    method  text NOT NULL CHECK (method IN ('factor', 'lda')),
    axis    text NOT NULL,                  -- f1..f3, l1..l3
    name    text NOT NULL,
    high    text NOT NULL,                  -- features that load highest
    low     text NOT NULL,
    PRIMARY KEY (season, side, axis)
);

CREATE TABLE IF NOT EXISTS feat.player_stats (
    season     text    NOT NULL,
    player_id  bigint  NOT NULL,
    name       text    NOT NULL,
    team       text,
    gp         integer NOT NULL,
    minutes    integer NOT NULL,
    stats      jsonb   NOT NULL,            -- {feature: value} in readable units
    PRIMARY KEY (season, player_id)
);
