"""
Tests for the knowledge notes in chatbot/knowledge/ and their loader, chatbot/knowledge.py.

Every statistic in the notes has a Check: its exact text must appear in the note, and its SQL,
run through run_select(), must return the expected value, so changing either side fails a test.
test_every_number_in_the_notes_is_checked fails if a number in a note has no Check, unless it is
a year or is listed in NOT_STATISTICS. Counts of 1,000 or more are written with commas, so a
plain four-digit number in a note is always a year.

    python -m pytest -q
"""

import re
from collections import Counter
from functools import cache
from typing import NamedTuple

import pytest

from chatbot.db import run_select
from chatbot.knowledge import KNOWLEDGE_DIR, load_chunks


class Check(NamedTuple):
    file: str
    text: str  # exact text in the note; line breaks and repeated spaces are ignored
    sql: str
    expected: object


def women_share(year: int) -> str:
    return f"""SELECT ROUND(100.0 * COUNT(DISTINCT CASE WHEN sex = 'F' THEN athlete_id END)
                     / COUNT(DISTINCT athlete_id), 1)
               FROM summer_entries WHERE year = {year}"""


def first_year_women_share_reached(percent: int) -> str:
    return f"""WITH shares AS (
                   SELECT year, 100.0 * COUNT(DISTINCT CASE WHEN sex = 'F' THEN athlete_id END)
                                / COUNT(DISTINCT athlete_id) AS share
                   FROM summer_entries GROUP BY year)
               SELECT MIN(year) FROM shares WHERE share >= {percent}"""


def medal_table_country(position: int) -> str:
    return f"""SELECT country FROM country_medals WHERE country IS NOT NULL GROUP BY country
               ORDER BY SUM(medal = 'Gold') DESC, SUM(medal = 'Silver') DESC, SUM(medal = 'Bronze') DESC
               LIMIT 1 OFFSET {position - 1}"""


def athlete_medals(name_pattern: str, gold_only: bool = False) -> str:
    medal = "medal = 'Gold'" if gold_only else "medal IS NOT NULL"
    return f"SELECT COUNT(*) FROM summer_entries WHERE athlete LIKE '{name_pattern}' AND {medal}"


def medallist_rate(position: int, column: str) -> str:
    """Q7: countries with at least 1,000 athletes ranked by the share who won a medal."""
    return f"""SELECT {column} FROM (
                   SELECT country, COUNT(DISTINCT athlete_id) AS athletes,
                          ROUND(100.0 * COUNT(DISTINCT CASE WHEN medal IS NOT NULL THEN athlete_id END)
                                / COUNT(DISTINCT athlete_id), 1) AS pct
                   FROM summer_entries WHERE country IS NOT NULL GROUP BY country
                   HAVING COUNT(DISTINCT athlete_id) >= 1000)
               ORDER BY pct DESC LIMIT 1 OFFSET {position - 1}"""


def usa_gold_share(sport: str, column: str) -> str:
    """Q9: the USA's golds in a sport, the sport's golds and the USA's share."""
    return f"""SELECT {column} FROM (
                   SELECT SUM(country = 'USA') AS usa, COUNT(*) AS total,
                          ROUND(100.0 * SUM(country = 'USA') / COUNT(*), 1) AS pct
                   FROM country_medals
                   WHERE medal = 'Gold' AND country IS NOT NULL AND sport = '{sport}')"""


def top_gold_share(position: int, column: str) -> str:
    """Q9: for sports with at least 50 golds, the country with the most golds and its share."""
    return f"""WITH golds AS (
                   SELECT sport, country, COUNT(*) AS gold FROM country_medals
                   WHERE medal = 'Gold' AND country IS NOT NULL GROUP BY sport, country),
               ranked AS (
                   SELECT sport, country, gold, SUM(gold) OVER (PARTITION BY sport) AS total,
                          RANK() OVER (PARTITION BY sport ORDER BY gold DESC) AS position
                   FROM golds)
               SELECT {column} FROM (
                   SELECT sport, country, ROUND(100.0 * gold / total, 1) AS pct
                   FROM ranked WHERE position = 1 AND total >= 50)
               ORDER BY pct DESC LIMIT 1 OFFSET {position - 1}"""


def tallest_sport(column: str, offset: int = 0, order: str = "DESC") -> str:
    """Q10: sports with at least 100 medallists whose height and weight are both known."""
    return f"""SELECT {column} FROM (
                   SELECT sport, ROUND(AVG(height_cm), 1) AS height, ROUND(AVG(weight_kg), 1) AS weight,
                          AVG(height_cm) AS exact_height
                   FROM (SELECT DISTINCT athlete_id, sport, height_cm, weight_kg FROM summer_entries
                         WHERE medal IS NOT NULL AND height_cm IS NOT NULL AND weight_kg IS NOT NULL)
                   GROUP BY sport HAVING COUNT(DISTINCT athlete_id) >= 100)
               ORDER BY exact_height {order} LIMIT 1 OFFSET {offset}"""


