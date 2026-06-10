# Infrastructure (CDK)

CDK Python app koja definise Student 1 infrastrukturu za bronze layer:
- S3 Data Lake bucket
- Hacker News Lambda resource
- Least-privilege IAM role/policy
- EventBridge daily trigger (`02:00 UTC`)

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
