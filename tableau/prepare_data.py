"""
prepare_data.py
---------------
Builds two tidy CSVs for the Tableau dashboard from the raw dataset, using the same
rules as the Streamlit app (Summer Games only, team medals counted once per country):

- tableau/medals.csv                  one row per Games x country x sport, with medal counts
- tableau/participation_by_year.csv   athletes, women's share, nations, sports and events per Games

Run from anywhere:
    python tableau/prepare_data.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tableau"

# Region names in noc_regions.csv that Tableau's map does not recognise as written.
MAP_NAMES = {
    "UK": "United Kingdom",
    "USA": "United States",
    "Boliva": "Bolivia",
    "Trinidad": "Trinidad and Tobago",
    "Antigua": "Antigua and Barbuda",
    "Saint Kitts": "Saint Kitts and Nevis",
    "Saint Vincent": "Saint Vincent and the Grenadines",
    "Virgin Islands, US": "U.S. Virgin Islands",
    "Virgin Islands, British": "British Virgin Islands",
    "Republic of Congo": "Congo",
    "Ivory Coast": "Côte d'Ivoire",
    "Macedonia": "North Macedonia",
    "Swaziland": "Eswatini",
}


def load() -> pd.DataFrame:
    events = pd.read_csv(ROOT / "athlete_events.csv")
    regions = pd.read_csv(ROOT / "noc_regions.csv")
    df = events[events["Season"] == "Summer"].merge(regions, on="NOC", how="left")
    return df.drop_duplicates()


def build_medals(df: pd.DataFrame) -> pd.DataFrame:
    medals = df.dropna(subset=["Medal", "region"]).drop_duplicates(
        subset=["Team", "NOC", "Year", "Season", "City", "Sport", "Event", "Medal"]
    )
    counts = (
        medals.groupby(["Year", "region", "Sport", "Medal"]).size()
        .unstack("Medal", fill_value=0)
        .reindex(columns=["Gold", "Silver", "Bronze"], fill_value=0)
        .reset_index()
        .rename(columns={"region": "Country"})
    )
    counts["Total"] = counts[["Gold", "Silver", "Bronze"]].sum(axis=1)
    counts.insert(2, "Map Country", counts["Country"].replace(MAP_NAMES))
    return counts.sort_values(["Year", "Country", "Sport"]).reset_index(drop=True)


def build_participation(df: pd.DataFrame) -> pd.DataFrame:
    per_year = df.groupby("Year").agg(
        Athletes=("ID", "nunique"),
        Nations=("region", "nunique"),
        Sports=("Sport", "nunique"),
        Events=("Event", "nunique"),
    )
    per_year["Women"] = df[df["Sex"] == "F"].groupby("Year")["ID"].nunique()
    per_year["Women"] = per_year["Women"].fillna(0).astype(int)
    per_year["Men"] = df[df["Sex"] == "M"].groupby("Year")["ID"].nunique()
    per_year["Women %"] = (100 * per_year["Women"] / per_year["Athletes"]).round(1)
    return per_year.reset_index()[["Year", "Athletes", "Women", "Men", "Women %", "Nations", "Sports", "Events"]]


def main() -> None:
    df = load()
    medals = build_medals(df)
    participation = build_participation(df)
    medals.to_csv(OUT_DIR / "medals.csv", index=False)
    participation.to_csv(OUT_DIR / "participation_by_year.csv", index=False)
    print(f"tableau/medals.csv: {len(medals):,} rows, {int(medals['Total'].sum()):,} medals")
    print(f"tableau/participation_by_year.csv: {len(participation)} rows")


if __name__ == "__main__":
    main()
