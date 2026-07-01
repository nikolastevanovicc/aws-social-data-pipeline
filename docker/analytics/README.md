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
