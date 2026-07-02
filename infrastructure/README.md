# Infrastructure (CDK)

CDK Python app koja definise projektnu infrastrukturu kroz odvojene stackove:

- `DataLakeStack`: S3 Data Lake bucket.
- `NetworkStack`: shared VPC, public subnets, private subnets with egress, NAT
  Gateway, S3 Gateway Endpoint, and shared security groups.
- `AnalyticsStack`: EC2 analytics host for PostgreSQL and Superset in the
  shared VPC.
- `BronzeStack`: Hacker News bronze ingestion Lambda i EventBridge daily trigger.
- `SilverStack`: silver normalization Lambda resource-i.
- `GoldStack`: gold aggregation Lambda resource-i and gold-to-PostgreSQL
  loader.
- `NotificationStack`: SNS, CloudWatch alarms, and Discord notification Lambda.

Pipeline Lambda functions run in the `NetworkStack` private subnets with egress
when the app is deployed through `app.py`. PostgreSQL access is limited to
`PipelineLambdaSecurityGroup -> AnalyticsSecurityGroup` on tcp/5432. Superset
tcp/8088 is limited to `analytics_allowed_cidr`.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## CDK commands

```bash
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'

cdk synth \
  -c analytics_allowed_cidr=203.0.113.10/32 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c postgres_password=dummy

cdk deploy DataLakeStack NetworkStack AnalyticsStack BronzeStack SilverStack GoldStack NotificationStack \
  -c analytics_allowed_cidr=203.0.113.10/32 \
  -c analytics_postgres_password=dummy \
  -c analytics_superset_secret_key=dummy \
  -c postgres_password=dummy
cdk diff
cdk destroy
```

For demos, replace `203.0.113.10/32` with your current public IP:

```bash
-c analytics_allowed_cidr="$(curl -s https://checkip.amazonaws.com)/32"
```

Use `DISCORD_WEBHOOK_URL` from your shell when deploying or synthesizing
`NotificationStack`; do not commit real webhook URLs or secrets.
