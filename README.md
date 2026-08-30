# 🏅 Olympics Analysis Dashboard

An interactive Streamlit dashboard exploring 120 years of Summer Olympics history — medal tallies, country-wise performance, athlete demographics, and participation trends.

**🔗 Live app:** _add your Streamlit Cloud link here after deploying_

## Features

- **Medal Tally** — filter by year and/or country, with a live medal breakdown
- **Overall Analysis** — key stats, auto-generated "Did You Know?" facts, participation trends, a choropleth medal map, and an animated medal-race chart of the top 10 nations
- **Country-Wise Analysis** — medal trend over time, sport-wise performance heatmap, and top athletes for any selected country
- **Athlete-Wise Analysis** — age distribution by medal type, age spread across sports, height vs. weight by sport, and male vs. female participation over time

## Tech Stack

- Streamlit for the app framework
- Pandas / NumPy for data processing
- Plotly for interactive charts (line, choropleth, animated bar race)
- Matplotlib / Seaborn for statistical heatmaps and scatter plots

## Data

Built on the [120 years of Olympic history: athletes and results](https://www.kaggle.com/datasets/heesoo37/120-years-of-olympic-history-athletes-and-results) dataset (`athlete_events.csv` + `noc_regions.csv`).

## Run Locally

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
pip install -r requirements.txt
streamlit run app.py
```

Place `athlete_events.csv` and `noc_regions.csv` in the project root before running.