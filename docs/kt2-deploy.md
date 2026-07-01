# KT2 Silver Deploy Guide

This guide covers the silver layer infrastructure and runtime workflow.

## Scope

The CDK app is split into three stacks:
- `DataLakeStack`: S3 Data Lake bucket
- `BronzeStack`: Hacker News bronze ingestion Lambda and EventBridge schedule
- `SilverStack`: silver normalization Lambda resources

`SilverStack` adds two silver normalization Lambda resources:
- `normalize-hn-silver`
- `normalize-x-silver`

Both functions receive the same environment contract:
- `DATA_LAKE_BUCKET`
- `BRONZE_HN_PREFIX=bronze/hacker-news`
- `BRONZE_X_PREFIX=bronze/x`
- `SILVER_PREFIX=silver`
- `DEFAULT_X_DATASET_NAME=x-synthetic-seed`

The silver Lambda role can list the Data Lake bucket, read `bronze/*`, and write `silver/*`.

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
cdk deploy --require-approval never
```

The deploy outputs include:
- `DataLakeStack.DataLakeBucketName`
- `BronzeStack.HackerNewsLambdaName`
- `SilverStack.NormalizeHnSilverLambdaName`
- `SilverStack.NormalizeXSilverLambdaName`

If an older monolithic `InfrastructureStack` is still deployed in AWS, coordinate cleanup before deploying this split-stack version. The repository now models the infrastructure as separate Data Lake, Bronze, and Silver stacks.

## Manual Invoke

Hacker News silver:

```bash
printf '%s' '{"data_date":"2026-05-18","ingest_date":"2026-07-01","mode":"overwrite_partitions"}' > hn_silver_runtime_event.json

aws lambda invoke \
  --function-name normalize-hn-silver \
  --payload fileb://hn_silver_runtime_event.json \
  hn_silver_response.json \
  --region eu-central-1 \
  --cli-read-timeout 900

cat hn_silver_response.json
```

Use an `ingest_date` that exists under `bronze/hacker-news/`. The example above
matches a manual HN bronze ingestion run for `data_date=2026-05-18`.

X silver:

```bash
aws lambda invoke \
  --function-name normalize-x-silver \
  --payload fileb://../lambdas/x_silver_normalization/test_event.json \
  x_silver_response.json \
  --region eu-central-1 \
  --cli-read-timeout 900

cat x_silver_response.json
```

The X test event uses the synthetic seed dataset at
`bronze/x/ingest_date=2026-05-30/dataset_name=x-synthetic-seed/tweets.json`.
Upload `datasets/x/tweets.json` and `datasets/x/metadata.json` to that prefix
before invoking `normalize-x-silver`.

## S3 Verification

```bash
aws s3 ls s3://<bucket-name>/silver/ --recursive --region eu-central-1
```

Expected silver prefixes:

```text
silver/users/platform=<platform>/year=YYYY/month=MM/day=DD/
silver/posts/
silver/post_tags/
silver/post_relations/
silver/data_quality_report/
```

HN silver enriches active authors from the Hacker News user API and writes
`karma_score` and `user_created_at_utc` in the `silver/users/` dataset. These
fields are required by the HN gold top/bottom karma metrics.

## Notes

The silver Lambdas perform real normalization and Parquet writes. Runtime
verification should show non-zero row counts for `users`, `posts`, `post_tags`,
`post_relations`, and `data_quality_report` after the matching bronze inputs
exist in S3.
