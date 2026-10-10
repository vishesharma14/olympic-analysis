"""
load_sqlite.py
--------------
Loads athlete_events.csv and noc_regions.csv into a local SQLite database,
sql/olympics.db, using the tables in sql/schema.sql. Standard library only.

Run from anywhere:
    python sql/load_sqlite.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DB_PATH = SQL_DIR / "olympics.db"

TABLES = {
    "noc_regions": ROOT / "noc_regions.csv",
    "athlete_events": ROOT / "athlete_events.csv",
}


def read_csv(path: Path) -> tuple[list[str], list[list]]:
    """Reads a CSV, turning the dataset's missing-value markers ("NA" or empty) into NULL."""
    # newline="" lets the csv module handle noc_regions.csv's old Mac-style \r line endings.
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [[None if value in ("NA", "") else value for value in row] for row in reader]
    return header, rows


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        for table, path in TABLES.items():
            header, rows = read_csv(path)
            placeholders = ", ".join("?" for _ in header)
            connection.executemany(
                f"INSERT INTO {table} ({', '.join(header)}) VALUES ({placeholders})", rows
            )
            print(f"{table}: {len(rows):,} rows loaded")
        connection.commit()
    finally:
        connection.close()
    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
