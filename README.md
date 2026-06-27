# AWS Social Data Pipeline

AWS/CDK projekat za social data pipeline kroz bronze, silver i gold slojeve.

## Trenutni scope

Repozitorijum trenutno pokriva:

- `DataLakeStack`: S3 Data Lake bucket.
- `BronzeStack`: Hacker News bronze ingestion Lambda i EventBridge schedule.
- `SilverStack`: silver normalization Lambda resource-i.
- `GoldStack`: gold aggregation Lambda resource-i.
- Least-privilege IAM role/policy po sloju.
- Osnovni scaffold za Student 2 i Student 3 transformacije.

## Struktura repozitorijuma

```text
.
├── infrastructure/
├── lambdas/
│   ├── hn_ingestion/
│   ├── hn_silver_normalization/
│   ├── x_silver_normalization/
│   ├── hn_gold_aggregation/
│   └── x_gold_aggregation/
├── datasets/
│   └── x/
├── scripts/
└── docs/
```

## Setup

1. Udji u CDK folder:
```bash
cd infrastructure
```
2. Kreiraj i aktiviraj virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```
3. Instaliraj dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```
4. Bootstrap (ako je prvi put u account/region kombinaciji):
```bash
cdk bootstrap
```

## Deploy

```bash
cd infrastructure
source .venv/bin/activate
cdk synth
cdk deploy --all
```

Deploy kreira Data Lake, Bronze, Silver i Gold stackove.

## Test invoke Lambda funkcije

Primer sa datumom:
```bash
aws lambda invoke \
  --function-name hn-bronze-ingestion \
  --payload '{"date":"2026-05-18"}' \
  response.json
cat response.json
```

Primer bez datuma:
```bash
aws lambda invoke \
  --function-name hn-bronze-ingestion \
  --payload '{}' \
  response.json
cat response.json
```

## Bronze S3 konvencije

Hacker News:
```text
s3://<bucket>/bronze/hacker-news/ingest_date=YYYY-MM-DD/data_date=YYYY-MM-DD/{story|ask|comment|job|poll}/part-000.json
```

X dataset:
```text
s3://<bucket>/bronze/x/ingest_date=YYYY-MM-DD/dataset_name=<name>/tweets.json
s3://<bucket>/bronze/x/ingest_date=YYYY-MM-DD/dataset_name=<name>/metadata.json
```

## Granice bronze layer-a

U bronze sloju podaci se cuvaju u raw obliku:
- nema ciscenja HTML-a
- nema normalizacije vremena
- nema deduplikacije
- nema izmene izvorne seme

## Silver i Gold konvencije

Silver sloj cita `bronze/*` i pise normalizovane podatke u:

```text
s3://<bucket>/silver/...
```

Gold sloj cita `silver/*` i pise agregirane analiticke podatke u:

```text
s3://<bucket>/gold/hacker-news/...
s3://<bucket>/gold/x/...
```

## Dokumentacija

- Silver deploy guide: `docs/kt2-deploy.md`
- Gold layer podela rada: `docs/gold-layer-student-division.md`
- Gold deploy guide: `docs/gold-deploy.md`
