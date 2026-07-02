# Gold to PostgreSQL Loader

## Purpose

The gold-to-postgres loader copies curated gold Parquet datasets from the S3
data lake into PostgreSQL tables for Apache Superset dashboards.

Expected flow:

```text
gold S3 Parquet -> gold-to-postgres-loader Lambda -> PostgreSQL -> Superset
```

This deploys only the loader Lambda. PostgreSQL and Superset EC2 provisioning is
handled by `AnalyticsStack`, and shared VPC networking is handled by
`NetworkStack`.

## Lambda Configuration

The loader is deployed from:

```text
lambdas/gold_to_postgres_loader/handler.py
```

Runtime dependencies:

- `pg8000` is packaged into the Lambda asset from
  `lambdas/gold_to_postgres_loader/requirements.txt`.
- `awswrangler` is provided by the AWS SDK for pandas Lambda layer, matching the
  existing silver and gold Lambda pattern.

Required environment variables:

- `DATA_LAKE_BUCKET`
- `GOLD_PREFIX`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DATABASE`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

In the full CDK app, `app.py` passes
`analytics_stack.postgres_private_host` into `GoldStack`, so `POSTGRES_HOST`
resolves to the private PostgreSQL host from `AnalyticsStack`. That constructor
value takes precedence over context or local environment fallback.

Do not commit real passwords or secrets. Pass deployment-specific non-host
values through CDK context or local environment variables at synth/deploy time.

## CDK Context Example

```bash
cd infrastructure
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'

cdk synth DataLakeStack NetworkStack AnalyticsStack GoldStack \
  -c analytics_allowed_cidr=x.x.x.x/32 \
  -c analytics_postgres_password='replace-with-secure-password' \
  -c analytics_superset_secret_key='replace-with-demo-secret-key' \
  -c postgres_port=5432 \
  -c postgres_database=social_analytics \
  -c postgres_user=superset \
  -c postgres_password='replace-with-secure-password'
```

The deployed app should not pass a public PostgreSQL host for
`gold-to-postgres-loader`. The host is wired from `AnalyticsStack` private IP.
The same non-host values can also come from local environment variables such as
`POSTGRES_PASSWORD`.

## Manual Invocation

Use the example event as a starting point:

```text
lambdas/gold_to_postgres_loader/test_event.example.json
```

Example payload:

```json
{
  "bucket": "replace-with-data-lake-bucket-name",
  "gold_prefix": "gold",
  "data_date": "2026-05-20",
  "platforms": ["hacker-news", "x"],
  "datasets": null,
  "mode": "replace_date"
}
```

Event values override Lambda environment variables for that invocation. In the
shared-VPC AWS deployment, omit `postgres_host` so the loader uses the private
host configured by CDK. If you include database override values for local
testing, never store real passwords in the repository.

```bash
aws lambda invoke \
  --function-name gold-to-postgres-loader \
  --payload fileb://../lambdas/gold_to_postgres_loader/test_event.example.json \
  gold_to_postgres_response.json \
  --region eu-central-1 \
  --cli-read-timeout 900
```

The loader is not automatically triggered yet. Invoke it manually after the gold
Parquet outputs for the selected `data_date` exist in S3.

Do not open PostgreSQL tcp/5432 publicly for this invocation. Lambda-to-PostgreSQL
access should use the `NetworkStack` rule from `PipelineLambdaSecurityGroup` to
`AnalyticsSecurityGroup` on tcp/5432.
