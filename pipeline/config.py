"""Central configuration. Everything can be overridden with environment variables
so the same code runs locally, in Docker, and in CI without edits."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"            # landing zone: files exactly as downloaded
WAREHOUSE_PATH = Path(os.getenv("WAREHOUSE_PATH", DATA_DIR / "warehouse" / "divvy.duckdb"))
DBT_DIR = ROOT / "divvy_dbt"

# Source systems
DIVVY_URL = "https://divvy-tripdata.s3.amazonaws.com/{yyyymm}-divvy-tripdata.zip"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
CHICAGO_LAT, CHICAGO_LON = 41.8781, -87.6298

# Months to process (YYYY-MM). Summer months give the most interesting weather swings.
DEFAULT_MONTHS = os.getenv("MONTHS", "2025-06,2025-07,2025-08").split(",")

# Reliability settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
BACKOFF_SECONDS = float(os.getenv("BACKOFF_SECONDS", 2))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", 120))

TRIP_COLUMNS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id", "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
]
