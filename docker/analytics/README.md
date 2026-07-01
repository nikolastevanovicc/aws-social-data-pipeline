# Local Analytics Environment

This Docker Compose setup runs PostgreSQL and Apache Superset locally for the
gold analytics dashboard work. Superset is built from
`docker/analytics/superset/Dockerfile`, which installs `psycopg2-binary` into
the Superset Python environment so it can connect to PostgreSQL without manual
commands inside the container.

## Start

From `docker/analytics`:

```bash
cp .env.example .env
docker compose up -d --build
```

Do not commit `docker/analytics/.env`; it can contain local passwords and
Superset secrets.

Check services:

```bash
docker compose ps
```

If containers are recreated, run `docker compose up -d --build` again. The
custom Superset image will still include PostgreSQL driver support
automatically.

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

## Python Loader Dependencies

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r lambdas/gold_to_postgres_loader/requirements.txt
```

## Seed Local Demo Dashboard Data

Run this from the repository root after `docker compose up -d --build`,
`database/schema.sql` has been applied, and `database/views.sql` has been
applied.

```bash
source .venv/bin/activate
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
docker compose up -d --build
```

Apply the PostgreSQL schema from the repository root:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/schema.sql
```

Apply the analytics views from the repository root:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/views.sql
```

Install local loader dependencies from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r lambdas/gold_to_postgres_loader/requirements.txt
```

Run the smoke tests from the repository root:

```bash
python scripts/smoke_test_gold_to_postgres.py
python scripts/smoke_test_analytics_views.py
```

After they pass, refresh the PyCharm database view or refresh the Superset
datasets to inspect the inserted sample rows.
