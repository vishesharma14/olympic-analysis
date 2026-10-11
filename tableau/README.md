# Tableau Dashboard

**Live dashboard:** https://public.tableau.com/app/profile/vishesh.sharma3888/viz/OlympicsMedalDashboard_17916664107200/OlympicsDashboard

An interactive Tableau Public dashboard built on the same data and counting rules as the Streamlit app.

## What it shows

| Chart | Question it answers |
| --- | --- |
| Medal map | Which countries have won the most Summer Olympic medals? |
| Top 10 countries | Who leads the all-time medal table (or the table for the selected years)? |
| Medals over time | How has the number of medals awarded grown across the Games? |
| Top 15 sports | Which sports award the most medals, overall or for a selected country? |
| Women's share of athletes | How has women's participation grown from 0% in 1896 to 45% in 2016? |

**Interactivity**

- **Year** (range) and **Country** filters update every medal chart.
- **Click a country on the map** to see its medals over time and its own strongest sports. For example, India shows 28 medals in total, a peak of 6 at London 2012, and Hockey as its top sport with 11 medals.

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

1. **Connect:** open Tableau Public, connect to `medals.csv`, then add `participation_by_year.csv` as a second data source.
2. **Medal map:** `Map Country` (geographic role *Country/Region*) on Detail, `SUM(Total)` on Color, and `Gold`, `Silver`, `Bronze` on Tooltip.
3. **Top 10 countries:** `Country` on Rows and `SUM(Total)` on Columns, sorted descending, with a Top 10 filter on `Map Country` by `SUM(Total)`.
4. **Medals over time:** `Year` (continuous dimension) on Columns and `SUM(Total)` on Rows, as a line.
5. **Top 15 sports:** `Sport` on Rows and `SUM(Total)` on Columns, sorted descending, with a Top 15 filter on `Sport`.
6. **Women's participation:** from `participation_by_year.csv`, `Year` on Columns and `Women %` on Rows, as a line.
7. **Filters:** `Year` (range of values) and `Country`, applied to all sheets that use `medals.csv` and **added to context**. Tableau computes Top N filters before ordinary filters, so without context the Top 10 and Top 15 would not be recalculated for the selected years or countries.
8. **Click a country:** a filter action from the map to *Medals over time* and *Top 15 sports*. Its action filter is added to context on the sports sheet, so a selected country shows its own top sports rather than the global top 15.
9. **Publish:** fixed size of 1200 × 900, worksheets hidden so only the dashboard is shown, then *File → Save to Tableau Public*.
