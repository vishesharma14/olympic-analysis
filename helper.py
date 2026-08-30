import numpy as np
import pandas as pd


def medal_tally(df):
    medal_df = df.drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )

    medal_df = (
        medal_df.groupby('region')[['Gold', 'Silver', 'Bronze']]
        .sum()
        .sort_values('Gold', ascending=False)
        .reset_index()
    )
    medal_df.rename(columns={'region': 'Region'}, inplace=True)

    medal_df['Total'] = medal_df['Gold'] + medal_df['Silver'] + medal_df['Bronze']

    return medal_df


def country_year_list(df):
    years = df['Year'].unique().tolist()
    years.sort()
    years.insert(0, 'Overall')

    country = np.unique(df['region'].dropna().values).tolist()
    country.sort()
    country.insert(0, 'Overall')

    return years, country


def fetch_medal_tally(df, year, country):
    medal_df = df.drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )

    flag = 0

    if year == 'Overall' and country == 'Overall':
        temp_df = medal_df
    elif year == 'Overall' and country != 'Overall':
        flag = 1
        temp_df = medal_df[medal_df['region'] == country]
    elif year != 'Overall' and country == 'Overall':
        temp_df = medal_df[medal_df['Year'] == int(year)]
    else:
        temp_df = medal_df[
            (medal_df['Year'] == int(year)) &
            (medal_df['region'] == country)
        ]

    if temp_df.empty:
        cols = ['Year', 'Gold', 'Silver', 'Bronze', 'Total'] if flag == 1 else \
               ['region', 'Gold', 'Silver', 'Bronze', 'Total']
        return pd.DataFrame(columns=cols)

    if flag == 1:
        x = (
            temp_df.groupby('Year')[['Gold', 'Silver', 'Bronze']]
            .sum()
            .sort_values('Year')
            .reset_index()
        )
    else:
        x = (
            temp_df.groupby('region')[['Gold', 'Silver', 'Bronze']]
            .sum()
            .sort_values('Gold', ascending=False)
            .reset_index()
        )
        x.rename(columns={'region': 'Region'}, inplace=True)

    x['Total'] = x['Gold'] + x['Silver'] + x['Bronze']

    return x


def data_over_time(df, col):
    over_time = (
        df.drop_duplicates(['Year', col])
        .groupby('Year')[col]
        .count()
        .reset_index()
        .sort_values('Year')
    )

    over_time.columns = ['Edition', col]

    return over_time


def _top_athletes(df, sport, country=None, top_n=15):
    """
    Shared logic for most_successful / most_successful_countrywise.
    Returns the top medal-winning athletes, optionally filtered by
    sport and/or country.

    Deliberately avoids merging back into the full `df` — some source
    CSVs end up with a duplicated 'Name' column after upstream merges,
    which makes `df[['Name', ...]]` ambiguous and crashes any merge on
    'Name'. Aggregating directly on the already-filtered subset sidesteps
    that entirely and needs no merge.
    """
    temp_df = df.dropna(subset=['Medal']).copy()
    # Guard against any duplicate column labels slipping in from upstream.
    temp_df = temp_df.loc[:, ~temp_df.columns.duplicated()]

    if country is not None:
        temp_df = temp_df[temp_df['region'] == country]

    if sport != 'Overall':
        temp_df = temp_df[temp_df['Sport'] == sport]

    if temp_df.empty:
        cols = ['Name', 'Medals', 'Sport'] + ([] if country is not None else ['region'])
        return pd.DataFrame(columns=cols)

    agg_dict = {'Medals': ('Medal', 'count'), 'Sport': ('Sport', 'first')}
    if country is None:
        agg_dict['region'] = ('region', 'first')

    result = (
        temp_df.groupby('Name')
        .agg(**agg_dict)
        .reset_index()
        .sort_values('Medals', ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    return result


def most_successful(df, sport):
    return _top_athletes(df, sport, country=None, top_n=15)


def most_successful_countrywise(df, country):
    return _top_athletes(df, 'Overall', country=country, top_n=10).drop(columns=['region'], errors='ignore')


def yearwise_medal_tally(df, country):
    temp_df = df.dropna(subset=['Medal']).copy()
    temp_df = temp_df.drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )

    new_df = temp_df[temp_df['region'] == country]
    final_df = new_df.groupby('Year').count()['Medal'].reset_index()

    return final_df


def country_event_heatmap(df, country):
    temp_df = df.dropna(subset=['Medal']).copy()
    temp_df = temp_df.drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )

    new_df = temp_df[temp_df['region'] == country]
    pt = new_df.pivot_table(index='Sport', columns='Year', values='Medal', aggfunc='count').fillna(0)
    return pt


