# Local Analytics Environment

This Docker Compose setup runs PostgreSQL and Apache Superset locally for the
gold analytics dashboard work.

## Start

From `docker/analytics`:

```bash
cp .env.example .env
docker compose up -d
```

Check services:

```bash
docker compose ps
```

## Apply PostgreSQL Schema

From the repository root:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/schema.sql
```

## Apply Analytics Views

Run this after `database/schema.sql` has been applied.

From the repository root:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/views.sql
```

## Seed Local Demo Dashboard Data

Run this from the repository root after `docker compose up -d`,
`database/schema.sql` has been applied, and `database/views.sql` has been
applied.

```bash
source .venv/bin/activate
python -m pip install -r lambdas/gold_to_postgres_loader/requirements.txt
python scripts/seed_local_demo_gold_data.py
```

## Open Superset

```text
http://localhost:8088
```

Login credentials from `.env.example`:

- username: `admin`
- password: `admin`

## PostgreSQL Connection Details for Superset

- host: `postgres`
- port: `5432`
- database: `social_analytics`
- username: `superset`
- password: `superset`

SQLAlchemy URI:

```text
postgresql+psycopg2://superset:superset@postgres:5432/social_analytics
```

## Run Local Loader Smoke Test

Start the local analytics services from `docker/analytics`:

```bash
docker compose up -d
```

Apply the PostgreSQL schema from the repository root:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/schema.sql
```

Install the local loader dependency if needed:

```bash
pip install -r lambdas/gold_to_postgres_loader/requirements.txt
```

Run the smoke test from the repository root:

```bash
python scripts/smoke_test_gold_to_postgres.py
```

After it passes, refresh the PyCharm database view or refresh the Superset
datasets to inspect the inserted sample rows.
