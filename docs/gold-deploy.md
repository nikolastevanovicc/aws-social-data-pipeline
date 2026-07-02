# Gold Deploy Guide

This guide covers the gold layer deployment and runtime checks.

## Scope

The CDK app is split into these stacks:

- `DataLakeStack`: S3 Data Lake bucket.
- `NetworkStack`: shared VPC, private subnets with egress, NAT Gateway, S3
  Gateway Endpoint, and shared security groups.
- `AnalyticsStack`: PostgreSQL and Superset EC2 host in the shared VPC.
- `BronzeStack`: Hacker News bronze ingestion Lambda and EventBridge schedule.
- `SilverStack`: silver normalization Lambda resources.
- `GoldStack`: gold aggregation Lambda resources.
- `NotificationStack`: pipeline alerting resources.

`GoldStack` adds two gold aggregation Lambda resources:

- `build-hn-gold`
- `build-x-gold`
- `gold-to-postgres-loader`

Both functions receive the same environment contract:

- `DATA_LAKE_BUCKET`
- `SILVER_PREFIX=silver`
- `GOLD_PREFIX=gold`
- `HN_GOLD_PREFIX=gold/hacker-news`
- `X_GOLD_PREFIX=gold/x`

The gold Lambda role can list the Data Lake bucket, read `silver/*`, and write
`gold/*`. Both aggregation functions read silver Parquet datasets and write
gold Parquet metrics back to S3. The loader reads gold outputs and writes to
PostgreSQL using the private host wired from `AnalyticsStack`.

## Local Checks

```bash
cd infrastructure
source .venv/bin/activate
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'
python -m pytest -q
cdk synth \
  -c analytics_allowed_cidr=203.0.113.10/32 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c postgres_password=dummy
```

If the JSII cache is not writable locally, run tests with:

```bash
JSII_RUNTIME_PACKAGE_CACHE=/private/tmp/jsii-cache python -m pytest -q
```

## Deploy

```bash
cd infrastructure
source .venv/bin/activate
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'
cdk deploy GoldStack --require-approval never \
  -c analytics_allowed_cidr=203.0.113.10/32 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c postgres_password=dummy
```

If the dependent stacks are not deployed yet, deploy the full shared-VPC app:

```bash
cdk deploy \
  DataLakeStack \
  NetworkStack \
  AnalyticsStack \
  BronzeStack \
  SilverStack \
  GoldStack \
  NotificationStack \
  --require-approval never \
  -c analytics_allowed_cidr=203.0.113.10/32 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c postgres_password=dummy
```

For demos, replace `203.0.113.10/32` with your own `/32` public IP. Do not use
`analytics_allowed_cidr=0.0.0.0/0` for loader access; PostgreSQL access uses
`PipelineLambdaSecurityGroup -> AnalyticsSecurityGroup` on tcp/5432.

The deploy outputs include:

- `GoldStack.BuildHnGoldLambdaName`
- `GoldStack.BuildXGoldLambdaName`

## Manual Invoke

Hacker News gold metrics:

```bash
printf '%s' '{"data_date":"2026-05-18","mode":"overwrite_partitions"}' > hn_gold_runtime_event.json

aws lambda invoke \
  --function-name build-hn-gold \
  --payload fileb://hn_gold_runtime_event.json \
  hn_gold_response.json \
  --region eu-central-1 \
  --cli-read-timeout 900

cat hn_gold_response.json
```

X gold metrics:

```bash
aws lambda invoke \
  --function-name build-x-gold \
  --payload fileb://../lambdas/x_gold_aggregation/test_event.json \
  x_gold_response.json \
  --region eu-central-1 \
  --cli-read-timeout 900

cat x_gold_response.json
```

The committed X test event uses `data_date=2026-05-30`, matching the synthetic X
seed dataset used by `normalize-x-silver`.

## S3 Verification

```bash
aws s3 ls s3://<bucket-name>/gold/ --recursive --region eu-central-1
```

Expected gold prefixes:

```text
gold/hacker-news/daily_item_counts/
gold/hacker-news/daily_users_metric/
gold/hacker-news/top_story_posts/
gold/hacker-news/top_job_posts/
gold/hacker-news/top_users_by_karma/
gold/hacker-news/bottom_users_by_karma/
gold/hacker-news/data_quality_summary/
gold/x/daily_users_metric/
gold/x/top_users_by_followers/
gold/x/top_posts_by_engagement/
gold/x/hashtag_trends/
gold/x/data_quality_summary/
```

## Notes

Gold execution requires existing silver outputs in `silver/users/`,
`silver/posts/`, `silver/post_tags/`, and `silver/data_quality_report/`.

Hacker News karma metrics use `karma_score` from the HN silver users dataset.
The HN silver Lambda enriches active authors from the Hacker News user API before
writing `silver/users/`.

Both gold Lambdas read only their platform partition from shared silver datasets:
`build-hn-gold` reads `platform=HackerNews`, and `build-x-gold` reads
`platform=X`.
