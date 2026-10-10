-- olympics_analysis.sql
-- Ten analysis questions on 120 years of Summer Olympics data.
-- Runs unchanged on SQLite and MySQL 8. Load the data first (see sql/README.md).
--
-- Counting rules, matching the dashboard:
-- * Summer Games only.
-- * A team medal counts once per country, not once per team member, so medal counts
--   use DISTINCT (Team, NOC, Year, City, Sport, Event, Medal).
-- * The source CSV contains 1,385 exact duplicate rows; athlete-level queries use
--   SELECT DISTINCT * so those rows are not counted twice.


-- Q1. How big are the Summer Olympics?
-- Concepts: COUNT(DISTINCT), CASE inside an aggregate, LEFT JOIN
SELECT
    COUNT(DISTINCT CASE WHEN e.Year <> 1906 THEN e.Year END) AS editions,  -- the 1906 Intercalated Games are not officially recognised
    COUNT(DISTINCT e.City)   AS host_cities,
    COUNT(DISTINCT e.Sport)  AS sports,
    COUNT(DISTINCT e.Event)  AS events,
    COUNT(DISTINCT r.region) AS nations,
    COUNT(DISTINCT e.ID)     AS athletes
FROM athlete_events e
LEFT JOIN noc_regions r ON r.NOC = e.NOC
WHERE e.Season = 'Summer';


-- Q2. Which countries have won the most medals of all time?
-- Concepts: CTE, conditional aggregation, JOIN, ORDER BY with tie-breakers
WITH medals AS (
    SELECT DISTINCT e.Team, e.NOC, e.Year, e.City, e.Sport, e.Event, e.Medal
    FROM athlete_events e
    WHERE e.Season = 'Summer' AND e.Medal IS NOT NULL
)
SELECT
    r.region AS country,
    SUM(CASE WHEN m.Medal = 'Gold'   THEN 1 ELSE 0 END) AS gold,
    SUM(CASE WHEN m.Medal = 'Silver' THEN 1 ELSE 0 END) AS silver,
    SUM(CASE WHEN m.Medal = 'Bronze' THEN 1 ELSE 0 END) AS bronze,
    COUNT(*) AS total
FROM medals m
JOIN noc_regions r ON r.NOC = m.NOC
WHERE r.region IS NOT NULL
GROUP BY r.region
ORDER BY gold DESC, silver DESC, bronze DESC
LIMIT 10;


-- Q3. How has India performed at every Summer Games, and how did each Games compare with the last?
-- Concepts: multiple CTEs, LEFT JOIN, COALESCE, LAG() window function
WITH india_athletes AS (
    SELECT e.Year, COUNT(DISTINCT e.ID) AS athletes
    FROM athlete_events e
    JOIN noc_regions r ON r.NOC = e.NOC
    WHERE e.Season = 'Summer' AND r.region = 'India'
    GROUP BY e.Year
),
india_medals AS (
    SELECT m.Year, COUNT(*) AS medals
    FROM (
        SELECT DISTINCT e.Team, e.NOC, e.Year, e.City, e.Sport, e.Event, e.Medal
        FROM athlete_events e
        WHERE e.Season = 'Summer' AND e.Medal IS NOT NULL
    ) m
    JOIN noc_regions r ON r.NOC = m.NOC
    WHERE r.region = 'India'
    GROUP BY m.Year
)
SELECT
    a.Year,
    a.athletes,
    COALESCE(m.medals, 0) AS medals,
    COALESCE(m.medals, 0) - LAG(COALESCE(m.medals, 0)) OVER (ORDER BY a.Year) AS change_vs_previous
FROM india_athletes a
LEFT JOIN india_medals m ON m.Year = a.Year
ORDER BY a.Year;


-- Q4. Which country topped the gold-medal table at each Games?
-- Concepts: RANK() window function partitioned by Games (ties are kept)
WITH medals AS (
    SELECT DISTINCT e.Team, e.NOC, e.Year, e.City, e.Sport, e.Event, e.Medal
    FROM athlete_events e
    WHERE e.Season = 'Summer' AND e.Medal IS NOT NULL
),
golds AS (
    SELECT m.Year, r.region AS country, COUNT(*) AS gold
    FROM medals m
    JOIN noc_regions r ON r.NOC = m.NOC
    WHERE m.Medal = 'Gold' AND r.region IS NOT NULL
    GROUP BY m.Year, r.region
),
ranked AS (
    SELECT Year, country, gold,
           RANK() OVER (PARTITION BY Year ORDER BY gold DESC) AS gold_position
    FROM golds
)
SELECT Year, country, gold
FROM ranked
WHERE gold_position = 1
ORDER BY Year, country;


