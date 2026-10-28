"""Generate small, realistic sample files in the exact source formats.

Used by CI and for offline demos so the full pipeline runs without the
internet. Deliberately includes dirty rows (negative durations, missing
stations, duplicate ride IDs, multi-day rides) so the data-quality layer has
something to catch.
"""

import json
import random
import uuid
from datetime import datetime, timedelta

import pandas as pd

from pipeline import config
from pipeline.extract import month_bounds

STATIONS = [
    ("Streeter Dr & Grand Ave", "13022", 41.8923, -87.6120),
    ("DuSable Lake Shore Dr & Monroe St", "13300", 41.8810, -87.6168),
    ("Clinton St & Washington Blvd", "WL-012", 41.8834, -87.6412),
    ("Kingsbury St & Kinzie St", "KA1503000043", 41.8892, -87.6385),
    ("Wells St & Concord Ln", "TA1308000050", 41.9121, -87.6348),
    ("Theater on the Lake", "TA1308000001", 41.9263, -87.6308),
    ("University Ave & 57th St", "KA1503000071", 41.7915, -87.5999),
    ("Wilton Ave & Belmont Ave", "TA1307000134", 41.9401, -87.6528),
]


def make_weather(month: str, rng: random.Random) -> dict:
    start, end = month_bounds(month)
    # Like the real extract, include the day before the month (boundary rides)
    days = pd.date_range(pd.Timestamp(start) - pd.Timedelta(days=1), end)
    tmax = [round(rng.gauss(82, 7), 1) for _ in days]
    return {
        "latitude": config.CHICAGO_LAT, "longitude": config.CHICAGO_LON,
        "daily": {
            "time": [d.strftime("%Y-%m-%d") for d in days],
            "temperature_2m_max": tmax,
            "temperature_2m_min": [round(t - rng.uniform(12, 20), 1) for t in tmax],
            "precipitation_sum": [round(max(0, rng.gauss(0, 0.35)), 2) for _ in days],
            "wind_speed_10m_max": [round(rng.uniform(6, 25), 1) for _ in days],
        },
    }


def make_trips(month: str, weather: dict, rng: random.Random, rides_per_day: int) -> pd.DataFrame:
    rows = []
    daily = weather["daily"]
    for day, tmax, rain in zip(daily["time"], daily["temperature_2m_max"], daily["precipitation_sum"]):
        if not day.startswith(month):
            # The day before the month: only a few late-night rides that end
            # after midnight land in this month's file, exactly like real Divvy data.
            for _ in range(3):
                s, e = rng.sample(STATIONS, 2)
                start = datetime.fromisoformat(day) + timedelta(hours=23, minutes=rng.randint(45, 58))
                rows.append({
                    "ride_id": uuid.UUID(int=rng.getrandbits(128)).hex[:16].upper(),
                    "rideable_type": "classic_bike",
                    "started_at": start.strftime("%Y-%m-%d %H:%M:%S.000"),
                    "ended_at": (start + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S.000"),
                    "start_station_name": s[0], "start_station_id": s[1],
                    "end_station_name": e[0], "end_station_id": e[1],
                    "start_lat": s[2], "start_lng": s[3], "end_lat": e[2], "end_lng": e[3],
                    "member_casual": "casual",
                })
            continue
        # Rain suppresses ridership, warm days boost it: gives the dashboard a real signal
        n = int(rides_per_day * (1 - min(rain, 1.0) * 0.6) * (0.7 + max(0, tmax - 60) / 100))
        is_weekend = datetime.fromisoformat(day).weekday() >= 5
        for _ in range(n):
            s, e = rng.sample(STATIONS, 2)
            hour = rng.choice([7, 8, 8, 9, 12, 16, 17, 17, 18, 19] if not is_weekend else list(range(9, 21)))
            start = datetime.fromisoformat(day) + timedelta(hours=hour, minutes=rng.randint(0, 59))
            member = rng.random() < (0.45 if is_weekend else 0.68)
            mins = rng.lognormvariate(2.4 if member else 2.9, 0.5)
            rows.append({
                "ride_id": uuid.UUID(int=rng.getrandbits(128)).hex[:16].upper(),
                "rideable_type": rng.choice(["classic_bike", "electric_bike", "electric_scooter"]),
                "started_at": start.strftime("%Y-%m-%d %H:%M:%S.000"),
                "ended_at": (start + timedelta(minutes=mins)).strftime("%Y-%m-%d %H:%M:%S.000"),
                "start_station_name": s[0], "start_station_id": s[1],
                "end_station_name": e[0], "end_station_id": e[1],
                "start_lat": s[2], "start_lng": s[3], "end_lat": e[2], "end_lng": e[3],
                "member_casual": "member" if member else "casual",
            })
    df = pd.DataFrame(rows, columns=config.TRIP_COLUMNS)

    # --- inject realistic dirt ---
    idx = df.sample(frac=0.01, random_state=1).index          # ended before it started
    df.loc[idx, "ended_at"] = (pd.to_datetime(df.loc[idx, "started_at"]) - timedelta(minutes=3)).dt.strftime("%Y-%m-%d %H:%M:%S.000")
    idx = df.sample(frac=0.03, random_state=2).index          # dockless e-bike: no station
    df.loc[idx, ["start_station_name", "start_station_id"]] = None
    idx = df.sample(frac=0.002, random_state=3).index         # bike never returned (> 24h)
    df.loc[idx, "ended_at"] = (pd.to_datetime(df.loc[idx, "started_at"]) + timedelta(days=2)).dt.strftime("%Y-%m-%d %H:%M:%S.000")
    dupes = df.sample(frac=0.002, random_state=4)             # duplicate records from source
    return pd.concat([df, dupes], ignore_index=True)


def generate(months: list[str], rides_per_day: int = 150, seed: int = 42) -> None:
    rng = random.Random(seed)
    for month in months:
        weather = make_weather(month, rng)
        (config.RAW_DIR / "weather").mkdir(parents=True, exist_ok=True)
        (config.RAW_DIR / "weather" / f"{month}.json").write_text(json.dumps(weather))
        trips = make_trips(month, weather, rng, rides_per_day)
        (config.RAW_DIR / "trips").mkdir(parents=True, exist_ok=True)
        trips.to_csv(config.RAW_DIR / "trips" / f"{month}.csv", index=False)
        print(f"Sample {month}: {len(trips):,} trips, {len(weather['daily']['time'])} weather days")


if __name__ == "__main__":
    generate(config.DEFAULT_MONTHS)
