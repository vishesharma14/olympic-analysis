-- load_mysql.sql
-- Creates the `olympics` database in MySQL 8 and loads both CSVs into it.
--
-- Run from the repository root (so the CSV paths resolve):
--   mysql --local-infile=1 -u root -p < sql/load_mysql.sql
--
-- LOAD DATA LOCAL needs local_infile enabled on the server as well as the client.
-- The next line turns it on for this server (needs an admin account such as root).
SET GLOBAL local_infile = 1;

CREATE DATABASE IF NOT EXISTS olympics CHARACTER SET utf8mb4;
USE olympics;

SOURCE sql/schema.sql;

-- noc_regions.csv uses old Mac-style \r line endings.
LOAD DATA LOCAL INFILE 'noc_regions.csv'
INTO TABLE noc_regions
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY ''
LINES TERMINATED BY '\r'
IGNORE 1 LINES
(NOC, @region, @notes)
SET region = NULLIF(@region, 'NA'),
    notes  = NULLIF(@notes, '');

LOAD DATA LOCAL INFILE 'athlete_events.csv'
INTO TABLE athlete_events
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY ''
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(ID, Name, Sex, @Age, @Height, @Weight, Team, NOC, Games, Year, Season, City, Sport, Event, @Medal)
SET Age    = NULLIF(@Age, 'NA'),
    Height = NULLIF(@Height, 'NA'),
    Weight = NULLIF(@Weight, 'NA'),
    Medal  = NULLIF(@Medal, 'NA');

SELECT 'noc_regions' AS table_name, COUNT(*) AS row_count FROM noc_regions
UNION ALL
SELECT 'athlete_events', COUNT(*) FROM athlete_events;
