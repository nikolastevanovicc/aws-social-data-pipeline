# KT1 Demo Script

## Opsti demo

1. Pokazi repozitorijum i folder strukturu.
2. Pokreni `cdk synth` i `cdk deploy`.
3. U AWS konzoli pokazi kreirani S3 bucket i Lambda funkciju.
4. Pokreni Lambda test event sa datumom.
5. Otvori CloudWatch logove i prikazi summary rezultat.
6. Pokazi `bronze/hacker-news` i `bronze/x` prefikse u S3.
7. Naglasi da je bronze sloj raw i bez transformacija.

## Student 3 demo - X/Twitter bronze dataset

1. Pokazi `datasets/x/tweets.json` i naglasi da sadrzi `50` sintetskih tweet zapisa.
2. Pokazi `datasets/x/metadata.json` i vrijednost `record_count`.
3. Objasni da se sintetski X/Twitter dataset koristi zato sto je X API free tier ogranicen, a specifikacija dozvoljava postojece, manuelno kreirane ili generisane datasete.
4. Pokreni dry-run komandu:
```bash
python scripts/upload_x_dataset.py --bucket test-bucket-name --dry-run
```
5. Ako je stvarni bucket dostupan, pokreni upload:
```bash
python scripts/upload_x_dataset.py --bucket <bucket-name> --dataset-name x-synthetic-seed
```
6. Pokazi ocekivane S3 putanje:
```text
s3://<bucket-name>/bronze/x/ingest_date=YYYY-MM-DD/dataset_name=x-synthetic-seed/tweets.json
s3://<bucket-name>/bronze/x/ingest_date=YYYY-MM-DD/dataset_name=x-synthetic-seed/metadata.json
```
7. Objasni da su ovo raw bronze podaci i da se normalizacija radi kasnije u silver sloju.
