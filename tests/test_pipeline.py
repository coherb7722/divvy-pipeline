"""Unit tests for the Python side (dbt tests cover the SQL side).

    pytest -q
"""

import pytest

from pipeline import config, load, sample_data
from pipeline.extract import month_bounds, pick_csv_name
from pipeline.utils import with_retries


def test_month_bounds_handles_month_lengths():
    assert month_bounds("2025-02") == ("2025-02-01", "2025-02-28")
    assert month_bounds("2024-02") == ("2024-02-01", "2024-02-29")  # leap year
    assert month_bounds("2025-07") == ("2025-07-01", "2025-07-31")


def test_pick_csv_ignores_macos_junk():
    names = ["__MACOSX/._202507-divvy-tripdata.csv", "202507-divvy-tripdata.csv"]
    assert pick_csv_name(names) == "202507-divvy-tripdata.csv"


def test_pick_csv_rejects_ambiguous_zip():
    with pytest.raises(ValueError):
        pick_csv_name(["a.csv", "b.csv"])


def test_retry_recovers_from_transient_failure(monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_SECONDS", 0)
    calls = {"n": 0}

    @with_retries
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("network blip")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_retry_gives_up_eventually(monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_SECONDS", 0)

    @with_retries
    def always_fails():
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        always_fails()


def test_load_is_idempotent(tmp_path, monkeypatch):
    """Loading the same month twice must not duplicate rows."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "WAREHOUSE_PATH", tmp_path / "wh.duckdb")
    sample_data.generate(["2025-07"], rides_per_day=10)
    path = config.RAW_DIR / "trips" / "2025-07.csv"

    con = load.connect()
    first = load.load_trips(con, "2025-07", path)
    second = load.load_trips(con, "2025-07", path)
    total = con.execute("select count(*) from raw.trips").fetchone()[0]
    con.close()

    assert first == second == total > 0
