# Tableau Dashboard

<!-- After publishing, replace this comment with:
**Live dashboard:** https://public.tableau.com/app/profile/<your-profile>/viz/<your-dashboard>
-->

An interactive Tableau Public dashboard built on the same data and counting rules as the Streamlit app.

## Data

`prepare_data.py` builds two tidy CSVs from the raw dataset, so Tableau never has to deduplicate team medals itself:

| File | Grain | Columns |
| --- | --- | --- |
| `medals.csv` | One row per Games × country × sport | Year, Country, Map Country, Sport, Gold, Silver, Bronze, Total |
| `participation_by_year.csv` | One row per Games | Year, Athletes, Women, Men, Women %, Nations, Sports, Events |

`Map Country` is `Country` with names Tableau's map recognises (for example, `UK` → `United Kingdom`, `USA` → `United States`).

```bash
python tableau/prepare_data.py
```

## How the dashboard is built

1. **Connect** — open Tableau Public, connect to `medals.csv`, then add `participation_by_year.csv` as a second data source.
2. **Medal map** — double-click `Map Country` (set its geographic role to *Country/Region*), put `SUM(Total)` on Color, and `Gold`, `Silver`, `Bronze` on Tooltip.
3. **Top 10 countries** — `Country` on Rows, `SUM(Gold)`, `SUM(Silver)` and `SUM(Bronze)` as a stacked bar with Measure Names on Color, and a Top 10 filter on `Country` by `SUM(Total)`.
4. **Medals over time** — `Year` (as a dimension) on Columns, `SUM(Total)` on Rows, line mark.
5. **Medals by sport** — `Sport` on Rows, `SUM(Total)` on Columns, sorted descending, or as a treemap.
6. **Women's participation** — from `participation_by_year.csv`: `Year` on Columns, `Women %` on Rows, line mark.
7. **KPI tiles** — single-number sheets for total medals, nations and athletes.
8. **Dashboard** — combine the sheets, add `Year` (range) and `Country` filters and apply them to all sheets that use `medals.csv`, and set the map as a filter action so clicking a country updates the other charts.
9. **Publish** — *File → Save to Tableau Public*, then copy the link into this README and the main README.
