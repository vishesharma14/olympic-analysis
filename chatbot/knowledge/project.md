# About this project

## What this project contains

This project analyses 120 years of Summer Olympics data, from Athens 1896 to Rio 2016, in four ways. A Streamlit dashboard shows medal tallies, country and athlete analysis and participation trends. A SQL analysis answers ten questions in SQLite and MySQL 8. A Tableau Public dashboard shows medals by country, year and sport. The Ask the data assistant answers plain-English questions by querying the same data. All four parts use the same data and the same counting rules.

## Streamlit dashboard pages

The Streamlit dashboard has four pages. Medal Tally shows gold, silver, bronze and total medals, filtered by year, by country or both. Overall Analysis shows headline figures, "Did You Know?" facts, nations, events and athletes over time, a world map of medals, an animated race of the top 10 nations and the most successful athletes. Country-Wise Analysis shows one country's medals over the years, its medals by sport and its top 10 athletes. Athlete Wise Analysis shows the ages of medallists, height and weight by sport, and men and women over time.

## SQL analysis

The SQL analysis answers ten questions about the Summer Olympics, such as the all-time medal table, India's record at every Games, the top nation at each Games, women's participation and the most decorated athletes. The queries use common table expressions (CTEs), window functions such as RANK, LAG and SUM OVER, conditional aggregation and HAVING. They run unchanged on SQLite and MySQL 8, return the same results on both, and match the dashboard's numbers. The SQL files are in the sql folder of the repository.

## Tableau Public dashboard

The Tableau Public dashboard shows a medal map, the top 10 countries, medals over time, the top 15 sports and women's share of athletes. Year and Country filters update every medal chart, and clicking a country on the map shows its medals over time and its strongest sports. The Tableau dashboard is built from CSV files prepared with the same counting rules as the rest of the project. Link: https://public.tableau.com/app/profile/vishesh.sharma3888/viz/OlympicsMedalDashboard_17916664107200/OlympicsDashboard

## How the Ask the data assistant answers

The Ask the data assistant answers questions about the Summer Olympics from 1896 to 2016 using this project's data and Google's Gemini models. For each question, it first retrieves the most relevant of these notes, which explain the dataset, the counting rules and key findings. Questions about definitions and counting rules are answered from the notes. For counts, totals, rankings and lists, the assistant writes read-only SQL queries on the Olympic data, prepared with the same counting rules as the dashboard, runs them and answers with the numbers from the results. Under each answer it shows the SQL it ran and the notes it used, and it flags any number it could not match to them. The assistant can only read the data, never change it. It cannot browse the web, see live or recent results such as Paris 2024, cover the Winter Games, or give opinions or predictions; it only reports what the data shows.