def weight_v_height(df, sport):
    athlete_df = df.drop_duplicates(subset=['Name', 'region']).copy()
    athlete_df['Medal'] = athlete_df['Medal'].fillna('No Medal')

    if sport == 'Overall':
        temp_df = athlete_df
    else:
        temp_df = athlete_df[athlete_df['Sport'] == sport]

    return temp_df


def men_vs_women(df):
    athlete_df = df.drop_duplicates(subset=['Name', 'region']).copy()
    men = athlete_df[athlete_df['Sex'] == 'M'].groupby('Year').count()['Name'].reset_index()
    women = athlete_df[athlete_df['Sex'] == 'F'].groupby('Year').count()['Name'].reset_index()

    final = men.merge(women, on='Year', how='left')
    final.rename(columns={'Name_x': 'Male', 'Name_y': 'Female'}, inplace=True)
    final.fillna(0, inplace=True)

    return final


def fun_facts(df):
    """
    Returns a dict of short, presentable 'did you know' style facts
    computed from the dataset. Missing data for any single fact is
    handled gracefully by simply omitting that key.
    """
    facts = {}
    medal_df = df.dropna(subset=['Medal']).copy()
    medal_df = medal_df.loc[:, ~medal_df.columns.duplicated()]

    if medal_df.empty:
        return facts

    # Youngest gold medalist
    gold_df = medal_df[(medal_df['Medal'] == 'Gold') & medal_df['Age'].notna()]
    if not gold_df.empty:
        row = gold_df.loc[gold_df['Age'].idxmin()]
        facts['youngest_gold'] = (
            f"{row['Name']}, age {row['Age']:.0f}, {row['Sport']} ({int(row['Year'])})"
        )

    # Oldest medalist (any medal)
    aged_df = medal_df[medal_df['Age'].notna()]
    if not aged_df.empty:
        row = aged_df.loc[aged_df['Age'].idxmax()]
        facts['oldest_medalist'] = (
            f"{row['Name']}, age {row['Age']:.0f}, {row['Sport']} ({int(row['Year'])})"
        )

    # Most decorated athlete (by individual medal-winning appearances)
    counts = medal_df['Name'].value_counts()
    if not counts.empty:
        facts['most_decorated'] = f"{counts.index[0]} — {int(counts.iloc[0])} medals"

    # Nation with the most gold medals of all time
    unique_golds = medal_df[medal_df['Medal'] == 'Gold'].drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )
    gold_counts = unique_golds['region'].value_counts()
    if not gold_counts.empty:
        facts['top_gold_nation'] = f"{gold_counts.index[0]} — {int(gold_counts.iloc[0])} golds"

    # Olympics edition with the most participating nations
    nations_per_year = df.drop_duplicates(['Year', 'region']).groupby('Year')['region'].count()
    if not nations_per_year.empty:
        peak_year = nations_per_year.idxmax()
        facts['most_nations_year'] = f"{int(peak_year)} — {int(nations_per_year.max())} nations"

    return facts


def medal_map_data(df, year='Overall'):
    """
    Aggregated Gold/Silver/Bronze/Total medal counts per country,
    suitable for a choropleth map. `year='Overall'` covers all editions.
    """
    medal_df = df.drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )

    if year != 'Overall':
        medal_df = medal_df[medal_df['Year'] == int(year)]

    agg = (
        medal_df.dropna(subset=['region'])
        .groupby('region')[['Gold', 'Silver', 'Bronze']]
        .sum()
        .reset_index()
    )
    agg['Total'] = agg['Gold'] + agg['Silver'] + agg['Bronze']
    agg.rename(columns={'region': 'Country'}, inplace=True)

    return agg


def medal_race_data(df, top_n=10):
    """
    Cumulative medal count per country per year, restricted to the
    top_n countries by final cumulative total — built for an animated
    'bar chart race' style visualization.
    """
    medal_df = df.drop_duplicates(
        subset=['Team', 'NOC', 'Year', 'Season', 'City', 'Sport', 'Event', 'Medal']
    )

    yearly = (
        medal_df.dropna(subset=['region'])
        .groupby(['Year', 'region'])[['Gold', 'Silver', 'Bronze']]
        .sum()
        .reset_index()
    )
    yearly['Total'] = yearly['Gold'] + yearly['Silver'] + yearly['Bronze']
    yearly.sort_values('Year', inplace=True)
    yearly['Cumulative'] = yearly.groupby('region')['Total'].cumsum()

    top_countries = (
        yearly.groupby('region')['Cumulative'].max().nlargest(top_n).index.tolist()
    )
    race_df = yearly[yearly['region'].isin(top_countries)].copy()

    return race_df