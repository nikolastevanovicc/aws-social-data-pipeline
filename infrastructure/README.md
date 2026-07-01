# Infrastructure (CDK)

CDK Python app koja definise projektnu infrastrukturu kroz odvojene stackove:

- `DataLakeStack`: S3 Data Lake bucket.
- `BronzeStack`: Hacker News bronze ingestion Lambda i EventBridge daily trigger.
- `SilverStack`: silver normalization Lambda resource-i.
- `GoldStack`: gold aggregation Lambda resource-i.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## CDK commands

```bash
cdk synth
cdk deploy
cdk diff
cdk destroy
```
