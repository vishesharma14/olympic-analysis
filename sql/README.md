# SQL Analysis

Ten business questions answered in SQL on the same dataset as the dashboard. The queries run unchanged on **SQLite** and **MySQL 8** and return identical results on both; the headline numbers also match the Streamlit dashboard.

## Files

| File | Purpose |
| --- | --- |
| `schema.sql` | Table definitions for `athlete_events` and `noc_regions` |
| `load_sqlite.py` | Loads both CSVs into `sql/olympics.db` (Python standard library only) |
| `load_mysql.sql` | Creates the `olympics` database in MySQL 8 and loads both CSVs |
| `olympics_analysis.sql` | The ten analysis queries, each with the question it answers |
| `run_queries.py` | Runs the queries against SQLite and prints each result as a table |

## Run with SQLite (no installation needed)

```bash
python sql/load_sqlite.py      # builds sql/olympics.db in a few seconds
python sql/run_queries.py      # prints all ten results
python sql/run_queries.py 3    # prints only Q3
```

You can also open `sql/olympics.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) and run the queries there.

## Run with MySQL 8

From the repository root:

```bash
mysql --local-infile=1 -u root -p < sql/load_mysql.sql
mysql -u root -p olympics < sql/olympics_analysis.sql
```

Or open `sql/olympics_analysis.sql` in MySQL Workbench and run each query on the `olympics` database.

## Questions and SQL concepts

| # | Question | Concepts |
| --- | --- | --- |
| Q1 | How big are the Summer Olympics? | `COUNT(DISTINCT)`, `CASE` inside an aggregate, `LEFT JOIN` |
| Q2 | Which countries have won the most medals of all time? | CTE, conditional aggregation, `JOIN` |
| Q3 | How has India performed at every Games, compared with the previous one? | Multiple CTEs, `COALESCE`, `LAG()` |
| Q4 | Which country topped the gold-medal table at each Games? | `RANK()` window partitioned by Games |
| Q5 | How has women's participation grown? | `COUNT(DISTINCT CASE …)`, percentages |
| Q6 | Who are the most decorated Summer Olympians? | Derived table to remove duplicates, `GROUP BY` a key |
| Q7 | Which countries turn the largest share of athletes into medallists? | Ratio of distinct counts, filtering aggregates |
| Q8 | Are medallists older or younger than other competitors? | `COALESCE` for NULLs, `AVG` / `MIN` / `MAX` |
| Q9 | In which sports does one country win the biggest share of golds? | `SUM() OVER`, `RANK() OVER`, share of a partition |
| Q10 | Which sports have the tallest medallists? | Derived table, `HAVING` |

## Key findings

| Finding | Query |
| --- | --- |
| 28 official Summer Games, 205 nations, 116,776 athletes and 651 events | Q1 |
| The USA leads the all-time table with 1,035 golds and 2,545 medals in total | Q2 |
| India's best Games was London 2012 with 6 medals; Rio 2016 had its largest team, 112 athletes | Q3 |
| Women made up 0% of athletes in 1896, 10% by 1948 and 45% by 2016 | Q5 |
| Michael Phelps leads with 28 medals, 23 of them gold | Q6 |
| Russia (including the Soviet Union) turns 48.6% of its athletes into medallists, the USA 42.2% | Q7 |
| The USA has won 43.9% of all swimming golds and 34.4% of all athletics golds | Q9 |
| Basketball medallists are the tallest, averaging 192 cm | Q10 |

## Counting rules

These match the Streamlit dashboard, so the numbers agree:

- **Summer Games only.**
- **Team medals count once per country.** A relay gold is one medal for the country, not four, so medal counts use `DISTINCT (Team, NOC, Year, City, Sport, Event, Medal)`.
- **Duplicates removed.** The source CSV has 1,385 exact duplicate rows; athlete-level queries use `SELECT DISTINCT *`.
- **Countries follow `noc_regions.csv`**, which groups historical teams with their modern country (for example, the Soviet Union with Russia and West and East Germany with Germany).
