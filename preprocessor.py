import pandas as pd
import streamlit as st


@st.cache_data(show_spinner="Loading Olympics data...")
def preprocess():
    """
    Loads, cleans, and merges the Olympics athlete + region datasets.
    Cached so the CSVs are only read/merged once per session instead of
    on every widget interaction (Streamlit reruns the whole script on
    every click, so this decorator is what makes the app feel fast).
    """
    df = pd.read_csv('athlete_events.csv')
    region_df = pd.read_csv('noc_regions.csv')

    # Filter for Summer Olympics only
    df = df[df['Season'] == 'Summer']

    # Merge with region data
    df = df.merge(region_df, on='NOC', how='left')

    # Drop exact duplicate rows
    df.drop_duplicates(inplace=True)

    # One-hot encode medals (Gold / Silver / Bronze columns of 0/1)
    medal_dummies = pd.get_dummies(df['Medal'], dtype=int)
    df = pd.concat([df, medal_dummies], axis=1)

    # Safety net: if the merge or source CSVs ever produce a duplicate
    # column label (e.g. two 'Name' columns), keep only the first —
    # duplicate labels silently break any later selection/merge on that name.
    df = df.loc[:, ~df.columns.duplicated()]

    return df