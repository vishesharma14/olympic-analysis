# Counting rules

## Summer Games only

Every number in this project counts the Summer Olympic Games only, from Athens 1896 to Rio 2016. The source data also contains 48,564 Winter Games records, which are left out of the Streamlit dashboard, the SQL analysis, the Tableau dashboard and the Ask the data assistant. A medal total for a country such as Norway, which has won many Winter medals, therefore counts only its Summer medals. Questions about Winter sports such as skiing or ice hockey cannot be answered from this data.

## Duplicate records are removed

The source data has 1,385 exact duplicate records, all of them in the Summer Games. Every count in this project removes the duplicates first, in the dashboard, the SQL analysis and the assistant alike, so each athlete appears once per event per Games. That leaves 221,167 Summer entries. Removing duplicates matters for counts of entries and of medals per athlete; counts of distinct athletes are not affected.

## Team medals count once

A team medal counts once for the country, not once per team member. In the data, a relay or team-sport medal is recorded once for every athlete who received it, including athletes who swam only in the heats. For example, the USA's gold in the men's 4 x 100 metres freestyle relay at Beijing 2008 is recorded for 7 athletes but counts as 1 gold medal for the USA. Counted once per athlete instead, the USA's all-time Summer total would be 5,002 medals instead of 2,545. Country medal tables therefore count each team medal once per event and Games. Medal counts for individual athletes still credit every team member.

## Historical teams count as today's country

Every team is assigned to a present-day country through the dataset's list of National Olympic Committee (NOC) codes, which maps each code to a country. Historical teams are grouped with their successor: the Soviet Union (URS) and the 1992 Unified Team (EUN) count as Russia, East Germany (GDR) and West Germany (FRG) count as Germany, Hong Kong (HKG) counts as China, Czechoslovakia (TCH) counts as Czech Republic, and Yugoslavia (YUG) counts as Serbia. The grouping changes totals a lot: Russia's 1,577 medals include 1,005 won by the Soviet Union and 112 by the Unified Team, and Germany's 1,392 medals include 409 won by East Germany and 204 by West Germany. Country names are short names, such as USA, UK and Russia.

## Teams with no country

A few teams have no country in this data. Singapore competes under the NOC code SGP, but the dataset's country list gives Singapore the code SIN, so Singapore's results get no country: its 5 Summer medals, including 1 gold, are missing from country medal tables. The same applies to the Refugee Olympic Athletes (ROT), Tuvalu (TUV) and an unknown team (UNK), none of which won a medal. These teams can still be counted by their NOC code instead of a country.

## Unusual country names

Some country names in the data are short or misspelt. Bolivia is spelled "Boliva", and Trinidad and Tobago is just "Trinidad". The United States is "USA" and Great Britain is "UK". Athletes from Hong Kong are counted under "China", and athletes who competed independently under the Olympic flag are grouped as "Individual Olympic Athletes". Answers can use the usual names, but searches of the data need the spellings used there.

## Why totals can differ from official IOC medal tables

Medal totals in this project can differ from the official International Olympic Committee (IOC) medal tables, for several reasons. Historical teams are grouped with today's country, so the Soviet Union's medals count for Russia and East and West Germany's for Germany, while the IOC lists those teams separately. The 1906 Intercalated Games are included, although the IOC does not count them. Medals won by mixed teams in early Games count once for each country in the team: the Denmark/Sweden tug-of-war gold of 1900 counts once for Denmark and once for Sweden. The data was scraped from Sports Reference in 2018, so medals reassigned later, for example after doping cases, are not reflected, and the source has occasional errors of its own. Answers should quote this project's numbers and mention these reasons when a user compares them with official tables.
