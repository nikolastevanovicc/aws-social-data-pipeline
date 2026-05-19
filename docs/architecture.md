# KT1 Architecture (Bronze Layer)

## Flow

1. EventBridge rule pokrece `hn-bronze-ingestion` svakog dana u `02:00 UTC`.
2. Lambda skuplja raw Hacker News podatke i upisuje ih u `s3://<bucket>/bronze/hacker-news/...`.
3. X dataset se uploaduje manuelno ili skriptom u `s3://<bucket>/bronze/x/...`.
4. CloudWatch cuva logove i greske za ingestion.

## Scope boundary

KT1 ne ukljucuje silver/gold transformacije, PostgreSQL, Superset, ni notifikacije.