TOP_GOLD_NATIONS = """
    WITH golds AS (
        SELECT year, country, COUNT(*) AS gold FROM country_medals
        WHERE medal = 'Gold' AND country IS NOT NULL GROUP BY year, country),
    ranked AS (SELECT year, country, gold, RANK() OVER (PARTITION BY year ORDER BY gold DESC) AS position FROM golds)
    SELECT {column} FROM ranked WHERE position = 1 {condition}"""


def top_gold_nation(year: int, column: str) -> str:
    return TOP_GOLD_NATIONS.format(column=column, condition=f"AND year = {year}")


def times_top_gold_nation(country: str) -> str:
    return TOP_GOLD_NATIONS.format(column="COUNT(*)", condition=f"AND country = '{country}'")


def average_age(condition: str) -> str:
    return f"SELECT ROUND(AVG(age), 1) FROM summer_entries WHERE age IS NOT NULL AND {condition}"


def india_medals(condition: str = "1 = 1") -> str:
    return f"SELECT COUNT(*) FROM country_medals WHERE country = 'India' AND {condition}"


INDIA_MEDALS_BY_YEAR = "SELECT year, COUNT(*) AS medals FROM country_medals WHERE country = 'India' GROUP BY year"
RELAY_2008 = """year = 2008 AND country = 'USA' AND medal = 'Gold'
                AND event = 'Swimming Men''s 4 x 100 metres Freestyle Relay'"""
ALL_DUPLICATES = "SELECT (SELECT COUNT(*) FROM athlete_events) - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM athlete_events))"
WINTER_DUPLICATES = """SELECT (SELECT COUNT(*) FROM athlete_events WHERE Season = 'Winter')
                            - (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM athlete_events WHERE Season = 'Winter'))"""
OFFICIAL_EDITIONS = "SELECT COUNT(DISTINCT year) FROM summer_entries WHERE year <> 1906"
GAMES_YEARS = "SELECT COUNT(DISTINCT year) FROM summer_entries"
ATHLETES = "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries"
SUMMER_ENTRIES = "SELECT COUNT(*) FROM summer_entries"
WINTER_ROWS = "SELECT COUNT(*) FROM athlete_events WHERE Season = 'Winter'"
USA_TOTAL = "SELECT COUNT(*) FROM country_medals WHERE country = 'USA'"


def region(noc: str) -> str:
    return f"SELECT region FROM noc_regions WHERE NOC = '{noc}'"


def city_years(city: str) -> str:
    return f"SELECT GROUP_CONCAT(year) FROM (SELECT DISTINCT year FROM summer_entries WHERE city = '{city}' ORDER BY year)"


def medals_by_noc(noc: str, condition: str = "1 = 1") -> str:
    return f"SELECT COUNT(*) FROM country_medals WHERE noc = '{noc}' AND {condition}"


def ioa_athletes(year: int) -> str:
    return f"SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE noc = 'IOA' AND year = {year}"


