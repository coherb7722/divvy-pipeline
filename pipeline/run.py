"""ORCHESTRATE: run the whole pipeline end to end.

    python -m pipeline.run                      # real data, default months
    python -m pipeline.run --months 2025-07     # one month
    python -m pipeline.run --sample             # offline sample data (CI / demos)

Flow per month:  extract trips + weather  ->  load to raw  ->  (all months)  dbt build
`dbt build` runs every model AND every data test; a failed test fails the run.
Each step is recorded in raw.pipeline_runs so you can see what happened and when.
"""

import argparse
import os
import subprocess
import sys
import uuid

from pipeline import config, extract, load, sample_data
from pipeline.utils import get_logger

log = get_logger("pipeline.run")


def run_dbt() -> None:
    env = {**os.environ, "WAREHOUSE_PATH": str(config.WAREHOUSE_PATH)}
    cmd = ["dbt", "build", "--project-dir", str(config.DBT_DIR), "--profiles-dir", str(config.DBT_DIR)]
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise RuntimeError("dbt build failed (a model errored or a data test failed)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Divvy + weather ELT pipeline")
    parser.add_argument("--months", nargs="+", default=config.DEFAULT_MONTHS, help="YYYY-MM ...")
    parser.add_argument("--sample", action="store_true", help="use generated sample data (no internet)")
    args = parser.parse_args(argv)

    run_id = uuid.uuid4().hex[:8]
    log.info("Run %s starting for months %s (sample=%s)", run_id, args.months, args.sample)

    if args.sample:
        sample_data.generate(args.months)

    con = load.connect()
    failed = []
    for month in args.months:
        try:
            trips_path = extract.extract_trips(month)
            weather_path = extract.extract_weather(month)
            n_trips = load.load_trips(con, month, trips_path)
            n_days = load.load_weather(con, month, weather_path)
            load.log_run(con, run_id, month, "extract_load", "success", n_trips, f"{n_days} weather days")
        except Exception as exc:  # keep going: one bad month shouldn't block the others
            log.exception("Month %s failed", month)
            load.log_run(con, run_id, month, "extract_load", "failed", 0, str(exc))
            failed.append(month)
    con.close()  # DuckDB allows one writer; release it for dbt

    dbt_status, detail = "success", ""
    try:
        run_dbt()
    except RuntimeError as exc:
        dbt_status, detail = "failed", str(exc)
        log.error(detail)

    con = load.connect()
    load.log_run(con, run_id, "all", "dbt_build", dbt_status, 0, detail)
    con.close()

    if failed or dbt_status == "failed":
        log.error("Run %s finished with problems. Failed months: %s, dbt: %s", run_id, failed, dbt_status)
        return 1
    log.info("Run %s finished successfully", run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
