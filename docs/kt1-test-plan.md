# KT1 Test Plan

## Infrastructure tests

- `cdk synth` prolazi bez greske.
- `cdk deploy` kreira S3 bucket, Lambda, IAM policy i EventBridge rule.
- Lambda env var `DATA_LAKE_BUCKET` je postavljena.
- EventBridge schedule je `cron(0 2 * * ? *)`.

## Functional smoke tests

- Invoke sa `{"date":"YYYY-MM-DD"}` vraca summary payload.
- Invoke sa `{}` koristi prethodni dan u UTC.
- CloudWatch log stream postoji za Lambda funkciju.

## X/Twitter dataset tests

- `datasets/x/tweets.json` je validan JSON.
- `datasets/x/metadata.json` je validan JSON.
- `datasets/x/tweets.json` sadrzi tacno `50` zapisa.
- `metadata.json` polje `record_count` se poklapa sa brojem tweet zapisa.
- Upload skripta se kompajlira:
```bash
python -m py_compile scripts/upload_x_dataset.py
```
- Dry-run upload skripte prolazi bez greske:
```bash
python scripts/upload_x_dataset.py --bucket test-bucket-name --dry-run
```
- Dry-run ispisuje ocekivani S3 prefix:
```text
bronze/x/ingest_date=YYYY-MM-DD/dataset_name=x-synthetic-seed/
```
- Stvarni upload se moze provjeriti komandom:
```bash
aws s3 ls s3://<bucket-name>/bronze/x/ --recursive
```

## Security checks

- Nema `AdministratorAccess`.
- Nema wildcard admin akcija (`*`, `s3:*`, `iam:*`) u custom policy dokumentu.
