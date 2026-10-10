"""
run_queries.py
--------------
Runs the analysis queries in sql/olympics_analysis.sql against sql/olympics.db
and prints each result as a table. Standard library only.

    python sql/load_sqlite.py      # once, to build the database
    python sql/run_queries.py      # all ten questions
    python sql/run_queries.py 3    # only Q3
"""

import re
import sqlite3
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent
DB_PATH = SQL_DIR / "olympics.db"
QUERIES_PATH = SQL_DIR / "olympics_analysis.sql"


def load_queries() -> list[tuple[int, str, str]]:
    """Splits the .sql file into (number, title, sql) at each '-- Q<n>.' heading."""
    text = QUERIES_PATH.read_text(encoding="utf-8")
    parts = re.split(r"^-- Q(\d+)\. (.*)$", text, flags=re.MULTILINE)
    return [(int(parts[i]), parts[i + 1].strip(), parts[i + 2].strip()) for i in range(1, len(parts), 3)]


def format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def print_table(columns: list[str], rows: list[tuple]) -> None:
    cells = [[format_value(v) for v in row] for row in rows]
    widths = [max(len(col), *(len(row[i]) for row in cells)) if cells else len(col) for i, col in enumerate(columns)]
    line = "  ".join("-" * w for w in widths)
    print("  ".join(col.ljust(w) for col, w in zip(columns, widths)))
    print(line)
    for row in cells:
        print("  ".join(v.rjust(w) if v.replace(".", "").lstrip("-").isdigit() else v.ljust(w)
                        for v, w in zip(row, widths)))


def main() -> None:
    if not DB_PATH.exists():
        sys.exit(f"{DB_PATH.name} not found. Run: python sql/load_sqlite.py")
    wanted = {int(arg) for arg in sys.argv[1:]}
    connection = sqlite3.connect(DB_PATH)
    try:
        for number, title, sql in load_queries():
            if wanted and number not in wanted:
                continue
            cursor = connection.execute(sql)
            columns = [d[0] for d in cursor.description]
            print(f"\nQ{number}. {title}\n")
            print_table(columns, cursor.fetchall())
    finally:
        connection.close()


if __name__ == "__main__":
    main()
