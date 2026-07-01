# Student 2 - PostgreSQL and Superset Visualization Summary

## Responsibility

Student 2 owns the analytics serving and visualization layer for the social data
pipeline. The intended end-to-end project flow is:

```text
bronze -> silver -> gold -> PostgreSQL -> Superset
```

For Student 2 specifically, the implemented flow is:

```text
gold S3 Parquet -> gold-to-postgres-loader Lambda -> PostgreSQL -> Superset dashboards
```

## Implemented Components

- PostgreSQL schema for gold analytics tables.
- Gold-to-PostgreSQL loader Lambda.
- Local Docker Compose analytics environment.
- Apache Superset visualization setup.
- AWS CDK analytics EC2 stack for demo hosting.
- Analytics SQL views for dashboard-friendly datasets.
- Local demo data seeding and smoke-test scripts.
- Cost-safety documentation and EC2 auto-stop guardrails.

## PostgreSQL Schema

`database/schema.sql` defines PostgreSQL tables that mirror the current gold
Parquet outputs for Hacker News and X metrics. It includes daily activity,
top content, top users, hashtag trends, and data quality summary tables, plus
indexes for common dashboard filters.

## Gold-to-PostgreSQL Loader

`lambdas/gold_to_postgres_loader/handler.py` reads gold Parquet data from S3 and
writes normalized rows into the PostgreSQL analytics tables. The loader supports
the Student 2 serving path from gold S3 Parquet into PostgreSQL.

## Local Analytics Environment

`docker/analytics/docker-compose.yml` starts local PostgreSQL and Superset.
Superset is built from `docker/analytics/superset/Dockerfile`, which installs
`psycopg2-binary` into the Superset Python environment so a fresh Docker Compose
setup can connect to PostgreSQL without manual container changes.

Start locally from `docker/analytics`:

```bash
docker compose up -d --build
```

## AWS CDK Infrastructure

`AnalyticsStack` provisions a demo EC2 analytics host that runs PostgreSQL and
Superset with Docker Compose. User data writes the Compose file, `.env`,
`superset-init.sh`, `schema.sql`, and the custom Superset Dockerfile, then runs
Docker Compose with `--build`.

## Cost Safety Guardrails

The analytics EC2 stack is intended for demos, not production. It defaults to a
small instance, uses no NAT gateway, supports restricted inbound CIDR context,
and can create a UTC cron job that stops the instance daily. Documentation
emphasizes `cdk synth` for review and warns that `cdk deploy` creates billable
resources.

## Analytics Views

`database/views.sql` creates dashboard-friendly Superset views:

- `vw_hn_daily_activity`
- `vw_x_daily_activity`
- `vw_hn_top_posts`
- `vw_hn_top_users`
- `vw_x_top_posts`
- `vw_x_top_users`
- `vw_x_hashtag_trends`
- `vw_data_quality_score`

## Superset Dashboards

`docs/superset-dashboard-guide.md` documents the Superset database connection,
recommended datasets, chart ideas, layout, screenshot checklist, and common
troubleshooting steps. The local SQLAlchemy URI is:

```text
postgresql+psycopg2://superset:superset@postgres:5432/social_analytics
```

## Local Demo Data

`scripts/seed_local_demo_gold_data.py` inserts local demo rows for dashboard
screenshots and validates that each analytics view returns rows. This data is
for local demonstration only and is not AWS production data.

## Validation Commands

```bash
python -m py_compile lambdas/gold_to_postgres_loader/handler.py
python -m py_compile scripts/smoke_test_gold_to_postgres.py
python -m py_compile scripts/smoke_test_analytics_views.py
python -m py_compile scripts/seed_local_demo_gold_data.py
python -m py_compile infrastructure/infrastructure/analytics_stack.py

pytest tests/unit/test_gold_to_postgres_loader.py
pytest infrastructure/tests/unit/test_infrastructure_stack.py

docker compose -f docker/analytics/docker-compose.yml config
docker compose -f docker/analytics/docker-compose.yml build superset

cd infrastructure
cdk synth AnalyticsStack \
  -c analytics_allowed_cidr=0.0.0.0/0 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c analytics_instance_type=t3.micro \
  -c analytics_auto_stop_enabled=true \
  -c analytics_auto_stop_utc_hour=22

cdk synth \
  -c analytics_allowed_cidr=0.0.0.0/0 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c analytics_instance_type=t3.micro \
  -c analytics_auto_stop_enabled=true \
  -c analytics_auto_stop_utc_hour=22 \
  -c postgres_host=localhost \
  -c postgres_password=dummy
```

## Demo Checklist

- Start local analytics services with `docker compose up -d --build`.
- Apply `database/schema.sql`.
- Apply `database/views.sql`.
- Seed local demo data.
- Connect Superset to PostgreSQL with the documented SQLAlchemy URI.
- Create datasets from analytics views.
- Build charts for daily activity, top content, top users, hashtags, and data
  quality.
- Capture screenshots for the final report.
- For AWS demos, run `cdk synth` first and deploy only when the team is ready.

## Known Limitation

Actual AWS deploy and Lambda-to-EC2 networking should only be tested when the
team is ready to avoid unexpected cost. The current AnalyticsStack hosts
PostgreSQL and Superset, but production-grade Lambda networking, private
routing, and hardened access controls are outside this Student 2 demo scope.
