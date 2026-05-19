# AWS Social Data Pipeline

Bronze layer baseline za predmetni projekat iz Racunarstva u oblaku.

## Scope ove iteracije

Ova iteracija pokriva Student 1 minimum:
- S3 Data Lake bucket
- Lambda resource za Hacker News ingestion
- IAM least-privilege prava za Lambdu
- EventBridge dnevni schedule u `02:00 UTC`
- Osnovni scaffold za Student 2 i Student 3 rad

## Struktura repozitorijuma

```text
.
├── infrastructure/
├── lambdas/
│   └── hn_ingestion/
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
cdk deploy
```

Deploy kreira:
- `S3` Data Lake bucket
- `Lambda` funkciju `hn-bronze-ingestion`
- `EventBridge` pravilo sa schedule izrazom `cron(0 2 * * ? *)`

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

## Dokumentacija

- Networking odluka: `docs/networking-decision.md`
- Arhitektura i demo skeleton: `docs/architecture.md`, `docs/kt1-test-plan.md`, `docs/demo-script.md`
