"""LOAD: copy landed files into the warehouse's `raw` schema.

Loads are idempotent: each month is deleted and re-inserted, so re-running a
month never creates duplicates. Every row carries `_source_month` and
`_loaded_at` for lineage.
"""

import json
from pathlib import Path

import duckdb

from pipeline import config
from pipeline.utils import get_logger

log = get_logger(__name__)


def connect() -> duckdb.DuckDBPyConnection:
    config.WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.WAREHOUSE_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.trips (
            ride_id VARCHAR, rideable_type VARCHAR, started_at VARCHAR, ended_at VARCHAR,
            start_station_name VARCHAR, start_station_id VARCHAR,
            end_station_name VARCHAR, end_station_id VARCHAR,
            start_lat DOUBLE, start_lng DOUBLE, end_lat DOUBLE, end_lng DOUBLE,
            member_casual VARCHAR, _source_month VARCHAR, _loaded_at TIMESTAMP
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.weather_daily (
            date DATE, temp_max_f DOUBLE, temp_min_f DOUBLE,
            precipitation_in DOUBLE, wind_max_mph DOUBLE,
            _source_month VARCHAR, _loaded_at TIMESTAMP
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.pipeline_runs (
            run_id VARCHAR, month VARCHAR, step VARCHAR, status VARCHAR,
            rows_loaded BIGINT, detail VARCHAR, logged_at TIMESTAMP
        )""")
    return con


def load_trips(con, month: str, path: Path) -> int:
    cols = ", ".join(config.TRIP_COLUMNS)
    con.execute("BEGIN")
    con.execute("DELETE FROM raw.trips WHERE _source_month = ?", [month])
    # Read every column as text: typing/cleaning is dbt's job, not the loader's.
    con.execute(f"""
        INSERT INTO raw.trips
        SELECT {cols}, ? AS _source_month, now() AS _loaded_at
        FROM read_csv(?, header = true, all_varchar = true)
    """, [month, str(path)])
    con.execute("COMMIT")
    n = con.execute("SELECT count(*) FROM raw.trips WHERE _source_month = ?", [month]).fetchone()[0]
    log.info("Loaded %s trips for %s", f"{n:,}", month)
    return n


def load_weather(con, month: str, path: Path) -> int:
    daily = json.loads(path.read_text())["daily"]
    rows = list(zip(
        daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"],
        daily["precipitation_sum"], daily["wind_speed_10m_max"],
    ))
    con.execute("BEGIN")
    con.execute("DELETE FROM raw.weather_daily WHERE _source_month = ?", [month])
    con.executemany(
        "INSERT INTO raw.weather_daily VALUES (?, ?, ?, ?, ?, ?, now())",
        [(*r, month) for r in rows],
    )
    con.execute("COMMIT")
    log.info("Loaded %d weather days for %s", len(rows), month)
    return len(rows)


def log_run(con, run_id: str, month: str, step: str, status: str, rows: int = 0, detail: str = ""):
    con.execute(
        "INSERT INTO raw.pipeline_runs VALUES (?, ?, ?, ?, ?, ?, now())",
        [run_id, month, step, status, rows, detail[:500]],
    )
