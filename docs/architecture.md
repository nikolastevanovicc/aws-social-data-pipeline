# KT1 Architecture (Bronze Layer)

## Flow

1. EventBridge rule pokrece `hn-bronze-ingestion` svakog dana u `02:00 UTC`.
2. Lambda skuplja raw Hacker News podatke i upisuje ih u `s3://<bucket>/bronze/hacker-news/...`.
3. X/Twitter sintetski dataset se priprema lokalno i uploaduje skriptom `scripts/upload_x_dataset.py`.
4. X/Twitter podaci se upisuju u S3 bronze sloj u raw JSON obliku.
5. Hacker News ingestion i X dataset upload su dvije odvojene bronze ingestion putanje.
6. CloudWatch cuva logove i greske za ingestion.

## X/Twitter bronze ingestion path

X/Twitter dataset ne koristi Lambda ingestion. Dataset je lokalno pripremljen kao raw JSON i uploaduje se u S3 bronze sloj pomocu `scripts/upload_x_dataset.py`. Ova putanja je nezavisna od Hacker News Lambda ingestion putanje.

```text
Local X dataset
      |
      v
upload_x_dataset.py
      |
      v
S3 bronze/x/ingest_date=YYYY-MM-DD/dataset_name=x-synthetic-seed/
```

Hacker News ingestion i X/Twitter upload su odvojeni izvori za bronze sloj:
- Hacker News: automatski EventBridge + Lambda tok.
- X/Twitter: lokalni sintetski dataset + upload skripta.

## Scope boundary

KT1 ne ukljucuje silver/gold transformacije, PostgreSQL, Superset, ni notifikacije.
