# The Olympic dataset

## Source of the data

The data comes from the Kaggle dataset "120 years of Olympic history: athletes and results", which was scraped from the historical results on Sports Reference (sports-reference.com) in 2018. It has two files. athlete_events.csv holds the results and has 271,116 rows, covering both the Summer and the Winter Games. noc_regions.csv maps each National Olympic Committee (NOC) code to a country and has 230 rows. The Streamlit dashboard, the SQL analysis, the Tableau dashboard and the Ask the data assistant all use these two files and nothing else.

## What one row is

In athlete_events.csv, one row is one athlete taking part in one event at one Games. The row records the athlete's ID, name, sex, age, height and weight, the team and NOC code, the Games year, season and host city, the sport and event, and the medal won: Gold, Silver, Bronze, or empty for no medal. An athlete who entered three events at one Games has three rows, and a relay team has one row per team member. The assistant's summer_entries view keeps this grain for the Summer Games: it has 221,167 rows, one per athlete per event per Games, after duplicate rows are removed.

## Coverage: Summer Games 1896 to 2016 only

This project covers the Summer Olympic Games only, from Athens 1896 to Rio de Janeiro 2016. The CSV also contains 48,564 Winter Games rows, which are excluded everywhere: in the Streamlit dashboard, the SQL analysis, the Tableau dashboard and the Ask the data assistant. The latest Games in the data are Rio 2016, so there are no results for Tokyo 2020, Paris 2024 or any later Games. The Summer data covers 29 Games years: 28 official editions plus the 1906 Intercalated Games.

## The 1906 Intercalated Games

The 1906 Intercalated Games were held in Athens, spelled Athina in the data, between the official 1904 and 1908 Games. The International Olympic Committee (IOC) does not recognise them as an official edition, which is why there are 28 official Summer Games rather than 29. The 1906 Games are still part of this data: 841 athletes competed in 74 events, and the 224 medals awarded there are included in every medal total, as in the dashboard. For example, the USA's all-time total of 2,545 medals includes 23 medals won in 1906.

## The 1956 Games had two host cities

The 1956 Summer Games had two host cities. Most events took place in Melbourne, Australia, but Australia's quarantine rules kept foreign horses out, so the equestrian events were held in Stockholm, Sweden, earlier that year. In the data, the 1956 Games therefore have rows with city Melbourne, where 3,189 athletes competed in 145 events, and rows with city Stockholm, where 158 athletes competed in 6 equestrian events. Questions about the 1956 Games should include both cities unless the question asks about one of them.

## Missing values

Some athlete details are missing from the data, especially heights and weights. Of the 221,167 Summer entries (one row per athlete per event per Games), 4.1% have no age, 22.8% have no height and 23.7% have no weight. Missing values are stored as NULL. Averages of age, height or weight therefore only cover entries where the value is known, and rankings such as the tallest or heaviest athletes ignore entries with no measurement.

## Duplicate rows

The source CSV contains 1,385 rows that exactly duplicate another row, and all of them are Summer Games rows. The duplicates are removed before any counting, matching the dashboard's drop_duplicates step and the SELECT DISTINCT used in the SQL analysis. After removal, the 222,552 Summer rows in the CSV become 221,167 Summer entries, one per athlete per event per Games. Without this step, counts of entries and of medals per athlete would be slightly too high.

## City spellings in the data

Host cities use the dataset's own spellings, which follow the local language for some cities. Athens is spelled Athina (1896, 1906 and 2004), Moscow is Moskva (1980), Rome is Roma (1960) and Antwerp is Antwerpen (1920). Other host cities use their English names, such as London, Paris, Los Angeles, Rio de Janeiro and Mexico City. When filtering by city, use the spelling from the data, for example city = 'Athina' for Athens. The Summer data has 23 different host cities.
