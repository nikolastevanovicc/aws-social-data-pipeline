# KT2 Silver Deploy Guide

This guide covers the Student 1 infrastructure workflow for the KT2 silver layer.

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

Hacker News silver placeholder:

```bash
aws lambda invoke \
  --function-name normalize-hn-silver \
  --payload fileb://../lambdas/hn_silver_normalization/test_event.json \
  hn_silver_response.json \
  --region eu-central-1

cat hn_silver_response.json
```

X silver placeholder:

```bash
aws lambda invoke \
  --function-name normalize-x-silver \
  --payload fileb://../lambdas/x_silver_normalization/test_event.json \
  x_silver_response.json \
  --region eu-central-1

cat x_silver_response.json
```

## S3 Verification

After Student 2 and Student 3 implement normalization and Parquet writes:

```bash
aws s3 ls s3://<bucket-name>/silver/ --recursive --region eu-central-1
```

Expected silver prefixes:

```text
silver/users/
silver/posts/
silver/post_tags/
silver/post_relations/
silver/data_quality_report/
```

## Notes

The current Student 1 delivery creates infrastructure and placeholder Lambda entrypoints. Actual HN/X normalization, Parquet writing, and Data Quality output are implemented by Student 2 and Student 3.
