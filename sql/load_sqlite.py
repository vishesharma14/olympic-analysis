"""
load_sqlite.py
--------------
Loads athlete_events.csv and noc_regions.csv into a local SQLite database,
sql/olympics.db, using the tables in sql/schema.sql. Standard library only.

Run from anywhere:
    python sql/load_sqlite.py

build_database() is also used by the chatbot (chatbot/db.py) to build its own copy.
"""

import csv
import sqlite3
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DB_PATH = SQL_DIR / "olympics.db"

TABLES = {
    "noc_regions": ROOT / "noc_regions.csv",
    "athlete_events": ROOT / "athlete_events.csv",
}


def read_csv(path: Path) -> tuple[list[str], Iterator[list]]:
    """Returns a CSV's header and a generator of its rows, turning the dataset's missing-value markers
    ("NA" or empty) into NULL. Rows are read as they are consumed, so the whole file is never in memory."""
    lines = _read_lines(path)
    return next(lines), lines


def _read_lines(path: Path) -> Iterator[list]:
    # newline="" lets the csv module handle noc_regions.csv's old Mac-style \r line endings.
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        yield next(reader)  # the header, as written
        for row in reader:
            yield [None if value in ("NA", "") else value for value in row]


def build_database(db_path: Path) -> None:
    """Creates the tables from schema.sql in db_path (replacing any existing ones) and loads both CSVs."""
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        for table, path in TABLES.items():
            header, rows = read_csv(path)
            placeholders = ", ".join("?" for _ in header)
            cursor = connection.executemany(
                f"INSERT INTO {table} ({', '.join(header)}) VALUES ({placeholders})", rows
            )
            print(f"{table}: {cursor.rowcount:,} rows loaded")  # executemany sums the inserted rows
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    build_database(DB_PATH)
    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
