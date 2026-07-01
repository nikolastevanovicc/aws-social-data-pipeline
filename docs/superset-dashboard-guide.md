# Superset Dashboard Guide

## Purpose

This guide defines the PostgreSQL and Apache Superset visualization layer for
gold metrics produced by the social data pipeline. The Superset dashboard should
use analytics views from `database/views.sql` instead of querying the raw gold
tables directly.

## Prerequisites

- PostgreSQL and Superset are running locally with Docker or on the EC2 analytics
  host.
- `database/schema.sql` has been applied.
- `database/views.sql` has been applied.
- The gold-to-postgres loader has inserted rows into the PostgreSQL gold tables.

Apply the local schema and views from the repository root:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/schema.sql

docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/views.sql
```

## Superset Database Connection

### Local Docker

Use this SQLAlchemy URI when Superset is running from
`docker/analytics/docker-compose.yml`:

```text
postgresql+psycopg2://superset:superset@postgres:5432/social_analytics
```

The local Superset image is built from `docker/analytics/superset/Dockerfile`
and includes PostgreSQL driver support through `psycopg2-binary`, so fresh
Docker Compose setups can use this URI without manually installing packages in
the running container.

### EC2

Use the `PostgresHost` CloudFormation output as the PostgreSQL host. The
database name, username, and password should match the deployment context values
used for the analytics stack.

## Recommended Superset Datasets

Create one Superset dataset for each analytics view:

- `vw_hn_daily_activity`
- `vw_x_daily_activity`
- `vw_hn_top_posts`
- `vw_hn_top_users`
- `vw_x_top_posts`
- `vw_x_top_users`
- `vw_x_hashtag_trends`
- `vw_data_quality_score`

## Local Demo Data for Screenshots

For local screenshots, seed demo gold rows after PostgreSQL is running and the
schema and views have been applied:

```bash
python scripts/seed_local_demo_gold_data.py
```

The script inserts local/demo-only sample data for `2026-05-18` through
`2026-05-20`, reapplies the analytics views, and validates that each dashboard
view returns rows. Refresh the Superset datasets after running it, then use the
date range `2026-05-18` to `2026-05-20` in charts. The charts should no longer
be empty. This data is only for local dashboard screenshots and is not AWS
production data.

## Recommended Charts

### HN Daily Metrics

- Big Number: `total_count`
- Time-series Bar Chart: `story_count`, `ask_count`, `comment_count`,
  `job_count`, and `poll_count` by `date`
- Table: `vw_hn_daily_activity`

### X Daily Metrics

- Big Number: `total_users`
- Big Number: `active_users`
- Time-series Line Chart: `total_users` and `active_users` by `date`

### HN Top Content

- Table: `vw_hn_top_posts` filtered by latest `date`, ordered by `rank`
- Table: `vw_hn_top_users` filtered by latest `date`, ordered by `user_bucket`
  and `rank`

### X Top Content

- Table: `vw_x_top_posts` ordered by `engagement_count` descending
- Table: `vw_x_top_users` ordered by `followers_count` descending
- Bar Chart: `vw_x_hashtag_trends`, `tag` versus `post_count`

### Data Quality

- Big Number or Gauge: average `data_quality_score`
- Table: `vw_data_quality_score`
- Bar Chart: `data_quality_score` by `table_name`

## Recommended Dashboard Layout

Dashboard title:

```text
Social Data Pipeline Gold Analytics
```

Sections:

1. Daily Activity Overview
2. Hacker News Insights
3. X Insights
4. Data Quality

## Screenshots Checklist for Final Report

- PostgreSQL tables and views visible
- Superset database connection
- Superset datasets
- Dashboard overview
- Data quality chart
- One HN chart
- One X chart

## Troubleshooting

### No Tables Visible

Confirm `database/schema.sql` was applied to the same database Superset is using.
For local Docker, the database should be `social_analytics` on host `postgres`
from Superset and `localhost` from the host machine.

### No Views Visible

Apply `database/views.sql` after `database/schema.sql`:

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/views.sql
```

Then refresh the database metadata in Superset and create datasets from the view
names.

### Empty Charts

Confirm the gold-to-postgres loader has inserted rows into the source tables.
The views are read-only projections and will be empty when the underlying tables
are empty.

### Database Connection Refused

For local Docker, confirm the analytics containers are running:

```bash
cd docker/analytics
docker compose ps
```

In Superset, use host `postgres`, not `localhost`. From the host machine, use
`localhost` for direct PostgreSQL scripts.

### Superset Login Issue

For local Docker, use the admin credentials from `docker/analytics/.env`. If the
file was created from `.env.example`, the default username is `admin` and the
default password is `admin`.
