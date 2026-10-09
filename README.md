# 🏅 Olympics Analysis Dashboard

[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://olympic-analysis-wbcngllnqyncsjv4agufpt.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)

An interactive Streamlit dashboard that explores **120 years of Summer Olympics history** — medal tallies, country-wise performance, athlete demographics and participation trends.

**Live app:** https://olympic-analysis-wbcngllnqyncsjv4agufpt.streamlit.app/

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

## Tech Stack

| Layer | Tools |
| --- | --- |
| App framework | Streamlit |
| Data processing | pandas, NumPy |
| Interactive charts | Plotly (line charts, choropleth map, animated bar race, histograms) |
| Statistical plots | Matplotlib, Seaborn (heatmaps, scatter plots) |

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
