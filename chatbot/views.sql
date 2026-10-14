-- views.sql
-- The two views the chatbot queries. They apply the dashboard's counting rules so that
-- model-written SQL returns the same numbers as the dashboard and sql/olympics_analysis.sql:
-- * Summer Games only.
-- * The 1,385 exact duplicate rows in athlete_events.csv are removed with SELECT DISTINCT.
-- * Countries follow noc_regions.csv (the Soviet Union counts as Russia, East and West Germany as Germany).
-- * In country_medals a team medal counts once per country, not once per team member.
-- Run after sql/schema.sql has been loaded (see chatbot/db.py).

DROP VIEW IF EXISTS summer_entries;
DROP VIEW IF EXISTS country_medals;

-- One row per athlete per event per Games.
CREATE VIEW summer_entries AS
SELECT DISTINCT
    e.ID     AS athlete_id,
    e.Name   AS athlete,
    e.Sex    AS sex,
    e.Age    AS age,
    e.Height AS height_cm,
    e.Weight AS weight_kg,
    e.Team   AS team,
    e.NOC    AS noc,
    r.region AS country,
    e.Year   AS year,
    e.City   AS city,
    e.Sport  AS sport,
    e.Event  AS event,
    e.Medal  AS medal
FROM athlete_events e
LEFT JOIN noc_regions r ON r.NOC = e.NOC
WHERE e.Season = 'Summer';

-- One row per medal won by a country: a relay gold is one row, not one per runner.
CREATE VIEW country_medals AS
SELECT DISTINCT
    e.Team   AS team,
    e.NOC    AS noc,
    r.region AS country,
    e.Year   AS year,
    e.City   AS city,
    e.Sport  AS sport,
    e.Event  AS event,
    e.Medal  AS medal
FROM athlete_events e
LEFT JOIN noc_regions r ON r.NOC = e.NOC
WHERE e.Season = 'Summer' AND e.Medal IS NOT NULL;
