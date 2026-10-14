"""
db.py
-----
The chatbot's data layer. It builds a SQLite copy of the Olympic data with the two views in
views.sql, and runs model-written SQL against it safely.

    ensure_database() -> Path         builds the database once, then reuses it
    run_select(sql)   -> QueryResult  runs one read-only SELECT with time and row limits

run_select() is the only way the model reaches the data. Each call opens a fresh read-only
connection, lets SQLite authorize nothing but reads, accepts exactly one statement, stops the
query after timeout_s seconds and returns at most max_rows rows. Anything else raises
SQLGuardError with a short message that is safe to show to users and to send back to the model.
"""

import hashlib
import os
import sqlite3
import tempfile
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sql.load_sqlite import build_database

ROOT = Path(__file__).resolve().parent.parent
VIEWS_PATH = Path(__file__).resolve().parent / "views.sql"
VIEW_NAMES = ("summer_entries", "country_medals")

# The system temp directory is writable on Streamlit Community Cloud and lies outside the repo.
DEFAULT_DB_PATH = Path(tempfile.gettempdir()) / "olympics_chatbot.db"
DB_PATH_ENV_VAR = "OLYMPICS_DB_PATH"

# Files that decide what gets built. Their fingerprint is stored in the database's user_version,
# so editing any of them (for example adding a column to a view) triggers a rebuild.
BUILD_INPUTS = (ROOT / "sql" / "schema.sql", ROOT / "sql" / "load_sqlite.py", VIEWS_PATH)

# Authorizer actions a plain SELECT needs. Everything else (writes, PRAGMA, ATTACH, ...) is denied.
ALLOWED_ACTIONS = frozenset({
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
})
PROGRESS_INTERVAL = 1_000  # SQLite VM instructions between timeout checks
MAX_VALUE_BYTES = 100_000  # largest string, blob or row a query may produce, so it cannot exhaust memory
CACHE_SIZE_KIB = 64 * 1024  # page cache per query connection

_build_lock = threading.Lock()


class SQLGuardError(Exception):
    """A query was rejected or failed. The message is short and safe to show to users and the model."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: pd.DataFrame
    truncated: bool  # True when the query had more than max_rows rows and only the first max_rows are returned
    elapsed_s: float


SCHEMA_DESCRIPTION = """\
SQLite database of the Summer Olympic Games from Athens 1896 to Rio 2016. It has no Winter Games \
and no Games after 2016. Query only the two views below, with a single SELECT (WITH ... SELECT is fine).