CHECKS = [
    # dataset.md
    Check("dataset.md", "has 271,116 rows", "SELECT COUNT(*) FROM athlete_events", 271_116),
    Check("dataset.md", "has 230 rows", "SELECT COUNT(*) FROM noc_regions", 230),
    Check("dataset.md", "it has 221,167 rows", SUMMER_ENTRIES, 221_167),
    Check("dataset.md", "221,167 Summer entries", SUMMER_ENTRIES, 221_167),
    Check("dataset.md", "48,564 Winter Games rows", WINTER_ROWS, 48_564),
    Check("dataset.md", "The latest Games in the data are Rio 2016", "SELECT MAX(Year) FROM athlete_events", 2016),
    Check("dataset.md", "29 Games years", GAMES_YEARS, 29),
    Check("dataset.md", "28 official editions", OFFICIAL_EDITIONS, 28),
    Check("dataset.md", "28 official Summer Games rather than 29", OFFICIAL_EDITIONS, 28),
    Check("dataset.md", "28 official Summer Games rather than 29", GAMES_YEARS, 29),
    Check("dataset.md", "841 athletes competed in 74 events",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 1906", 841),
    Check("dataset.md", "841 athletes competed in 74 events",
          "SELECT COUNT(DISTINCT event) FROM summer_entries WHERE year = 1906", 74),
    Check("dataset.md", "the 224 medals awarded there", "SELECT COUNT(*) FROM country_medals WHERE year = 1906", 224),
    Check("dataset.md", "all-time total of 2,545 medals", USA_TOTAL, 2545),
    Check("dataset.md", "includes 23 medals won in 1906",
          "SELECT COUNT(*) FROM country_medals WHERE country = 'USA' AND year = 1906", 23),
    Check("dataset.md", "where 3,189 athletes competed in 145 events",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 1956 AND city = 'Melbourne'", 3189),
    Check("dataset.md", "where 3,189 athletes competed in 145 events",
          "SELECT COUNT(DISTINCT event) FROM summer_entries WHERE year = 1956 AND city = 'Melbourne'", 145),
    Check("dataset.md", "where 158 athletes competed in 6 equestrian events",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 1956 AND city = 'Stockholm'", 158),
    Check("dataset.md", "where 158 athletes competed in 6 equestrian events",
          "SELECT COUNT(DISTINCT event) FROM summer_entries WHERE year = 1956 AND city = 'Stockholm'", 6),
    Check("dataset.md", "the equestrian events were held in Stockholm",
          "SELECT GROUP_CONCAT(DISTINCT sport) FROM summer_entries WHERE year = 1956 AND city = 'Stockholm'", "Equestrianism"),
    Check("dataset.md", "4.1% have no age", "SELECT ROUND(100.0 * SUM(age IS NULL) / COUNT(*), 1) FROM summer_entries", 4.1),
    Check("dataset.md", "22.8% have no height",
          "SELECT ROUND(100.0 * SUM(height_cm IS NULL) / COUNT(*), 1) FROM summer_entries", 22.8),
    Check("dataset.md", "23.7% have no weight",
          "SELECT ROUND(100.0 * SUM(weight_kg IS NULL) / COUNT(*), 1) FROM summer_entries", 23.7),
    Check("dataset.md", "1,385 rows that exactly duplicate another row", ALL_DUPLICATES, 1385),
    Check("dataset.md", "all of them are Summer Games rows", WINTER_DUPLICATES, 0),
    Check("dataset.md", "the 222,552 Summer rows in the CSV",
          "SELECT COUNT(*) FROM athlete_events WHERE Season = 'Summer'", 222_552),
    Check("dataset.md", "Athina (1896, 1906 and 2004)", city_years("Athina"), "1896,1906,2004"),
    Check("dataset.md", "Moskva (1980)", city_years("Moskva"), "1980"),
    Check("dataset.md", "Roma (1960)", city_years("Roma"), "1960"),
    Check("dataset.md", "Antwerpen (1920)", city_years("Antwerpen"), "1920"),
    Check("dataset.md", "23 different host cities", "SELECT COUNT(DISTINCT city) FROM summer_entries", 23),

    # counting_rules.md
    Check("counting_rules.md", "48,564 Winter Games rows", WINTER_ROWS, 48_564),
    Check("counting_rules.md", "1,385 exact duplicate rows", ALL_DUPLICATES, 1385),
    Check("counting_rules.md", "all of them in the Summer Games", WINTER_DUPLICATES, 0),
    Check("counting_rules.md", "That leaves 221,167 Summer entries", SUMMER_ENTRIES, 221_167),
    Check("counting_rules.md", "has 7 athlete rows", f"SELECT COUNT(*) FROM summer_entries WHERE {RELAY_2008}", 7),
    Check("counting_rules.md", "counts as 1 gold medal for the USA",
          f"SELECT COUNT(*) FROM country_medals WHERE {RELAY_2008}", 1),
    Check("counting_rules.md", "would be 5,002 medals",
          "SELECT COUNT(*) FROM summer_entries WHERE country = 'USA' AND medal IS NOT NULL", 5002),
    Check("counting_rules.md", "instead of 2,545", USA_TOTAL, 2545),
    Check("counting_rules.md", "Soviet Union (URS) and the 1992 Unified Team (EUN) count as Russia",
          "SELECT GROUP_CONCAT(DISTINCT region) FROM noc_regions WHERE NOC IN ('URS', 'EUN')", "Russia"),
    Check("counting_rules.md", "East Germany (GDR) and West Germany (FRG) count as Germany",
          "SELECT GROUP_CONCAT(DISTINCT region) FROM noc_regions WHERE NOC IN ('GDR', 'FRG')", "Germany"),
    Check("counting_rules.md", "Hong Kong (HKG) counts as China", region("HKG"), "China"),
    Check("counting_rules.md", "Czechoslovakia (TCH) counts as Czech Republic", region("TCH"), "Czech Republic"),
    Check("counting_rules.md", "Yugoslavia (YUG) counts as Serbia", region("YUG"), "Serbia"),
    Check("counting_rules.md", "Russia's 1,577 medals", "SELECT COUNT(*) FROM country_medals WHERE country = 'Russia'", 1577),
    Check("counting_rules.md", "include 1,005 won by the Soviet Union", medals_by_noc("URS"), 1005),
    Check("counting_rules.md", "112 by the Unified Team", medals_by_noc("EUN"), 112),
    Check("counting_rules.md", "Germany's 1,392 medals", "SELECT COUNT(*) FROM country_medals WHERE country = 'Germany'", 1392),
    Check("counting_rules.md", "409 won by East Germany", medals_by_noc("GDR"), 409),
    Check("counting_rules.md", "204 by West Germany", medals_by_noc("FRG"), 204),
    Check("counting_rules.md", "Singapore competes under the NOC code SGP",
          "SELECT COUNT(*) > 0 FROM summer_entries WHERE noc = 'SGP' AND team = 'Singapore'", 1),
    Check("counting_rules.md", "noc_regions lists Singapore as SIN",
          "SELECT GROUP_CONCAT(NOC) FROM noc_regions WHERE region = 'Singapore'", "SIN"),
    Check("counting_rules.md", "its 5 Summer medals", medals_by_noc("SGP"), 5),
    Check("counting_rules.md", "including 1 gold", medals_by_noc("SGP", "medal = 'Gold'"), 1),
    Check("counting_rules.md", "none of which won a medal",
          "SELECT COUNT(*) FROM country_medals WHERE noc IN ('ROT', 'TUV', 'UNK')", 0),
    Check("counting_rules.md", 'Bolivia is spelled "Boliva"', region("BOL"), "Boliva"),
    Check("counting_rules.md", 'Trinidad and Tobago is just "Trinidad"', region("TTO"), "Trinidad"),
    Check("counting_rules.md", 'The United States is "USA"', region("USA"), "USA"),
    Check("counting_rules.md", 'Great Britain is "UK"', region("GBR"), "UK"),
    Check("counting_rules.md", 'grouped as "Individual Olympic Athletes"', region("IOA"), "Individual Olympic Athletes"),
    Check("counting_rules.md", "counts once for Denmark and once for Sweden",
          """SELECT GROUP_CONCAT(country) FROM (SELECT country FROM country_medals
             WHERE team = 'Denmark/Sweden' AND year = 1900 AND medal = 'Gold' ORDER BY country)""", "Denmark,Sweden"),

    # findings.md: How big the Summer Olympics are (Q1)
    Check("findings.md", "28 official editions", OFFICIAL_EDITIONS, 28),
    Check("findings.md", "23 host cities", "SELECT COUNT(DISTINCT city) FROM summer_entries", 23),
    Check("findings.md", "52 sports", "SELECT COUNT(DISTINCT sport) FROM summer_entries", 52),
    Check("findings.md", "651 events", "SELECT COUNT(DISTINCT event) FROM summer_entries", 651),
    Check("findings.md", "205 nations", "SELECT COUNT(DISTINCT country) FROM summer_entries", 205),
    Check("findings.md", "116,776 athletes", ATHLETES, 116_776),
    # All-time medal table (Q2)
    Check("findings.md", "The USA leads the all-time Summer Olympic medal table", medal_table_country(1), "USA"),
    Check("findings.md", "1,035 gold", "SELECT COUNT(*) FROM country_medals WHERE country = 'USA' AND medal = 'Gold'", 1035),
    Check("findings.md", "2,545 medals in total", USA_TOTAL, 2545),
    Check("findings.md", "802 silver", "SELECT COUNT(*) FROM country_medals WHERE country = 'USA' AND medal = 'Silver'", 802),
    Check("findings.md", "708 bronze", "SELECT COUNT(*) FROM country_medals WHERE country = 'USA' AND medal = 'Bronze'", 708),
    Check("findings.md", "Russia is second", medal_table_country(2), "Russia"),
    Check("findings.md", "592 golds", "SELECT COUNT(*) FROM country_medals WHERE country = 'Russia' AND medal = 'Gold'", 592),
    Check("findings.md", "1,577 medals", "SELECT COUNT(*) FROM country_medals WHERE country = 'Russia'", 1577),
    Check("findings.md", "Germany is third", medal_table_country(3), "Germany"),
    Check("findings.md", "444 golds", "SELECT COUNT(*) FROM country_medals WHERE country = 'Germany' AND medal = 'Gold'", 444),
    Check("findings.md", "1,392 medals", "SELECT COUNT(*) FROM country_medals WHERE country = 'Germany'", 1392),
    # India's best Games (Q3) and India's overall record
    Check("findings.md", "best Summer Games was London 2012",
          f"SELECT year FROM ({INDIA_MEDALS_BY_YEAR}) ORDER BY medals DESC LIMIT 1", 2012),
    Check("findings.md", "London 2012, with 6 medals", f"SELECT MAX(medals) FROM ({INDIA_MEDALS_BY_YEAR})", 6),
    Check("findings.md", "next best was Beijing 2008",
          f"SELECT year FROM ({INDIA_MEDALS_BY_YEAR}) ORDER BY medals DESC LIMIT 1 OFFSET 1", 2008),
    Check("findings.md", "Beijing 2008 with 3 medals",
          f"SELECT medals FROM ({INDIA_MEDALS_BY_YEAR}) ORDER BY medals DESC LIMIT 1 OFFSET 1", 3),
    Check("findings.md", "largest team was at Rio 2016",
          """SELECT year FROM summer_entries WHERE country = 'India' GROUP BY year
             ORDER BY COUNT(DISTINCT athlete_id) DESC LIMIT 1""", 2016),
    Check("findings.md", "Rio 2016, with 112 athletes",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE country = 'India' AND year = 2016", 112),
    Check("findings.md", "India won only 2 medals there", india_medals("year = 2016"), 2),
    Check("findings.md", "India has won 28 Summer Olympic medals", india_medals(), 28),
    Check("findings.md", "9 gold, 7 silver and 12 bronze", india_medals("medal = 'Gold'"), 9),
    Check("findings.md", "9 gold, 7 silver and 12 bronze", india_medals("medal = 'Silver'"), 7),
    Check("findings.md", "9 gold, 7 silver and 12 bronze", india_medals("medal = 'Bronze'"), 12),
    Check("findings.md", "from 871 athletes",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE country = 'India'", 871),
    Check("findings.md", "competed at 24 Games", "SELECT COUNT(DISTINCT year) FROM summer_entries WHERE country = 'India'", 24),
    Check("findings.md", "Hockey is India's strongest sport",
          "SELECT sport FROM country_medals WHERE country = 'India' GROUP BY sport ORDER BY COUNT(*) DESC LIMIT 1", "Hockey"),
    Check("findings.md", "with 11 medals, including 8 golds", india_medals("sport = 'Hockey'"), 11),
    Check("findings.md", "with 11 medals, including 8 golds", india_medals("sport = 'Hockey' AND medal = 'Gold'"), 8),
    Check("findings.md", "from 1928 to 1956, then again in 1964 and 1980",
          """SELECT GROUP_CONCAT(year) FROM (SELECT year FROM country_medals
             WHERE country = 'India' AND sport = 'Hockey' AND medal = 'Gold' ORDER BY year)""",
          "1928,1932,1936,1948,1952,1956,1964,1980"),
    Check("findings.md", "India's only gold outside hockey is Abhinav Bindra's",
          """SELECT GROUP_CONCAT(athlete) FROM summer_entries
             WHERE country = 'India' AND medal = 'Gold' AND sport <> 'Hockey'""", "Abhinav Bindra"),
    # Women's share of athletes (Q5) and milestones
    Check("findings.md", "0% of athletes in 1896", women_share(1896), 0.0),
    Check("findings.md", "10.1% in 1948", women_share(1948), 10.1),
    Check("findings.md", "45.0% in 2016", women_share(2016), 45.0),
    Check("findings.md", "5,034 of the 11,179 athletes",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 2016 AND sex = 'F'", 5034),
    Check("findings.md", "5,034 of the 11,179 athletes",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 2016", 11_179),
    Check("findings.md", "Women first competed at the Paris 1900 Games", "SELECT MIN(year) FROM summer_entries WHERE sex = 'F'", 1900),
    Check("findings.md", "23 of the 1,224 athletes were women",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 1900 AND sex = 'F'", 23),
    Check("findings.md", "23 of the 1,224 athletes were women",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 1900", 1224),
    Check("findings.md", "(1.9%)", women_share(1900), 1.9),
    Check("findings.md", "women won medals at those Games too",
          "SELECT COUNT(*) > 0 FROM summer_entries WHERE year = 1900 AND sex = 'F' AND medal IS NOT NULL", 1),
    Check("findings.md", "first reached 10% in 1932", first_year_women_share_reached(10), 1932),
    Check("findings.md", "20% in 1976", first_year_women_share_reached(20), 1976),
    Check("findings.md", "30% in 1996", first_year_women_share_reached(30), 1996),
    Check("findings.md", "40% in 2004", first_year_women_share_reached(40), 2004),
    Check("findings.md", "28,851 different women",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE sex = 'F'", 28_851),
    # Most decorated Olympians (Q6)
    Check("findings.md", "Michael Phelps of the USA is the most decorated Summer Olympian",
          """SELECT MAX(athlete) FROM summer_entries WHERE medal IS NOT NULL
             GROUP BY athlete_id ORDER BY COUNT(*) DESC LIMIT 1""", "Michael Fred Phelps, II"),
    Check("findings.md", "with 28 medals, 23 of them gold", athlete_medals("%Michael%Phelps%"), 28),
    Check("findings.md", "with 28 medals, 23 of them gold", athlete_medals("%Michael%Phelps%", gold_only=True), 23),
    Check("findings.md", "all in swimming",
          "SELECT GROUP_CONCAT(DISTINCT sport) FROM summer_entries WHERE athlete LIKE '%Michael%Phelps%' AND medal IS NOT NULL",
          "Swimming"),
    Check("findings.md", "Next come three Soviet gymnasts",
          """SELECT GROUP_CONCAT(athlete, '; ') FROM (
                 SELECT MAX(athlete) AS athlete FROM summer_entries WHERE medal IS NOT NULL GROUP BY athlete_id
                 ORDER BY COUNT(*) DESC, SUM(medal = 'Gold') DESC LIMIT 3 OFFSET 1)""",
          "Larysa Semenivna Latynina (Diriy-); Nikolay Yefimovich Andrianov; Borys Anfiyanovych Shakhlin"),
    Check("findings.md", "Larysa Latynina with 18 medals (9 gold)", athlete_medals("%Larysa%Latynina%"), 18),
    Check("findings.md", "Larysa Latynina with 18 medals (9 gold)", athlete_medals("%Larysa%Latynina%", gold_only=True), 9),
    Check("findings.md", "Nikolay Andrianov with 15 medals (7 gold)", athlete_medals("%Nikolay%Andrianov%"), 15),
    Check("findings.md", "Nikolay Andrianov with 15 medals (7 gold)", athlete_medals("%Nikolay%Andrianov%", gold_only=True), 7),
    Check("findings.md", "Borys Shakhlin with 13 medals (7 gold)", athlete_medals("%Borys%Shakhlin%"), 13),
    Check("findings.md", "Borys Shakhlin with 13 medals (7 gold)", athlete_medals("%Borys%Shakhlin%", gold_only=True), 7),
    # Countries that turn athletes into medallists (Q7)
    Check("findings.md", "Russia turns the largest share", medallist_rate(1, "country"), "Russia"),
    Check("findings.md", "48.6% of its 4,486 athletes", medallist_rate(1, "pct"), 48.6),
    Check("findings.md", "48.6% of its 4,486 athletes", medallist_rate(1, "athletes"), 4486),
    Check("findings.md", "The USA is second with 42.2%", medallist_rate(2, "country"), "USA"),
    Check("findings.md", "42.2% of its 7,970 athletes", medallist_rate(2, "pct"), 42.2),
    Check("findings.md", "42.2% of its 7,970 athletes", medallist_rate(2, "athletes"), 7970),
    Check("findings.md", "Germany third with 36.1%", medallist_rate(3, "country"), "Germany"),
    Check("findings.md", "Germany third with 36.1%", medallist_rate(3, "pct"), 36.1),
    # USA dominance in swimming and athletics (Q9)
    Check("findings.md", "43.9% of all Summer Olympic swimming golds (246 of 561)", usa_gold_share("Swimming", "pct"), 43.9),
    Check("findings.md", "43.9% of all Summer Olympic swimming golds (246 of 561)", usa_gold_share("Swimming", "usa"), 246),
    Check("findings.md", "43.9% of all Summer Olympic swimming golds (246 of 561)", usa_gold_share("Swimming", "total"), 561),
    Check("findings.md", "34.4% of all athletics golds (344 of 1,000)", usa_gold_share("Athletics", "pct"), 34.4),
    Check("findings.md", "34.4% of all athletics golds (344 of 1,000)", usa_gold_share("Athletics", "usa"), 344),
    Check("findings.md", "34.4% of all athletics golds (344 of 1,000)", usa_gold_share("Athletics", "total"), 1000),
    Check("findings.md", "Swimming is the sport where a single country holds the largest share",
          top_gold_share(1, "sport"), "Swimming"),
    Check("findings.md", "the USA in diving with 39.3%", top_gold_share(2, "sport || ' ' || country"), "Diving USA"),
    Check("findings.md", "the USA in diving with 39.3%", top_gold_share(2, "pct"), 39.3),
    # Tallest medallists (Q10)
    Check("findings.md", "Basketball medallists are the tallest", tallest_sport("sport"), "Basketball"),
    Check("findings.md", "averaging 192.1 cm and 86.7 kg", tallest_sport("height"), 192.1),
    Check("findings.md", "averaging 192.1 cm and 86.7 kg", tallest_sport("weight"), 86.7),
    Check("findings.md", "Volleyball medallists come next at 186.4 cm", tallest_sport("sport || ' ' || height", 1),
          "Volleyball 186.4"),
    Check("findings.md", "then water polo medallists at 184.8 cm", tallest_sport("sport || ' ' || height", 2),
          "Water Polo 184.8"),
    Check("findings.md", "gymnastics medallists are the shortest at 160.9 cm", tallest_sport("sport || ' ' || height", order="ASC"),
          "Gymnastics 160.9"),
    # Top gold-medal nation at selected Games (Q4)
    Check("findings.md", "At Moscow 1980, Russia", top_gold_nation(1980, "country"), "Russia"),
    Check("findings.md", "won the most golds with 80", top_gold_nation(1980, "gold"), 80),
    Check("findings.md", "only 80 nations took part", "SELECT COUNT(DISTINCT country) FROM summer_entries WHERE year = 1980", 80),
    Check("findings.md", "the USA won 82 golds", top_gold_nation(1984, "country || ' ' || gold"), "USA 82"),
    Check("findings.md", "China topped the table once", times_top_gold_nation("China"), 1),
    Check("findings.md", "Beijing 2008, with 51 golds", top_gold_nation(2008, "country || ' ' || gold"), "China 51"),
    Check("findings.md", "the USA was top again at Rio 2016 with 46 golds", top_gold_nation(2016, "country || ' ' || gold"), "USA 46"),
    Check("findings.md", "the USA topped the gold table at 17 of the 29 Games", times_top_gold_nation("USA"), 17),
    Check("findings.md", "the USA topped the gold table at 17 of the 29 Games", GAMES_YEARS, 29),
    Check("findings.md", "and Russia at 6", times_top_gold_nation("Russia"), 6),
    # Age of medallists (Q8)
    Check("findings.md", "medal-winning entries average 25.9 years", average_age("medal IS NOT NULL"), 25.9),
    Check("findings.md", "25.5 years for entries without a medal", average_age("medal IS NULL"), 25.5),
    Check("findings.md", "gold and bronze medallists average 25.9 years", average_age("medal = 'Gold'"), 25.9),
    Check("findings.md", "gold and bronze medallists average 25.9 years", average_age("medal = 'Bronze'"), 25.9),
    Check("findings.md", "silver medallists 26.0 years", average_age("medal = 'Silver'"), 26.0),
    Check("findings.md", "The youngest medallist in the data was 10 years old",
          "SELECT MIN(age) FROM summer_entries WHERE medal IS NOT NULL", 10),
    Check("findings.md", "the oldest was 73", "SELECT MAX(age) FROM summer_entries WHERE medal IS NOT NULL", 73),

    # glossary.md
    Check("glossary.md", "230 different NOC codes", "SELECT COUNT(DISTINCT noc) FROM summer_entries", 230),
    Check("glossary.md", "205 countries", "SELECT COUNT(DISTINCT country) FROM summer_entries", 205),
    Check("glossary.md", "29 Summer Games years", GAMES_YEARS, 29),
    Check("glossary.md", "28 official editions", OFFICIAL_EDITIONS, 28),
    Check("glossary.md", "No Games were held in 1916, 1940 or 1944",
          "SELECT COUNT(*) FROM summer_entries WHERE year IN (1916, 1940, 1944)", 0),
    Check("glossary.md", "Athletics Men's Marathon",
          "SELECT COUNT(DISTINCT event) FROM summer_entries WHERE event = 'Athletics Men''s Marathon'", 1),
    Check("glossary.md", "52 sports and 651 different events", "SELECT COUNT(DISTINCT sport) FROM summer_entries", 52),
    Check("glossary.md", "52 sports and 651 different events", "SELECT COUNT(DISTINCT event) FROM summer_entries", 651),
    Check("glossary.md", "116,776", ATHLETES, 116_776),
    Check("glossary.md", "24,584 are medallists",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE medal IS NOT NULL", 24_584),
    Check("glossary.md", "the official count of Summer Games is 28", OFFICIAL_EDITIONS, 28),
    Check("glossary.md", "841 athletes in 74 events",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE year = 1906", 841),
    Check("glossary.md", "841 athletes in 74 events",
          "SELECT COUNT(DISTINCT event) FROM summer_entries WHERE year = 1906", 74),
    Check("glossary.md", "their 224 medals", "SELECT COUNT(*) FROM country_medals WHERE year = 1906", 224),
    Check("glossary.md", "competed at the 1992 Barcelona Games",
          "SELECT GROUP_CONCAT(DISTINCT year) FROM summer_entries WHERE noc = 'EUN'", "1992"),
    Check("glossary.md", "the Unified Team counts as Russia", region("EUN"), "Russia"),
    Check("glossary.md", "its 112 medals, including 45 golds", medals_by_noc("EUN"), 112),
    Check("glossary.md", "its 112 medals, including 45 golds", medals_by_noc("EUN", "medal = 'Gold'"), 45),
    Check("glossary.md", "A total of 475 athletes",
          "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE noc = 'EUN'", 475),
    Check("glossary.md", 'both the team and the country are labelled "Individual Olympic Athletes"',
          "SELECT GROUP_CONCAT(DISTINCT team || '|' || country) FROM summer_entries WHERE noc = 'IOA'",
          "Individual Olympic Athletes|Individual Olympic Athletes"),
    Check("glossary.md", "They appear at four Games",
          "SELECT COUNT(DISTINCT year) FROM summer_entries WHERE noc = 'IOA'", 4),
    Check("glossary.md", "in 1992, 58 athletes from Yugoslavia", ioa_athletes(1992), 58),
    Check("glossary.md", "in 2000, 4 athletes from East Timor", ioa_athletes(2000), 4),
    Check("glossary.md", "in 2012, 4 athletes from the Netherlands Antilles and South Sudan", ioa_athletes(2012), 4),
    Check("glossary.md", "in 2016, 9 athletes from Kuwait", ioa_athletes(2016), 9),
    Check("glossary.md", "won 5 medals, all in shooting", medals_by_noc("IOA"), 5),
    Check("glossary.md", "won 5 medals, all in shooting",
          "SELECT GROUP_CONCAT(DISTINCT sport) FROM country_medals WHERE noc = 'IOA'", "Shooting"),
    Check("glossary.md", "including 1 gold at Rio 2016", medals_by_noc("IOA", "medal = 'Gold' AND year = 2016"), 1),
    Check("glossary.md", "competed under the Olympic flag at Rio 2016",
          "SELECT GROUP_CONCAT(DISTINCT year) FROM summer_entries WHERE noc = 'ROT'", "2016"),
    Check("glossary.md", "10 athletes in 3 sports", "SELECT COUNT(DISTINCT athlete_id) FROM summer_entries WHERE noc = 'ROT'", 10),
    Check("glossary.md", "10 athletes in 3 sports", "SELECT COUNT(DISTINCT sport) FROM summer_entries WHERE noc = 'ROT'", 3),
    Check("glossary.md", "athletics, judo and swimming",
          "SELECT GROUP_CONCAT(sport) FROM (SELECT DISTINCT sport FROM summer_entries WHERE noc = 'ROT' ORDER BY sport)",
          "Athletics,Judo,Swimming"),
    Check("glossary.md", "The Refugee Olympic Athletes did not win a medal", medals_by_noc("ROT"), 0),
    Check("glossary.md", "564 names in the Summer data belong to more than one athlete_id",
          "SELECT COUNT(*) FROM (SELECT athlete FROM summer_entries GROUP BY athlete HAVING COUNT(DISTINCT athlete_id) > 1)", 564),
    Check("glossary.md", "Michael Phelps's 28 medals", athlete_medals("%Michael%Phelps%"), 28),
]

# Numbers in the notes that are names, labels or thresholds, not statistics.
NOT_STATISTICS = {
    "dataset.md": ["120 years of Olympic history"],
    "counting_rules.md": ["4 x 100 metres"],
    "findings.md": ["at least 1,000 Summer Olympians", "at least 50 golds", "at least 100 such medallists",
                    "10 metre air rifle"],
    "project.md": ["120 years", "MySQL 8", "top 10", "top 15"],
}

NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")  # skips digits inside words such as Q10
YEAR = re.compile(r"(18|19|20)\d\d")
URL = re.compile(r"https?://\S+")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
NOTE_FILES = sorted(path.name for path in KNOWLEDGE_DIR.glob("*.md"))
CHUNKS = load_chunks()


def normalise(text: str) -> str:
    return " ".join(text.split())


@cache
def note_text(file: str) -> str:
    return normalise(HTML_COMMENT.sub("", (KNOWLEDGE_DIR / file).read_text(encoding="utf-8")))


@cache
def query_value(sql: str):
    return run_select(sql, timeout_s=30).rows.iat[0, 0]


# Every statistic matches the data

@pytest.mark.parametrize("check", CHECKS, ids=[f"{c.file}: {c.text}" for c in CHECKS])
def test_statistic_is_in_the_note_and_matches_the_data(check):
    assert normalise(check.text) in note_text(check.file), f"text not found in {check.file}"
    value = query_value(check.sql)
    if isinstance(check.expected, float):
        assert value == pytest.approx(check.expected)
    else:
        assert value == check.expected


@pytest.mark.parametrize("file", NOTE_FILES)
def test_every_number_in_the_notes_is_checked(file):
    text = URL.sub(" ", note_text(file))
    covered = [False] * len(text)  # characters inside the text of a Check or a NOT_STATISTICS phrase
    for phrase in [c.text for c in CHECKS if c.file == file] + NOT_STATISTICS.get(file, []):
        for match in re.finditer(re.escape(normalise(phrase)), text):
            covered[match.start():match.end()] = [True] * (match.end() - match.start())
    unchecked = [match.group() for match in NUMBER.finditer(text)
                 if not YEAR.fullmatch(match.group()) and not all(covered[match.start():match.end()])]
    assert unchecked == [], f"numbers in {file} without a Check: {unchecked}"


# The loader splits the notes into retrievable chunks

def test_chunk_ids_are_unique():
    duplicates = [id_ for id_, n in Counter(c.id for c in CHUNKS).items() if n > 1]
    assert duplicates == []


def test_no_chunk_is_empty():
    for chunk in CHUNKS:
        heading_line, _, body = chunk.text.partition("\n")
        assert heading_line == f"{chunk.title} — {chunk.heading}"
        assert body.strip(), chunk.id


@pytest.mark.parametrize("chunk", CHUNKS, ids=[c.id for c in CHUNKS])
def test_chunk_has_30_to_200_words(chunk):
    assert 30 <= len(chunk.text.split()) <= 200


def test_every_file_has_at_least_3_chunks():
    counts = Counter(c.file for c in CHUNKS)
    assert NOTE_FILES and all(counts[file] >= 3 for file in NOTE_FILES), counts


def test_chunks_have_no_html_comments_or_cross_references():
    for chunk in CHUNKS:
        assert "<!--" not in chunk.text, chunk.id
        assert not re.search(r"\b(as above|see above|as below|see below|previous section|next section)\b",
                             chunk.text, re.IGNORECASE), chunk.id


def test_load_chunks_example_id():
    assert "counting_rules#team-medals-count-once" in {c.id for c in CHUNKS}
