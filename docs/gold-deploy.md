# Gold Deploy Guide

This guide covers the Student 1 infrastructure workflow for the gold layer.

## Scope

The CDK app is split into four stacks:

- `DataLakeStack`: S3 Data Lake bucket.
- `BronzeStack`: Hacker News bronze ingestion Lambda and EventBridge schedule.
- `SilverStack`: silver normalization Lambda resources.
- `GoldStack`: gold aggregation Lambda resources.

`GoldStack` adds two gold aggregation Lambda resources:

- `build-hn-gold`
- `build-x-gold`

Both functions receive the same environment contract:

- `DATA_LAKE_BUCKET`
- `SILVER_PREFIX=silver`
- `GOLD_PREFIX=gold`
- `HN_GOLD_PREFIX=gold/hacker-news`
- `X_GOLD_PREFIX=gold/x`

The gold Lambda role can list the Data Lake bucket, read `silver/*`, and write
`gold/*`.

## Local Checks

```bash
cd infrastructure
source .venv/bin/activate
python -m pytest -q
cdk synth
```

If the JSII cache is not writable locally, run tests with:

```bash
JSII_RUNTIME_PACKAGE_CACHE=/private/tmp/jsii-cache python -m pytest -q
```

## Deploy

```bash
cd infrastructure
source .venv/bin/activate
cdk deploy GoldStack --require-approval never
```

If the dependent stacks are not deployed yet, deploy all stacks:

```bash
cdk deploy --all --require-approval never
```

The deploy outputs include:

- `GoldStack.BuildHnGoldLambdaName`
- `GoldStack.BuildXGoldLambdaName`

## Manual Invoke

Hacker News gold placeholder:

```bash
aws lambda invoke \
  --function-name build-hn-gold \
  --payload fileb://../lambdas/hn_gold_aggregation/test_event.json \
  hn_gold_response.json \
  --region eu-central-1

cat hn_gold_response.json
```

X gold placeholder:

```bash
aws lambda invoke \
  --function-name build-x-gold \
  --payload fileb://../lambdas/x_gold_aggregation/test_event.json \
  x_gold_response.json \
  --region eu-central-1

cat x_gold_response.json
```

## S3 Verification

After Student 2 and Student 3 implement aggregation and Parquet writes:

```bash
aws s3 ls s3://<bucket-name>/gold/ --recursive --region eu-central-1
```

Expected gold prefixes:

```text
gold/hacker-news/daily_metrics/
gold/hacker-news/top_posts/
gold/hacker-news/top_users/
gold/hacker-news/post_type_distribution/
gold/hacker-news/data_quality_summary/
gold/x/daily_metrics/
gold/x/top_posts/
gold/x/top_users/
gold/x/hashtag_trends/
gold/x/data_quality_summary/
```

## Notes

The current Student 1 delivery creates infrastructure and placeholder Lambda
entrypoints. Actual gold business aggregations are implemented by Student 2 and
Student 3 after the required silver outputs are available.