View summer_entries: one row per athlete per event per Games.
- athlete_id  INTEGER  unique athlete ID. Names are not unique, so group and count athletes by athlete_id.
- athlete     TEXT     full name as recorded, e.g. 'Michael Fred Phelps, II', 'Usain St. Leo Bolt'. \
Match names with LIKE, e.g. athlete LIKE '%Michael%Phelps%'.
- sex         TEXT     'M' or 'F'.
- age         INTEGER  age in that Games year; NULL if unknown.
- height_cm   REAL     height in cm; NULL if unknown.
- weight_kg   REAL     weight in kg; NULL if unknown.
- team        TEXT     team name as entered, e.g. 'United States', 'Great Britain', 'Soviet Union', \
'United States-1' (a country's second boat or pair).
- noc         TEXT     3-letter National Olympic Committee code, e.g. 'USA', 'GBR', 'URS', 'GER', 'IND'.
- country     TEXT     country the team belongs to, from noc_regions, e.g. 'USA', 'UK', 'Russia', \
'Germany', 'China', 'India'. Historical teams are grouped with today's country: the Soviet Union \
('URS') and the 1992 Unified Team ('EUN') count as 'Russia', East and West Germany ('GDR', 'FRG') \
as 'Germany', Hong Kong ('HKG') as 'China', Czechoslovakia as 'Czech Republic', Yugoslavia as \
'Serbia'. Some names are short or misspelt: 'Trinidad' (Trinidad and Tobago), 'Boliva' (Bolivia). \
If unsure of a name, look it up first: SELECT DISTINCT country FROM country_medals WHERE country LIKE '%...%'. \
country is NULL for noc 'SGP' (Singapore), 'ROT' (Refugee Olympic Athletes), 'TUV' (Tuvalu) and \
'UNK' (unknown); use noc for those.
- year        INTEGER  Games year, 1896 to 2016. 1906 is the Intercalated Games, which is not \
officially recognised: there are 28 official Summer Games (COUNT(DISTINCT year) excluding 1906), \
but medal counts include 1906, as the dashboard does.
- city        TEXT     host city in the dataset's spelling, e.g. 'Athina', 'London', 'Moskva', \
'Roma', 'Rio de Janeiro'. 1956 had two host cities, 'Melbourne' and 'Stockholm'.
- sport       TEXT     e.g. 'Athletics', 'Swimming', 'Basketball', 'Hockey', 'Football'.
- event       TEXT     sport, sex and event together, e.g. "Athletics Men's 100 metres", \
"Swimming Women's 4 x 100 metres Freestyle Relay".
- medal       TEXT     'Gold', 'Silver' or 'Bronze'; NULL means no medal.

View country_medals: one row per medal won by a country. A team medal (a relay, a team sport) is \
one row, not one row per team member.
- team, noc, country, year, city, sport, event: same meaning as in summer_entries.
- medal       TEXT     'Gold', 'Silver' or 'Bronze'; never NULL.

Which view to use:
- Medal counts for countries (medal tables, golds per country, a country's best Games, medals \
in a sport or year): country_medals, counting rows with COUNT(*). Add country IS NOT NULL when \
ranking countries. Never count country medals from summer_entries: a relay gold would count once \
per runner.
- Athletes (how many athletes, ages, heights, weights, men and women, participation): \
summer_entries with COUNT(DISTINCT athlete_id).
- Medals of individual athletes: summer_entries rows WHERE medal IS NOT NULL, grouped by \
athlete_id; each row is one medal for that athlete.
"""


def ensure_database() -> Path:
    """Returns the chatbot database's path, building it first if it is missing or out of date.

    The location is OLYMPICS_DB_PATH if set, otherwise a file in the system temp directory. The
    database is built into a temporary file next to it and renamed into place only when complete,
    so a half-built file is never used.
    """
    path = Path(os.environ.get(DB_PATH_ENV_VAR) or DEFAULT_DB_PATH)
    with _build_lock:
        if not _is_ready(path):
            _build(path)
    return path


def run_select(sql: str, max_rows: int = 200, timeout_s: float = 5.0) -> QueryResult:
    """Runs one read-only SELECT on the chatbot database and returns at most max_rows rows."""
    if not isinstance(sql, str):
        raise SQLGuardError("The query must be a string of SQL.")
    statement = _single_statement(sql)
    path = ensure_database()

    start = time.perf_counter()
    deadline = start + timeout_s

    def past_deadline() -> int:
        return int(time.perf_counter() > deadline)  # non-zero makes SQLite interrupt the query

    try:
        with closing(_connect_read_only(path)) as connection:
            # Connection-local tuning, set before the authorizer starts denying PRAGMA: the views'
            # DISTINCT sorts about 220,000 rows, which runs 3-4 times faster in memory than in temp files.
            connection.execute("PRAGMA temp_store = MEMORY")
            connection.execute(f"PRAGMA cache_size = -{CACHE_SIZE_KIB}")
            connection.set_authorizer(_authorize)
            connection.set_progress_handler(past_deadline, PROGRESS_INTERVAL)
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
            cursor = connection.execute(statement)
            if cursor.description is None:
                raise SQLGuardError("Only SELECT queries are allowed.")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(max_rows + 1)
    except sqlite3.Error as error:
        raise SQLGuardError(_user_safe_message(error, timeout_s)) from None
    elapsed_s = time.perf_counter() - start

    truncated = len(rows) > max_rows
    frame = pd.DataFrame.from_records(rows[:max_rows], columns=columns)
    return QueryResult(columns=columns, rows=frame, truncated=truncated, elapsed_s=elapsed_s)


def _single_statement(sql: str) -> str:
    """Returns the one statement in sql without its trailing semicolon; raises if there is not exactly one.

    Skips over quoted strings, quoted identifiers and comments, so a ';' inside them does not count.
    """
    statement_end = None  # index of the first ';' outside quotes and comments
    has_code = False
    i, length = 0, len(sql)
    while i < length:
        char = sql[i]
        if sql.startswith("--", i):
            newline = sql.find("\n", i)
            i = length if newline == -1 else newline + 1
        elif sql.startswith("/*", i):
            close = sql.find("*/", i + 2)
            i = length if close == -1 else close + 2
        elif char.isspace():
            i += 1
        elif statement_end is not None:
            raise SQLGuardError("Only one SQL statement is allowed per query.")
        elif char == ";":
            statement_end = i
            i += 1
        else:
            has_code = True
            if char in "'\"`[":
                close = sql.find("]" if char == "[" else char, i + 1)
                i = length if close == -1 else close + 1
            else:
                i += 1
    if not has_code:
        raise SQLGuardError("The query is empty.")
    return sql if statement_end is None else sql[:statement_end]


def _authorize(action: int, *_details) -> int:
    """sqlite3 authorizer: allows reading tables and views, calling functions and recursive CTEs only."""
    return sqlite3.SQLITE_OK if action in ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _user_safe_message(error: sqlite3.Error, timeout_s: float) -> str:
    message = str(error)
    if message == "interrupted":
        return f"The query took longer than {timeout_s:g} seconds and was stopped. Simplify it or filter the data more."
    if message.startswith("not authorized"):
        return "Only read-only SELECT queries on the Olympic data are allowed."
    if message.startswith("string or blob too big"):
        return "The query result is too large. Return fewer or shorter values."
    return f"SQLite error: {message[:200]}"


def _connect_read_only(path: Path) -> sqlite3.Connection:
    # isolation_level=None: Python never opens a transaction of its own.
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, isolation_level=None)


def _build_fingerprint() -> int:
    """A number that changes whenever a build input changes; fits SQLite's 32-bit user_version."""
    digest = hashlib.sha256()
    for path in BUILD_INPUTS:
        digest.update(path.read_bytes())
    return int(digest.hexdigest()[:7], 16)


def _is_ready(path: Path) -> bool:
    """True if path is a complete database with both views, built from the current build inputs."""
    if not path.is_file():
        return False
    try:
        with closing(_connect_read_only(path)) as connection:
            views = {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'view'")}
            (fingerprint,) = connection.execute("PRAGMA user_version").fetchone()
    except sqlite3.Error:
        return False
    return views.issuperset(VIEW_NAMES) and fingerprint == _build_fingerprint()


def _build(path: Path) -> None:
    """Builds the tables and views into a temporary file next to path, then renames it to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        build_database(temp_path)
        with closing(sqlite3.connect(temp_path)) as connection:
            connection.executescript(VIEWS_PATH.read_text(encoding="utf-8"))
            connection.execute(f"PRAGMA user_version = {_build_fingerprint()}")
            connection.commit()
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
