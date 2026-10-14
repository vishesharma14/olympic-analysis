"""
Tests for chatbot/db.py: the views reproduce the verified findings in sql/README.md, and
run_select() refuses anything that is not a single read-only SELECT.

    pip install -r requirements-dev.txt
    python -m pytest -q
"""

import sqlite3
import time
from contextlib import closing

import pytest

from chatbot import db
from chatbot.db import SQLGuardError, ensure_database, run_select

SUMMER_ENTRIES_COLUMNS = [
    "athlete_id", "athlete", "sex", "age", "height_cm", "weight_kg", "team",
    "noc", "country", "year", "city", "sport", "event", "medal",
]

REJECTED_WRITES = {
    "delete": "DELETE FROM noc_regions",
    "drop_table": "DROP TABLE noc_regions",
    "drop_view": "DROP VIEW summer_entries",
    "insert": "INSERT INTO noc_regions (NOC, region) VALUES ('XXX', 'Nowhere')",
    "update": "UPDATE noc_regions SET region = 'Nowhere'",
    "pragma_read": "PRAGMA table_info(noc_regions)",
    "pragma_write": "PRAGMA user_version = 1",
    "attach": "ATTACH DATABASE ':memory:' AS scratch",
}


@pytest.fixture(scope="module", autouse=True)
def database():
    """Builds the database before the first test (about 20 seconds the first time, then reused)."""
    return ensure_database()


def scalar(sql: str):
    return run_select(sql).rows.iat[0, 0]


# The views reproduce the findings in sql/README.md

def test_usa_has_1035_golds_and_2545_medals():
    result = run_select("""
        SELECT SUM(medal = 'Gold') AS gold, COUNT(*) AS total
        FROM country_medals
        WHERE country = 'USA'
    """)
    assert result.rows.to_dict("records") == [{"gold": 1035, "total": 2545}]


def test_india_best_games_is_2012_with_6_medals():
    result = run_select("""
        SELECT year, COUNT(*) AS medals
        FROM country_medals
        WHERE country = 'India'
        GROUP BY year
        ORDER BY medals DESC, year
        LIMIT 2
    """)
    best, next_best = result.rows.to_dict("records")
    assert best == {"year": 2012, "medals": 6}
    assert next_best["medals"] < 6


def test_michael_phelps_has_28_medals_23_gold():
    result = run_select("""
        SELECT athlete_id, COUNT(*) AS medals, SUM(medal = 'Gold') AS gold
        FROM summer_entries
        WHERE athlete LIKE '%Michael%Phelps%' AND medal IS NOT NULL
        GROUP BY athlete_id
    """)
    assert result.rows[["medals", "gold"]].to_dict("records") == [{"medals": 28, "gold": 23}]


def test_summer_entries_has_116776_athletes():
    assert scalar("SELECT COUNT(DISTINCT athlete_id) FROM summer_entries") == 116_776


def test_summer_entries_drops_the_1385_duplicate_rows():
    summer_rows = scalar("SELECT COUNT(*) FROM athlete_events WHERE Season = 'Summer'")
    assert summer_rows - scalar("SELECT COUNT(*) FROM summer_entries") == 1_385


def test_basketball_medallists_are_tallest_at_192_cm():
    result = run_select("""
        SELECT sport, AVG(height_cm) AS avg_height_cm
        FROM (
            SELECT DISTINCT athlete_id, sport, height_cm
            FROM summer_entries
            WHERE medal IS NOT NULL AND height_cm IS NOT NULL
        )
        GROUP BY sport
        ORDER BY avg_height_cm DESC
        LIMIT 1
    """)
    tallest = result.rows.iloc[0]
    assert tallest["sport"] == "Basketball"
    assert round(tallest["avg_height_cm"]) == 192


# The guard rejects everything but one read-only SELECT

@pytest.mark.parametrize("sql", REJECTED_WRITES.values(), ids=REJECTED_WRITES.keys())
def test_guard_rejects_non_select_statements(sql):
    with pytest.raises(SQLGuardError, match="Only read-only SELECT"):
        run_select(sql)


@pytest.mark.parametrize("sql", [
    "SELECT 1; SELECT 2",
    "SELECT 1;;",
    "SELECT COUNT(*) FROM noc_regions; DELETE FROM noc_regions",
])
def test_guard_rejects_more_than_one_statement(sql):
    with pytest.raises(SQLGuardError, match="Only one SQL statement"):
        run_select(sql)


@pytest.mark.parametrize("sql", ["", "  \n\t ", ";", "-- only a comment", "/* only a comment */"])
def test_guard_rejects_empty_input(sql):
    with pytest.raises(SQLGuardError, match="empty"):
        run_select(sql)


def test_guard_stops_infinite_recursive_query_near_timeout():
    infinite = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n"
    timeout_s = 0.5
    start = time.perf_counter()
    with pytest.raises(SQLGuardError, match="longer than 0.5 seconds"):
        run_select(infinite, timeout_s=timeout_s)
    assert timeout_s <= time.perf_counter() - start < timeout_s + 1.0


def test_connection_is_read_only_even_without_the_authorizer(database):
    with closing(db._connect_read_only(database)) as connection:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM noc_regions")


# The guard accepts ordinary SELECTs and limits their size

def test_guard_accepts_with_select():
    result = run_select("""
        WITH golds AS (SELECT country FROM country_medals WHERE medal = 'Gold')
        SELECT COUNT(*) AS gold FROM golds WHERE country = 'USA'
    """)
    assert result.columns == ["gold"]
    assert result.rows.iat[0, 0] == 1035


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) AS n FROM noc_regions;",
    "SELECT COUNT(*) AS n FROM noc_regions;  -- trailing comment\n",
    "SELECT COUNT(*) AS n FROM noc_regions WHERE NOC <> 'a;b';",
])
def test_guard_accepts_one_trailing_semicolon(sql):
    result = run_select(sql)
    assert result.rows.iat[0, 0] == 230
    assert result.truncated is False


def test_select_without_limit_is_truncated_to_max_rows():
    result = run_select("SELECT * FROM summer_entries", max_rows=200)
    assert result.columns == SUMMER_ENTRIES_COLUMNS
    assert len(result.rows) == 200
    assert result.truncated is True


def test_noc_regions_unchanged_after_rejected_writes():
    before = scalar("SELECT COUNT(*) FROM noc_regions")
    for sql in REJECTED_WRITES.values():
        with pytest.raises(SQLGuardError):
            run_select(sql)
    assert before == 230
    assert scalar("SELECT COUNT(*) FROM noc_regions") == before
    assert scalar("SELECT COUNT(*) FROM noc_regions WHERE region = 'Nowhere'") == 0
