import streamlit as st
import pandas as pd
import preprocessor
import helper
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go

# ----------------------------------------------------------------------------
# Page configuration
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Olympics Analysis Dashboard",
    page_icon="🏅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# Global styling
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* Tighter top padding */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        /* Section headers */
        h1, h2, h3 {
            font-family: 'Segoe UI', sans-serif;
        }

        /* Metric cards */
        div[data-testid="stMetric"] {
            background-color: rgba(240, 242, 246, 0.06);
            border: 1px solid rgba(120, 120, 120, 0.25);
            border-radius: 12px;
            padding: 14px 10px;
            text-align: center;
        }
        div[data-testid="stMetricLabel"] {
            justify-content: center;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.6rem;
        }

        /* Sidebar branding */
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(120, 120, 120, 0.2);
        }

        /* Tables */
        .stTable, .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
        }

        hr {
            margin: 0.6rem 0 1.2rem 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

PLOTLY_TEMPLATE = "plotly_dark"

# ----------------------------------------------------------------------------
# Data load (cached inside preprocessor.preprocess)
# ----------------------------------------------------------------------------
df = preprocessor.preprocess()

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.markdown(
    """
    <div style="text-align:center; padding-bottom: 6px;">
        <h1 style="margin-bottom:0;">🏅</h1>
        <h2 style="margin-top:4px; margin-bottom:0;">Olympics Analysis</h2>
        <p style="color:gray; margin-top:2px;">Interactive Data Dashboard</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

user_menu = st.sidebar.radio(
    "Explore Dashboard",
    (
        "Medal Tally",
        "Overall Analysis",
        "Country-Wise Analysis",
        "Athlete Wise Analysis",
        "Ask the data",
    ),
)
st.sidebar.caption("New: ask questions in plain English")

st.sidebar.markdown("---")
st.sidebar.caption("Data: 120 years of Olympic history (Athlete Events)")

# ----------------------------------------------------------------------------
# Medal Tally
# ----------------------------------------------------------------------------
if user_menu == "Medal Tally":
    st.sidebar.header("Filters")
    years, country = helper.country_year_list(df)
    selected_year = st.sidebar.selectbox("Select Year", years)
    selected_country = st.sidebar.selectbox("Select Country", country)

    medal_tally = helper.fetch_medal_tally(df, selected_year, selected_country)

    if selected_year == "Overall" and selected_country == "Overall":
        title = "Overall Medal Tally"
    elif selected_year != "Overall" and selected_country == "Overall":
        title = f"Medal Tally — {selected_year} Olympics"
    elif selected_year == "Overall" and selected_country != "Overall":
        title = f"{selected_country} — Overall Performance"
    else:
        title = f"{selected_country} — Performance in {selected_year} Olympics"

    st.title(title)

    if medal_tally.empty:
        st.info("No medal data available for this selection.")
    else:
        totals = medal_tally[["Gold", "Silver", "Bronze"]].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🥇 Gold", int(totals["Gold"]))
        c2.metric("🥈 Silver", int(totals["Silver"]))
        c3.metric("🥉 Bronze", int(totals["Bronze"]))
        c4.metric("🏆 Total", int(totals.sum()))
        st.markdown("---")
        st.dataframe(medal_tally, width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# Overall Analysis
# ----------------------------------------------------------------------------
if user_menu == "Overall Analysis":
    editions = df["Year"].unique().shape[0] - 1
    cities = df["City"].unique().shape[0]
    sports = df["Sport"].unique().shape[0]
    events = df["Event"].unique().shape[0]
    athletes = df["Name"].unique().shape[0]
    nations = df["region"].unique().shape[0]

    st.title("Olympics Overview")
    st.caption("Key figures across the full history of the Summer Games")

    col1, col2, col3 = st.columns(3)
    col1.metric("🏟️ Olympic Editions", editions)
    col2.metric("🌍 Host Cities", cities)
    col3.metric("🏅 Sports", sports)

    col1, col2, col3 = st.columns(3)
    col1.metric("🎯 Events", events)
    col2.metric("🌎 Nations", nations)
    col3.metric("🏃 Athletes", athletes)

    st.markdown("---")

    facts = helper.fun_facts(df)
    if facts:
        st.subheader("✨ Did You Know?")
        fc1, fc2 = st.columns(2)
        fc3, fc4 = st.columns(2)
        if "youngest_gold" in facts:
            fc1.info(f"**Youngest gold medalist**\n\n{facts['youngest_gold']}")
        if "oldest_medalist" in facts:
            fc2.info(f"**Oldest medalist**\n\n{facts['oldest_medalist']}")
        if "most_decorated" in facts:
            fc3.success(f"**Most decorated athlete**\n\n{facts['most_decorated']}")
        if "top_gold_nation" in facts:
            fc4.success(f"**Most golds, all-time**\n\n{facts['top_gold_nation']}")
        if "most_nations_year" in facts:
            st.warning(f"**Biggest Olympics by participation** — {facts['most_nations_year']}")

    st.markdown("---")

    st.subheader("Participating Nations Over the Years")
    nations_over_time = helper.data_over_time(df, "region")
    fig = px.line(
        nations_over_time,
        x="Edition",
        y="region",
        markers=True,
    )
    fig.update_layout(
        height=420,
        xaxis_title="Olympic Year",
        yaxis_title="Number of Nations",
        template=PLOTLY_TEMPLATE,
        margin=dict(t=20),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.subheader("🗺️ Medals by Country")
    map_years = ["Overall"] + sorted(df["Year"].unique().tolist())
    map_year = st.selectbox("Select Year for Map", map_years, key="map_year")
    map_df = helper.medal_map_data(df, map_year)

    if map_df.empty:
        st.info("No medal data available for this selection.")
    else:
        fig = px.choropleth(
            map_df,
            locations="Country",
            locationmode="country names",
            color="Total",
            hover_name="Country",
            hover_data={"Gold": True, "Silver": True, "Bronze": True, "Total": True, "Country": False},
            color_continuous_scale="YlOrRd",
        )
        fig.update_layout(
            template=PLOTLY_TEMPLATE,
            height=480,
            margin=dict(t=10, b=0),
            geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False),
        )
        st.plotly_chart(fig, width="stretch")
        st.caption("Countries with no matching name in the map's country list are omitted from shading.")

    st.markdown("---")
    st.subheader("🏁 Medal Race: Top 10 Nations Over Time")
    race_df = helper.medal_race_data(df, top_n=10)
    if race_df.empty:
        st.info("Not enough data to build the medal race.")
    else:
        fig = px.bar(
            race_df,
            x="Cumulative",
            y="region",
            color="region",
            orientation="h",
            animation_frame="Year",
            range_x=[0, race_df["Cumulative"].max() * 1.1],
            labels={"Cumulative": "Cumulative Medals", "region": ""},
        )
        fig.update_layout(
            template=PLOTLY_TEMPLATE,
            height=520,
            showlegend=False,
            margin=dict(t=10),
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig, width="stretch")
        st.caption("Press ▶ to watch the top 10 medal-winning nations build their totals across every Olympics.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Events Over the Years")
        events_over_time = helper.data_over_time(df, "Event")
        fig = px.line(events_over_time, x="Edition", y="Event", markers=True)
        fig.update_layout(template=PLOTLY_TEMPLATE, height=380, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")

    with col_b:
        st.subheader("Athletes Over the Years")
        athlete_over_time = helper.data_over_time(df, "Name")
        fig = px.line(athlete_over_time, x="Edition", y="Name", markers=True)
        fig.update_layout(template=PLOTLY_TEMPLATE, height=380, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.subheader("Number of Events Across Sports Over the Years")
    with st.expander("Show heatmap", expanded=True):
        x = df.drop_duplicates(["Year", "Sport", "Event"])
        pivot = (
            x.pivot_table(index="Sport", columns="Year", values="Event", aggfunc="count")
            .fillna(0)
            .astype("int")
        )
        fig, ax = plt.subplots(figsize=(20, 20))
        sns.heatmap(pivot, annot=True, fmt="d", cmap="mako", ax=ax)
        st.pyplot(fig)

    st.markdown("---")
    st.subheader("🏅 Top 15 Most Successful Olympic Athletes")
    sport_list = df["Sport"].unique().tolist()
    sport_list.sort()
    sport_list.insert(0, "Overall")

    selected_sport = st.selectbox("Explore Athletes by Sport", sport_list)
    top_athletes = helper.most_successful(df, selected_sport)
    st.dataframe(top_athletes, width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# Country-Wise Analysis
# ----------------------------------------------------------------------------
if user_menu == "Country-Wise Analysis":
    st.sidebar.header("Filters")
    country_list = df["region"].dropna().unique().tolist()
    country_list.sort()
    selected_country = st.sidebar.selectbox("Select a Country", country_list)

    st.title(f"{selected_country} — Country Analysis")

    country_df = helper.yearwise_medal_tally(df, selected_country)
    st.subheader(f"Medal Tally Over the Years")
    if country_df.empty:
        st.info(f"No medal data available for {selected_country}.")
    else:
        fig = px.line(country_df, x="Year", y="Medal", markers=True)
        fig.update_layout(template=PLOTLY_TEMPLATE, height=400, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.subheader(f"Medal Performance by Sport")
    pt = helper.country_event_heatmap(df, selected_country)
    if pt.empty:
        st.info(f"No sport-wise medal data available for {selected_country}.")
    else:
        with st.expander("Show heatmap", expanded=True):
            fig, ax = plt.subplots(figsize=(20, 20))
            sns.heatmap(pt, annot=True, fmt=".0f", cmap="rocket_r", ax=ax)
            st.pyplot(fig)

    st.markdown("---")
    st.subheader(f"Top 10 Athletes of {selected_country}")
    top10_df = helper.most_successful_countrywise(df, selected_country)
    if top10_df.empty:
        st.info(f"No athlete data available for {selected_country}.")
    else:
        st.dataframe(top10_df, width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# Athlete-Wise Analysis
# ----------------------------------------------------------------------------
if user_menu == "Athlete Wise Analysis":
    st.title("Athlete Insights")

    athlete_df = df.drop_duplicates(subset=["Name", "region"])

    st.subheader("Age Distribution of Olympic Medalists by Medal Type")
    fig = px.histogram(
        df,
        x="Age",
        color="Medal",
        marginal="box",
        barmode="overlay",
    )
    fig.update_layout(template=PLOTLY_TEMPLATE, height=450, margin=dict(t=20))
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.subheader("Age Distribution of Gold Medalists Across Sports")

    famous_sports = [
        "Basketball", "Judo", "Football", "Tug-Of-War", "Athletics", "Swimming",
        "Badminton", "Sailing", "Gymnastics", "Art Competitions", "Handball",
        "Weightlifting", "Wrestling", "Water Polo", "Hockey", "Rowing", "Fencing",
        "Shooting", "Boxing", "Taekwondo", "Cycling", "Diving", "Canoeing",
        "Tennis", "Golf", "Softball", "Archery", "Volleyball",
        "Synchronized Swimming", "Table Tennis", "Baseball", "Rhythmic Gymnastics",
        "Rugby Sevens", "Beach Volleyball", "Triathlon", "Rugby", "Polo", "Ice Hockey",
    ]

    x, name = [], []
    for sport in famous_sports:
        temp_df = athlete_df[athlete_df["Sport"] == sport]
        ages = temp_df[temp_df["Medal"] == "Gold"]["Age"].dropna()
        if not ages.empty:
            x.append(ages)
            name.append(sport)

    fig = go.Figure()
    for ages, sport in zip(x, name):
        fig.add_trace(
            go.Histogram(x=ages, name=sport, histnorm="probability density", opacity=0.5)
        )
    fig.update_layout(
        barmode="overlay",
        xaxis_title="Age",
        yaxis_title="Density",
        template=PLOTLY_TEMPLATE,
        height=450,
        margin=dict(t=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.subheader("Height vs Weight of Olympic Athletes")
    sport_list = df["Sport"].unique().tolist()
    sport_list.sort()
    sport_list.insert(0, "Overall")
    selected_sport = st.selectbox("Explore Athletes by Sport", sport_list)

    temp_df = helper.weight_v_height(df, selected_sport)
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.scatterplot(
        data=temp_df, x="Weight", y="Height", hue="Medal", style="Sex", s=90, ax=ax
    )
    ax.set_title("Relationship Between Athlete Weight and Height")
    ax.set_xlabel("Weight (kg)")
    ax.set_ylabel("Height (cm)")
    st.pyplot(fig)

    st.markdown("---")
    st.subheader("Male vs Female Olympic Participation Over Time")
    final = helper.men_vs_women(df)
    fig = px.line(final, x="Year", y=["Male", "Female"], markers=True)
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=420,
        margin=dict(t=20),
        yaxis_title="Number of Athletes",
        legend_title="Gender",
    )
    st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------------------------
# Ask the data (imported only here, so the other pages never load the chatbot)
# ----------------------------------------------------------------------------
if user_menu == "Ask the data":
    from chatbot import ui as chatbot_ui

    chatbot_ui.render()

