# Key findings

## How big the Summer Olympics are

Across the Summer Games from 1896 to 2016, the data covers 28 official editions, 23 host cities, 52 sports, 651 events, 205 nations and 116,776 athletes. The edition count leaves out the 1906 Intercalated Games, which the IOC does not recognise. Athletes are counted once each by athlete_id, however many events or Games they entered, and nations are the countries in noc_regions, so the Soviet Union counts as Russia. This finding comes from question Q1 of the SQL analysis.

## All-time medal table

The USA leads the all-time Summer Olympic medal table with 1,035 gold medals and 2,545 medals in total: 1,035 gold, 802 silver and 708 bronze. Russia is second with 592 golds and 1,577 medals, and Germany is third with 444 golds and 1,392 medals. Russia's total includes the Soviet Union and the 1992 Unified Team, and Germany's includes East and West Germany, because countries follow noc_regions. A team medal such as a relay gold counts once for the country. The table is ranked by golds, then silvers, then bronzes, as in question Q2 of the SQL analysis.

## India's best Games

India's best Summer Games was London 2012, with 6 medals, more than at any other Games; its next best was Beijing 2008 with 3 medals. India's largest team was at Rio 2016, with 112 athletes, but India won only 2 medals there. These numbers count a team medal, such as a hockey gold, once for India, and count each athlete once per Games. They come from question Q3 of the SQL analysis, which lists India's athletes and medals at every Games and the change from the previous Games.

## Women's share of athletes

Women's participation in the Summer Olympics grew from none to almost half of all athletes. Women made up 0% of athletes in 1896, when no women competed, 10.1% in 1948 and 45.0% in 2016, when 5,034 of the 11,179 athletes were women. The shares count each athlete once per Games by athlete_id, using the sex column. This finding comes from question Q5 of the SQL analysis, which gives the share of women for every Games.

## Most decorated Olympians

Michael Phelps of the USA is the most decorated Summer Olympian, with 28 medals, 23 of them gold, all in swimming. Next come three Soviet gymnasts, who count under Russia: Larysa Latynina with 18 medals (9 gold), Nikolay Andrianov with 15 medals (7 gold) and Borys Shakhlin with 13 medals (7 gold). Athletes are grouped by athlete_id because names are not unique. Every member of a relay or team is credited with the medal individually, so a relay gold adds one medal to each swimmer's total. This is question Q6 of the SQL analysis.

## Countries that turn athletes into medallists

Among countries with at least 1,000 Summer Olympians, Russia turns the largest share of its athletes into medallists: 48.6% of its 4,486 athletes won at least one medal. The USA is second with 42.2% of its 7,970 athletes, and Germany third with 36.1%. Russia includes the Soviet Union and Germany includes East and West Germany, because countries follow noc_regions. Athletes are counted once each by athlete_id, and a medallist is an athlete with at least one medal, so every member of a medal-winning team counts. This is question Q7 of the SQL analysis.

## USA dominance in swimming and athletics

The USA has won 43.9% of all Summer Olympic swimming golds (246 of 561) and 34.4% of all athletics golds (344 of 1,000). Swimming is the sport where a single country holds the largest share of the golds, among sports with at least 50 golds; next comes the USA in diving with 39.3%. A relay or team gold counts once for the country, and countries follow noc_regions. This is question Q9 of the SQL analysis.

## Tallest medallists

Basketball medallists are the tallest of any Summer sport, averaging 192.1 cm and 86.7 kg. Volleyball medallists come next at 186.4 cm, then water polo medallists at 184.8 cm, while gymnastics medallists are the shortest at 160.9 cm. These averages count each medallist once per sport, include only medallists whose height and weight are both recorded, and rank only sports with at least 100 such medallists. This is question Q10 of the SQL analysis.

## Top gold-medal nation at selected Games

The country with the most golds changes from Games to Games. At Moscow 1980, Russia, competing as the Soviet Union, won the most golds with 80, at Games boycotted by the USA and many other countries, where only 80 nations took part. At Los Angeles 1984, boycotted by the Soviet Union and most of its allies, the USA won 82 golds. China topped the table once, at its home Games in Beijing 2008, with 51 golds, and the USA was top again at Rio 2016 with 46 golds. Overall, the USA topped the gold table at 17 of the 29 Games in the data and Russia at 6. Team golds count once per country, as in question Q4 of the SQL analysis.

## Age of medallists

Medallists are slightly older on average than other competitors. Across Summer entries with a known age, medal-winning entries average 25.9 years, against 25.5 years for entries without a medal. By medal colour, gold and bronze medallists average 25.9 years and silver medallists 26.0 years. The youngest medallist in the data was 10 years old and the oldest was 73. Ages are the athlete's age in that Games year, and entries with no recorded age are left out. This is question Q8 of the SQL analysis.

## India's overall record

India has won 28 Summer Olympic medals: 9 gold, 7 silver and 12 bronze, from 871 athletes who competed at 24 Games. Hockey is India's strongest sport by far, with 11 medals, including 8 golds; India won hockey gold at every Games from 1928 to 1956, then again in 1964 and 1980. India's only gold outside hockey is Abhinav Bindra's in the men's 10 metre air rifle (shooting) at Beijing 2008. India's best Games was London 2012, with 6 medals, and its largest team was at Rio 2016, with 112 athletes. A team medal, such as a hockey gold, counts once for India.

## Milestones in women's participation

Women first competed at the Paris 1900 Games, where 23 of the 1,224 athletes were women (1.9%), and women won medals at those Games too. The share of women among Summer Olympians first reached 10% in 1932, 20% in 1976, 30% in 1996 and 40% in 2004, and stood at 45.0% in 2016. Across all Summer Games, 28,851 different women have competed. Each athlete is counted once per Games by athlete_id, using the sex column.
