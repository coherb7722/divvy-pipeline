"""EXTRACT: pull raw data from the two source systems into the landing zone.

- Divvy trips: monthly zipped CSV files on a public S3 bucket.
- Weather: daily history for Chicago from the Open-Meteo archive API (JSON).

Files are written untouched (raw) so we can always re-load or re-transform
without hitting the source again.
"""

import io
import json
import zipfile
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

import requests

from pipeline import config
from pipeline.utils import get_logger, with_retries

log = get_logger(__name__)


def month_bounds(month: str) -> tuple[str, str]:
    """'2025-07' -> ('2025-07-01', '2025-07-31')"""
    year, mon = map(int, month.split("-"))
    return f"{month}-01", f"{month}-{monthrange(year, mon)[1]:02d}"


def pick_csv_name(names: list[str]) -> str:
    """Divvy zips sometimes include macOS junk folders; pick the real CSV."""
    candidates = [n for n in names if n.endswith(".csv") and not n.startswith("__MACOSX")]
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one trip CSV in zip, found: {candidates}")
    return candidates[0]


@with_retries
def extract_trips(month: str) -> Path:
    out = config.RAW_DIR / "trips" / f"{month}.csv"
    if out.exists():
        log.info("Trips %s already landed, skipping download", month)
        return out
    url = config.DIVVY_URL.format(yyyymm=month.replace("-", ""))
    log.info("Downloading %s", url)
    resp = requests.get(url, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        data = zf.read(pick_csv_name(zf.namelist()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    log.info("Landed trips %s (%.1f MB)", month, len(data) / 1e6)
    return out


@with_retries
def extract_weather(month: str) -> Path:
    out = config.RAW_DIR / "weather" / f"{month}.json"
    if out.exists():
        log.info("Weather %s already landed, skipping", month)
        return out
    start, end = month_bounds(month)
    # Divvy files each ride under the month it ENDED, so a ride starting late
    # on the last day of the previous month is in this month's file. Fetch one
    # extra day before the month so every ride has a weather row.
    start = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
    params = {
        "latitude": config.CHICAGO_LAT,
        "longitude": config.CHICAGO_LON,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "wind_speed_unit": "mph",
        "timezone": "America/Chicago",
    }
    resp = requests.get(config.WEATHER_URL, params=params, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if "daily" not in payload:
        raise ValueError(f"Unexpected weather response: {payload}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload))
    log.info("Landed weather %s (%d days)", month, len(payload["daily"]["time"]))
    return out
