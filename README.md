# Divvy Ridership & Weather Pipeline

An end-to-end **ELT data pipeline** that answers a simple business question:

> **How does weather change bike-share ridership in Chicago, and does it affect members and casual riders differently?**

It pulls two independent public sources, lands them untouched, loads them into a warehouse, transforms and tests them with dbt, and serves a dashboard. One command runs it locally or in Docker, and CI runs every test on every commit.

```
 Sources                 Landing zone          Warehouse (DuckDB)                                  Serve
 ───────                 ────────────          ──────────────────────────────────────────          ─────
 Divvy S3 (zip/CSV) ──┐                        raw ──► staging ──► intermediate ──► marts ──►  Streamlit
                      ├─► Python extract ─► data/raw/  (load)  (clean/type) (quality flags) (facts/aggs)  dashboard
 Open-Meteo API (JSON)┘   retries+backoff     files                       dbt build = models + tests
                                                                         │
                              raw.pipeline_runs (run log) ◄──────────────┘
         CI: GitHub Actions ─ pytest ─► full pipeline on sample data ─► docker build
```

## Tech stack and why

| Layer | Tool | Why this choice |
|---|---|---|
| Extract / load | **Python** (`requests`, `duckdb`) | Simple, testable; retries with exponential backoff for flaky networks |
| Warehouse | **DuckDB** | Runs in a single file with zero setup and real columnar SQL. Same role as Snowflake/Databricks at small scale |
| Transform + test | **dbt** | SQL models in layers, dependency graph, built-in data tests, docs. Swap the profile to Snowflake and the models run unchanged |
| Serve | **Streamlit** | A dashboard in ~60 lines of Python that reads only the curated `marts` layer |
| Package | **Docker / Compose** | Same environment everywhere; the dashboard only starts after the pipeline succeeds |
| CI | **GitHub Actions** | Unit tests + full pipeline + all data tests on each push |

## Design decisions

- **ELT, not ETL.** Raw data is loaded as text, exactly as published. All cleaning happens in SQL in the warehouse, so it is versioned, testable, and re-runnable without re-downloading.
- **Layered models (medallion style).**
  - `staging`: cast types, trim strings, remove duplicate `ride_id`s.
  - `intermediate`: apply quality rules and flag each row with `is_valid` plus an `invalid_reason`.
  - `marts`: business-ready tables for the dashboard.
- **Bad data is flagged, never silently dropped.** `mart_data_quality` reports, per month, how many rows arrived, how many were duplicates, and why rows were rejected. A reconciliation test proves the counts add up.
- **Idempotent loads.** Each month is deleted and re-inserted inside a transaction, so a re-run never duplicates data.
- **Fail loudly.** `dbt build` runs models *and* tests together. Any failure exits non-zero, which fails CI and stops the Docker dashboard from starting on bad data.
- **Observability.** Every step writes to `raw.pipeline_runs` (run id, month, status, row counts), and the dashboard shows it.

## Data quality rules

| Rule | Where | What happens |
|---|---|---|
| Duplicate `ride_id` | `stg_trips` | Keep the latest copy |
| Unparseable timestamp | `int_trips_validated` | Flagged `bad_timestamp` |
| Ended before it started | `int_trips_validated` | Flagged `ended_before_start` |
| Shorter than 1 minute (false starts / re-docks) | `int_trips_validated` | Flagged `under_1_minute` |
| Longer than 24 hours (lost / unreturned bikes) | `int_trips_validated` | Flagged `over_24_hours` |
| Unknown rider type | test (warn) + flag | Warns so a source change gets noticed |
| No start station (dockless e-bike) | kept | Valid ride; counted as `missing_start_station` |
| Unique keys, not-nulls, weather join present | `schema.yml` | Build fails |

## Run it

**Requirements:** Python 3.11+ or Docker.

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2a. Run on real data (downloads ~3 months of Divvy trips + weather)
python -m pipeline.run
# or pick months:  python -m pipeline.run --months 2025-06 2025-07

# 2b. Or run offline on generated sample data
python -m pipeline.run --sample

# 3. Open the dashboard at http://localhost:8501
streamlit run dashboard/app.py

# Tests
pytest -q
```

**With Docker:** `docker compose up --build`, then open http://localhost:8501.
Add `SAMPLE=--sample` in front for offline mode.

**Explore the warehouse directly:**
```bash
python -c "import duckdb; print(duckdb.connect('data/warehouse/divvy.duckdb').sql('select * from marts.mart_data_quality'))"
```

**dbt lineage docs:**
```bash
cd divvy_dbt && WAREHOUSE_PATH=../data/warehouse/divvy.duckdb dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .
```

## Project layout

```
pipeline/            Python extract, load, orchestration, sample data generator
  run.py             entry point: extract -> load -> dbt build, with run logging
divvy_dbt/
  models/staging/      typed, de-duplicated sources
  models/intermediate/ quality rules and flags
  models/marts/        fct_trips, mart_daily_ridership, mart_station_activity, mart_data_quality
  tests/               custom business-rule and reconciliation tests
dashboard/app.py     Streamlit dashboard
tests/               pytest unit tests
.github/workflows/   CI
```

## What I'd do next in production

- **Cloud:** land files in S3 / ADLS, swap DuckDB for Snowflake or Databricks (a new dbt target), and define the infrastructure with Terraform.
- **Orchestration:** move scheduling to Airflow or Dagster for monthly runs, backfills, and alerting.
- **Incremental models:** process only new months in `fct_trips` once data grows.
- **Security & governance:** secrets in a vault, role-based access on marts, data contracts with the source.
- **Monitoring:** source-freshness checks (`dbt source freshness`) and alerts to Slack or email on failure.

## Data sources and licensing

- Trip data: [Divvy System Data](https://divvybikes.com/system-data), published by Lyft Bikes and Scooters under the Divvy Data License Agreement.
- Weather: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api), CC BY 4.0.
