# Glossary

## NOC (National Olympic Committee)

An NOC, or National Olympic Committee, is the organisation that enters a team at the Olympic Games. In the data, each NOC has a three-letter code, such as USA for the United States, GBR for Great Britain, IND for India and URS for the Soviet Union. The Summer data uses 230 different NOC codes, including codes for teams that no longer exist. The noc_regions file maps each NOC code to a present-day country.

## Region and country

A country, called region in the noc_regions file, is the present-day country that an NOC code maps to. Country is how this project groups medals and athletes by nation, and several historical NOC codes can share one country: the Soviet Union (URS) and Russia (RUS) both count as Russia. The Summer data has 205 countries. A few teams have no country, such as Singapore, whose code SGP is missing from noc_regions.

## Games and edition

A Games, or edition, is one Summer Olympics, identified by its year and host city, for example Rio 2016. The data has 29 Summer Games years from 1896 to 2016: 28 official editions plus the 1906 Intercalated Games, which the IOC does not count. No Games were held in 1916, 1940 or 1944 because of the World Wars. In the raw data, the Games column combines the year and the season, such as "2016 Summer".

## Sport and event

A sport is a whole discipline, such as Athletics, Swimming or Hockey. An event is a single competition within a sport that awards its own set of medals, such as Athletics Men's Marathon. Event names include the sport and the sex, so the same event name is used at every Games where that event was held. The Summer data has 52 sports and 651 different events.

## Medallist

A medallist is an athlete who won at least one Gold, Silver or Bronze medal. Of the 116,776 athletes in the Summer data, 24,584 are medallists. Every member of a medal-winning team or relay counts as a medallist and is credited with the medal individually, even though a country's medal table counts that team medal only once. In the data, a medal value of NULL means the athlete did not win a medal in that event.

## Team medal

A team medal is a medal won by a team rather than by one athlete, for example in a relay, in a team sport such as hockey or basketball, or by a rowing crew. The data lists every team member as a separate row with the medal. In country medal tables, a team medal counts once for the country, so a relay gold is one gold, not one per runner. In individual athlete counts, each team member is still credited with the medal.

## Intercalated Games

The Intercalated Games were held in Athens in 1906, between the official 1904 and 1908 Games. The IOC does not recognise the Intercalated Games as an official edition, so the official count of Summer Games is 28. The 1906 Games are still in the data, with 841 athletes in 74 events, and their 224 medals are included in medal totals in this project, matching the dashboard.

## Unified Team (1992)

The Unified Team, NOC code EUN, competed at the 1992 Barcelona Games. It was made up of athletes from former Soviet republics after the Soviet Union broke up. In this data the Unified Team counts as Russia, so its 112 medals, including 45 golds, are part of Russia's total. A total of 475 athletes competed for the Unified Team.

## Independent Olympic Athletes (IOA)

Independent Olympic Athletes competed under the Olympic flag instead of for a country, with the NOC code IOA. In this data both the team and the country are labelled "Individual Olympic Athletes". They appear at four Games: in 1992, 58 athletes from Yugoslavia competed as Independent Olympic Participants because of UN sanctions; in 2000, 4 athletes from East Timor; in 2012, 4 athletes from the Netherlands Antilles and South Sudan; and in 2016, 9 athletes from Kuwait. Independent athletes won 5 medals, all in shooting, including 1 gold at Rio 2016.

## Refugee Olympic Athletes (ROT)

The Refugee Olympic Athletes, NOC code ROT, were a team of refugees who competed under the Olympic flag at Rio 2016. In this data the team has 10 athletes in 3 sports: athletics, judo and swimming. The ROT code has no country in noc_regions, so the team's rows have no country; filter on noc = 'ROT' to find them. The Refugee Olympic Athletes did not win a medal.

## athlete_id

athlete_id is the unique number given to each athlete in the data, and it is the right way to count or group athletes. Names are not unique: 564 names in the Summer data belong to more than one athlete_id, so grouping by name would merge different people. The Summer data has 116,776 different athlete_ids. An athlete keeps the same athlete_id across all their events and Games, which is how career totals such as Michael Phelps's 28 medals are computed.
