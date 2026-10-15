# The Olympic dataset

## Source of the data

The data comes from the Kaggle dataset "120 years of Olympic history: athletes and results", which was scraped from the historical results on Sports Reference (sports-reference.com) in 2018. It has two files: a results file with 271,116 records, covering both the Summer and the Winter Games, and a list of 230 National Olympic Committee (NOC) codes, each mapped to a country. The Streamlit dashboard, the SQL analysis, the Tableau dashboard and the Ask the data assistant all use these two files and nothing else.

## What one record is

In the results file, one record is one athlete taking part in one event at one Games. It holds the athlete's ID number, name, sex, age, height and weight, the team and NOC code, the Games year, season and host city, the sport and event, and the medal won: Gold, Silver, Bronze, or empty for no medal. An athlete who entered three events at one Games has three records, and a relay team has one record per team member. The Summer data used by the assistant keeps this level of detail: it has 221,167 entries, one per athlete per event per Games, after duplicate records are removed.

## Coverage: Summer Games 1896 to 2016 only

This project covers the Summer Olympic Games only, from Athens 1896 to Rio de Janeiro 2016. The source data also contains 48,564 Winter Games records, which are excluded everywhere: in the Streamlit dashboard, the SQL analysis, the Tableau dashboard and the Ask the data assistant. The latest Games in the data are Rio 2016, so there are no results for Tokyo 2020, Paris 2024 or any later Games. The Summer data covers 29 Games years: 28 official editions plus the 1906 Intercalated Games.

## The 1906 Intercalated Games

The 1906 Intercalated Games were held in Athens, spelled Athina in the data, between the official 1904 and 1908 Games. The International Olympic Committee (IOC) does not recognise them as an official edition, which is why there are 28 official Summer Games rather than 29. The 1906 Games are still part of this data: 841 athletes competed in 74 events, and the 224 medals awarded there are included in every medal total, as in the dashboard. For example, the USA's all-time total of 2,545 medals includes 23 medals won in 1906.

## The 1956 Games had two host cities

The 1956 Summer Games had two host cities. Most events took place in Melbourne, Australia, but Australia's quarantine rules kept foreign horses out, so the equestrian events were held in Stockholm, Sweden, earlier that year. In the data, the 1956 Games therefore have two host cities: Melbourne, where 3,189 athletes competed in 145 events, and Stockholm, where 158 athletes competed in 6 equestrian events. Questions about the 1956 Games should include both cities unless the question asks about one of them.

## Missing values

Some athlete details are missing from the data, especially heights and weights. Of the 221,167 Summer entries (one per athlete per event per Games), 4.1% have no age, 22.8% have no height and 23.7% have no weight. Missing values are left empty. Averages of age, height or weight therefore only cover entries where the value is known, and rankings such as the tallest or heaviest athletes ignore entries with no measurement.

## Duplicate records

The source data contains 1,385 records that exactly duplicate another record, and all of them are Summer Games records. The duplicates are removed before any counting, as in the dashboard and the SQL analysis. After removal, the 222,552 Summer records in the source data become 221,167 Summer entries, one per athlete per event per Games. Without this step, counts of entries and of medals per athlete would be slightly too high.

## City spellings in the data

Host cities use the dataset's own spellings, which follow the local language for some cities. Athens is spelled Athina (1896, 1906 and 2004), Moscow is Moskva (1980), Rome is Roma (1960) and Antwerp is Antwerpen (1920). Other host cities use their English names, such as London, Paris, Los Angeles, Rio de Janeiro and Mexico City. Searches of the data by city need these spellings, for example Athina for Athens. The Summer data has 23 different host cities.