-- Q5. How has women's participation grown over time?
-- Concepts: COUNT(DISTINCT CASE ...), percentage calculation, GROUP BY year
SELECT
    e.Year,
    COUNT(DISTINCT e.ID) AS athletes,
    COUNT(DISTINCT CASE WHEN e.Sex = 'F' THEN e.ID END) AS women,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN e.Sex = 'F' THEN e.ID END) / COUNT(DISTINCT e.ID), 1) AS women_pct
FROM athlete_events e
WHERE e.Season = 'Summer'
GROUP BY e.Year
ORDER BY e.Year;


-- Q6. Who are the most decorated Summer Olympians?
-- Concepts: derived table to remove duplicate rows, GROUP BY on a key, aggregate tie-breakers
SELECT
    e.Name AS athlete,
    MAX(r.region) AS country,
    MAX(e.Sport)  AS sport,
    SUM(CASE WHEN e.Medal = 'Gold' THEN 1 ELSE 0 END) AS gold,
    COUNT(*) AS total_medals
FROM (SELECT DISTINCT * FROM athlete_events WHERE Season = 'Summer') e
LEFT JOIN noc_regions r ON r.NOC = e.NOC
WHERE e.Medal IS NOT NULL
GROUP BY e.ID, e.Name
ORDER BY total_medals DESC, gold DESC, athlete
LIMIT 10;


-- Q7. Which countries turn the largest share of their athletes into medallists? (at least 1,000 athletes)
-- Concepts: CTE, ratio of two distinct counts, filtering an aggregate
WITH country_athletes AS (
    SELECT
        r.region AS country,
        COUNT(DISTINCT e.ID) AS athletes,
        COUNT(DISTINCT CASE WHEN e.Medal IS NOT NULL THEN e.ID END) AS medallists
    FROM athlete_events e
    JOIN noc_regions r ON r.NOC = e.NOC
    WHERE e.Season = 'Summer' AND r.region IS NOT NULL
    GROUP BY r.region
)
SELECT
    country,
    athletes,
    medallists,
    ROUND(100.0 * medallists / athletes, 1) AS medallist_pct
FROM country_athletes
WHERE athletes >= 1000
ORDER BY medallist_pct DESC
LIMIT 10;


-- Q8. Are medallists older or younger than other competitors?
-- Concepts: COALESCE to label NULLs, AVG / MIN / MAX, GROUP BY an expression
SELECT
    COALESCE(e.Medal, 'No medal') AS result,
    COUNT(*)             AS entries,
    ROUND(AVG(e.Age), 1) AS avg_age,
    MIN(e.Age)           AS youngest,
    MAX(e.Age)           AS oldest
FROM (SELECT DISTINCT * FROM athlete_events WHERE Season = 'Summer') e
WHERE e.Age IS NOT NULL
GROUP BY COALESCE(e.Medal, 'No medal')
ORDER BY AVG(e.Age), result;


-- Q9. In which sports does a single country win the biggest share of the golds? (sports with at least 50 golds)
-- Concepts: window SUM() OVER, RANK() OVER, share of a partition total
WITH medals AS (
    SELECT DISTINCT e.Team, e.NOC, e.Year, e.City, e.Sport, e.Event, e.Medal
    FROM athlete_events e
    WHERE e.Season = 'Summer' AND e.Medal IS NOT NULL
),
sport_golds AS (
    SELECT m.Sport, r.region AS country, COUNT(*) AS gold
    FROM medals m
    JOIN noc_regions r ON r.NOC = m.NOC
    WHERE m.Medal = 'Gold' AND r.region IS NOT NULL
    GROUP BY m.Sport, r.region
),
ranked AS (
    SELECT Sport, country, gold,
           SUM(gold) OVER (PARTITION BY Sport) AS sport_golds_total,
           RANK() OVER (PARTITION BY Sport ORDER BY gold DESC) AS gold_position
    FROM sport_golds
)
SELECT
    Sport,
    country,
    gold,
    sport_golds_total,
    ROUND(100.0 * gold / sport_golds_total, 1) AS share_pct
FROM ranked
WHERE gold_position = 1 AND sport_golds_total >= 50
ORDER BY share_pct DESC
LIMIT 10;


-- Q10. Which sports have the tallest medallists, and how heavy are they? (at least 100 measured medallists)
-- Concepts: derived table, AVG on measurements, HAVING
SELECT
    e.Sport,
    COUNT(DISTINCT e.ID)    AS medallists,
    ROUND(AVG(e.Height), 1) AS avg_height_cm,
    ROUND(AVG(e.Weight), 1) AS avg_weight_kg
FROM (
    SELECT DISTINCT ID, Sport, Height, Weight
    FROM athlete_events
    WHERE Season = 'Summer' AND Medal IS NOT NULL AND Height IS NOT NULL AND Weight IS NOT NULL
) e
GROUP BY e.Sport
HAVING COUNT(DISTINCT e.ID) >= 100
ORDER BY AVG(e.Height) DESC, e.Sport
LIMIT 10;
