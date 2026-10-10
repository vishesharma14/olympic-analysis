-- schema.sql
-- Tables for the Olympic dataset. Works in both SQLite and MySQL 8.
-- "NA" values in the CSVs are loaded as NULL.

DROP TABLE IF EXISTS athlete_events;
DROP TABLE IF EXISTS noc_regions;

-- One row per National Olympic Committee (NOC) code.
CREATE TABLE noc_regions (
    NOC     CHAR(3)      NOT NULL PRIMARY KEY,
    region  VARCHAR(50),
    notes   VARCHAR(50)
);

-- One row per athlete per event per Games.
-- No foreign key to noc_regions: a few NOC codes (e.g. SGP) have no region row,
-- so queries use LEFT JOIN or filter on region explicitly.
CREATE TABLE athlete_events (
    ID      INT          NOT NULL,
    Name    VARCHAR(120) NOT NULL,
    Sex     CHAR(1)      NOT NULL,
    Age     INT,
    Height  DOUBLE,
    Weight  DOUBLE,
    Team    VARCHAR(60)  NOT NULL,
    NOC     CHAR(3)      NOT NULL,
    Games   VARCHAR(15)  NOT NULL,
    Year    INT          NOT NULL,
    Season  VARCHAR(6)   NOT NULL,
    City    VARCHAR(30)  NOT NULL,
    Sport   VARCHAR(30)  NOT NULL,
    Event   VARCHAR(100) NOT NULL,
    Medal   VARCHAR(6)
);

CREATE INDEX idx_athlete_events_noc         ON athlete_events (NOC);
CREATE INDEX idx_athlete_events_season_year ON athlete_events (Season, Year);
CREATE INDEX idx_athlete_events_medal       ON athlete_events (Medal);
