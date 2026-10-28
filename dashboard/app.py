"""Streamlit dashboard: reads ONLY the marts schema (the curated layer).

    streamlit run dashboard/app.py
"""

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB = Path(os.getenv("WAREHOUSE_PATH", Path(__file__).resolve().parent.parent / "data/warehouse/divvy.duckdb"))

st.set_page_config(page_title="Divvy Ridership & Weather", layout="wide")
st.title("Chicago Divvy Ridership vs. Weather")


@st.cache_data(ttl=300)
def q(sql: str) -> pd.DataFrame:
    with duckdb.connect(str(DB), read_only=True) as con:
        return con.execute(sql).df()


if not DB.exists():
    st.error(f"No warehouse found at {DB}. Run `python -m pipeline.run` first.")
    st.stop()

daily = q("select * from marts.mart_daily_ridership")
stations = q("select * from marts.mart_station_activity limit 10")
dq = q("select * from marts.mart_data_quality")
runs = q("select * from raw.pipeline_runs order by logged_at desc limit 10")

# ---- KPIs ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Valid rides", f"{int(daily.total_rides.sum()):,}")
c2.metric("Member share", f"{daily.member_rides.sum() / daily.total_rides.sum():.0%}")
dry = daily.loc[~daily.is_rainy_day, "total_rides"].mean()
wet = daily.loc[daily.is_rainy_day, "total_rides"].mean()
c3.metric("Rainy-day effect", f"{(wet - dry) / dry:+.0%}" if pd.notna(wet) else "n/a",
          help="Average rides on days with ≥0.1in rain vs dry days")
c4.metric("Rows passing quality checks", f"{dq.valid_rows.sum() / dq.raw_rows.sum():.1%}")

# ---- Ridership vs weather ----
st.subheader("Daily rides and temperature")
st.line_chart(daily.set_index("ride_date")[["member_rides", "casual_rides"]])

left, right = st.columns(2)
with left:
    st.subheader("Rides vs. high temperature")
    st.scatter_chart(daily, x="temp_max_f", y="total_rides", color="is_rainy_day")
with right:
    st.subheader("Top 10 start stations")
    st.bar_chart(stations.set_index("station_name")[["member_departures", "casual_departures"]], horizontal=True)

# ---- Pipeline health ----
st.subheader("Data quality by source month")
st.dataframe(dq, hide_index=True, width="stretch")
st.subheader("Recent pipeline runs")
st.dataframe(runs, hide_index=True, width="stretch")
