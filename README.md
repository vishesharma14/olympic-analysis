# 🏅 Olympics Analysis Dashboard

[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://olympic-analysis-wbcngllnqyncsjv4agufpt.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-SQLite_|_MySQL-4479A1?logo=mysql&logoColor=white)
![Tableau](https://img.shields.io/badge/Tableau-dashboard-E97627?logo=tableau&logoColor=white)

An interactive Streamlit dashboard that explores **120 years of Summer Olympics history** — medal tallies, country-wise performance, athlete demographics and participation trends. The same data is also analysed in **SQL** and visualised in **Tableau**.

**Live app:** https://olympic-analysis-wbcngllnqyncsjv4agufpt.streamlit.app/
<!-- After publishing the Tableau dashboard, add: **Tableau dashboard:** <link> -->

<!-- Add a screenshot here, e.g. ![Dashboard overview](assets/overview.png) -->

---

## Features

### 🥇 Medal Tally
- Filter by year, by country, or both
- Gold, silver, bronze and total medal cards, with the full medal table

### 📊 Overall Analysis
- Key figures: Olympic editions, host cities, sports, events, nations and athletes
- Auto-generated **"Did You Know?"** facts: youngest gold medalist, oldest medalist, most decorated athlete, the nation with the most golds and the biggest Games by participation
- Participating nations, events and athletes over time
- **Choropleth world map** of medals by country, for any single year or overall
- **Animated medal race** of the top 10 nations, building cumulative totals across every Games
- Heatmap of events per sport across the years
- Top 15 most successful athletes, overall or by sport

### 🌍 Country-Wise Analysis
- Medal tally over the years for any country
- Sport-wise medal performance heatmap
- Top 10 athletes of the selected country

### 🏃 Athlete-Wise Analysis
- Age distribution of medalists by medal type
- Age distribution of gold medalists across sports
- Height vs. weight of athletes by sport, colored by medal and styled by sex
- Male vs. female participation over time

## SQL Analysis

Ten business questions answered in SQL — all-time medal table, India's performance at every Games, the top nation per Games, women's participation, the most decorated athletes, medal conversion rates and more. The queries use CTEs, window functions (`RANK`, `LAG`, `SUM OVER`), conditional aggregation and `HAVING`, run unchanged on **SQLite and MySQL 8**, and return the same numbers as the dashboard.

```bash
python sql/load_sqlite.py    # build a local SQLite database
python sql/run_queries.py    # print all ten results
```

See [`sql/README.md`](sql/README.md) for the questions, key findings and MySQL instructions.

## Tableau Dashboard

`tableau/prepare_data.py` builds tidy CSVs (team medals counted once, map-ready country names) for an interactive Tableau Public dashboard: a medal map, top-10 countries, medals over time, medals by sport and women's participation. See [`tableau/README.md`](tableau/README.md).

## Tech Stack

| Layer | Tools |
| --- | --- |
| App framework | Streamlit |
| Data processing | pandas, NumPy |
| Interactive charts | Plotly (line charts, choropleth map, animated bar race, histograms) |
| Statistical plots | Matplotlib, Seaborn (heatmaps, scatter plots) |
| SQL | SQLite, MySQL 8 (CTEs, window functions) |
| BI dashboard | Tableau Public |

## Dataset

[120 years of Olympic history: athletes and results](https://www.kaggle.com/datasets/heesoo37/120-years-of-olympic-history-athletes-and-results) (Kaggle):

- `athlete_events.csv` — athlete-level results for each event
- `noc_regions.csv` — National Olympic Committee codes mapped to regions

Both files are included in this repository.

## Project Structure

```
olympic-analysis/
├── app.py               # Streamlit app: navigation, layout and charts
├── preprocessor.py      # Loads, merges and prepares the dataset
├── helper.py            # Analysis functions: medal tallies, trends, facts, map and race data, top athletes
├── athlete_events.csv   # Athlete-level results
├── noc_regions.csv      # NOC code → region mapping
├── sql/                 # Schema, loaders (SQLite, MySQL) and ten analysis queries
├── tableau/             # Data preparation and CSVs for the Tableau dashboard
└── requirements.txt
```

## Run Locally

```bash
git clone https://github.com/vishesharma14/olympic-analysis.git
cd olympic-analysis
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501.

## Author

**Vishesh Sharma** · [GitHub](https://github.com/vishesharma14)
