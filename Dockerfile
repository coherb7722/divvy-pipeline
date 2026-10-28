FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    WAREHOUSE_PATH=/app/data/warehouse/divvy.duckdb

# Install dependencies first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline/ pipeline/
COPY divvy_dbt/ divvy_dbt/
COPY dashboard/ dashboard/
COPY tests/ tests/

# Install dbt packages/parse once at build time to catch SQL errors early
RUN dbt parse --project-dir divvy_dbt --profiles-dir divvy_dbt

CMD ["python", "-m", "pipeline.run"]
