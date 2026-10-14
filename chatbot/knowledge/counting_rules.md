# Counting rules

## Summer Games only

Every number in this project counts the Summer Olympic Games only, from Athens 1896 to Rio 2016. The source CSV also contains 48,564 Winter Games rows, which are left out of the Streamlit dashboard, the SQL analysis, the Tableau dashboard and the Ask the data assistant. A medal total for a country such as Norway, which has won many Winter medals, therefore counts only its Summer medals. Questions about Winter sports such as skiing or ice hockey cannot be answered from this data.

## Duplicate rows are removed

The source CSV has 1,385 exact duplicate rows, all of them in the Summer Games. Every count in this project removes the duplicates first: the dashboard drops duplicate rows, the SQL analysis uses SELECT DISTINCT, and the assistant's summer_entries view keeps one row per athlete per event per Games. That leaves 221,167 Summer entries. Removing duplicates matters for counts of entries and of medals per athlete; counts of distinct athletes are not affected.

## Team medals count once

A team medal counts once for the country, not once per team member. In the data, a relay or team-sport medal appears as one row for every athlete who received it, including athletes who swam only in the heats. For example, the USA's gold in the men's 4 x 100 metres freestyle relay at Beijing 2008 has 7 athlete rows but counts as 1 gold medal for the USA. Counted once per athlete instead, the USA's all-time Summer total would be 5,002 medals instead of 2,545. Country medal tables use the country_medals view, which keeps one row per team, NOC, Games, sport, event and medal. Medal counts for individual athletes still credit every team member.

## Countries follow noc_regions

Countries come from the noc_regions file, which maps each NOC code to a present-day country, called region in the file. Historical teams are grouped with their successor: the Soviet Union (URS) and the 1992 Unified Team (EUN) count as Russia, East Germany (GDR) and West Germany (FRG) count as Germany, Hong Kong (HKG) counts as China, Czechoslovakia (TCH) counts as Czech Republic, and Yugoslavia (YUG) counts as Serbia. The grouping changes totals a lot: Russia's 1,577 medals include 1,005 won by the Soviet Union and 112 by the Unified Team, and Germany's 1,392 medals include 409 won by East Germany and 204 by West Germany. Country names are the file's short names, such as USA, UK and Russia.

## Teams with no country

A few teams have no country in this data. Singapore competes under the NOC code SGP, but noc_regions lists Singapore as SIN, so Singapore's rows get no country: its 5 Summer medals, including 1 gold, are missing from country medal tables. The same applies to the Refugee Olympic Athletes (ROT), Tuvalu (TUV) and an unknown team (UNK), none of which won a medal. To count medals for these teams, filter on the NOC code instead of the country, for example noc = 'SGP'.

## Unusual country names

Some country names in noc_regions are short or misspelt, and queries must use them exactly. Bolivia is spelled "Boliva", and Trinidad and Tobago is just "Trinidad". The United States is "USA" and Great Britain is "UK". Athletes from Hong Kong are counted under "China", and athletes who competed independently under the Olympic flag are grouped as "Individual Olympic Athletes". When a country name gives no results, search with a pattern such as country LIKE '%Boliv%' to find the spelling used in the data.

## Why totals can differ from official IOC medal tables

Medal totals in this project can differ from the official International Olympic Committee (IOC) medal tables, for several reasons. Historical teams are grouped with today's country, so the Soviet Union's medals count for Russia and East and West Germany's for Germany, while the IOC lists those teams separately. The 1906 Intercalated Games are included, although the IOC does not count them. Medals won by mixed teams in early Games count once for each country in the team: the Denmark/Sweden tug-of-war gold of 1900 counts once for Denmark and once for Sweden. The data was scraped from Sports Reference in 2018, so medals reassigned later, for example after doping cases, are not reflected, and the source has occasional errors of its own. Answers should quote this project's numbers and mention these reasons when a user compares them with official tables.
