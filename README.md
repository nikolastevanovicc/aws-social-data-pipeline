# AWS Social Data Pipeline

AWS Social Data Pipeline is a CDK-based data engineering project that moves
social data through a Medallion architecture and into a local or EC2-hosted
analytics layer.

Current implemented scope:

- Bronze ingestion for Hacker News and upload support for an X dataset.
- Silver normalization to Parquet tables.
- Gold metrics and KPI aggregation.
- Gold-to-PostgreSQL loader Lambda.
- PostgreSQL and Apache Superset analytics workflow.
- Failed-job notifications through CloudWatch alarms, SNS, Lambda, and Discord.
- Shared VPC CDK infrastructure with private pipeline Lambdas and restricted
  analytics access.

## Architecture

### Network and Security Boundary

`NetworkStack` creates the shared network used by the deployed AWS pipeline:

- one VPC,
- public subnets,
- private subnets with egress,
- one NAT Gateway,
- an S3 Gateway Endpoint,
- `PipelineLambdaSecurityGroup`,
- `AnalyticsSecurityGroup`.

Pipeline Lambda functions run in the VPC private subnets with egress. They use
`PipelineLambdaSecurityGroup` and reach AWS services through the VPC routing
path; S3 traffic can use the S3 Gateway Endpoint and external APIs/webhooks use
NAT egress.

`AnalyticsStack` runs the demo analytics EC2 host in the same VPC. PostgreSQL
is not opened publicly for Lambda access. The intended database path is:

```text
Pipeline Lambdas in private subnets
  -> PipelineLambdaSecurityGroup
  -> AnalyticsSecurityGroup tcp/5432
  -> PostgreSQL on the analytics EC2 host
```

Superset remains browser-accessible on tcp/8088, but only from
`analytics_allowed_cidr`. For a demo or presentation, use your current public
IP as a `/32`:

```bash
-c analytics_allowed_cidr="$(curl -s https://checkip.amazonaws.com)/32"
```

Do not use `analytics_allowed_cidr=0.0.0.0/0` as a Lambda-to-PostgreSQL
workaround. That old workaround is obsolete because Lambda-to-PostgreSQL access
now uses security-group-to-security-group connectivity inside the shared VPC.

### Bronze Layer

Bronze stores raw source data in S3.

Hacker News ingestion is implemented by `lambdas/hn_ingestion/handler.py` and
is deployed by `BronzeStack`. With no explicit date, it ingests Hacker News
items created on the previous UTC day.

Hacker News bronze layout:

```text
s3://<bucket>/bronze/hacker-news/ingest_date=YYYY-MM-DD/data_date=YYYY-MM-DD/{story|ask|comment|job|poll}/part-000.json
```

X dataset upload support is provided by `scripts/upload_x_dataset.py`.

X bronze layout:

```text
s3://<bucket>/bronze/x/ingest_date=YYYY-MM-DD/dataset_name=<name>/tweets.json
s3://<bucket>/bronze/x/ingest_date=YYYY-MM-DD/dataset_name=<name>/metadata.json
```

Bronze data is intentionally raw: no schema rewriting, text cleaning,
deduplication, or normalized timestamp conversion happens in this layer.

### Silver Layer

Silver normalizes bronze data into curated Parquet tables under:

```text
s3://<bucket>/silver/...
```

Implemented handlers:

- `lambdas/hn_silver_normalization/handler.py`
- `lambdas/x_silver_normalization/handler.py`

For Hacker News, the silver default dates align with bronze ingestion:

- `data_date` defaults to yesterday in UTC.
- `ingest_date` defaults to today in UTC.
- Event-provided `data_date` and `ingest_date` override those defaults.

### Gold Layer

Gold aggregates silver data into metrics and KPIs under:

```text
s3://<bucket>/gold/hacker-news/...
s3://<bucket>/gold/x/...
```

Implemented handlers:

- `lambdas/hn_gold_aggregation/handler.py`
- `lambdas/x_gold_aggregation/handler.py`

Gold outputs include daily counts, user metrics, top posts, top users, hashtag
trends, and data quality summaries used by downstream analytics.

### Gold-to-PostgreSQL Loader

`lambdas/gold_to_postgres_loader/handler.py` copies gold Parquet outputs from
S3 into PostgreSQL tables defined in `database/schema.sql`. It is deployed by
`GoldStack` as `gold-to-postgres-loader`.

In the deployed CDK app, `GoldStack` receives
`analytics_stack.postgres_private_host` from `app.py`, so `POSTGRES_HOST`
resolves to the private IP of the analytics EC2 instance. Constructor wiring
takes precedence over the older context/environment fallback.

The remaining loader settings can be configured through CDK context or
environment variables:

- `postgres_port` / `POSTGRES_PORT`
- `postgres_database` / `POSTGRES_DATABASE`
- `postgres_user` / `POSTGRES_USER`
- `postgres_password` / `POSTGRES_PASSWORD`

Do not commit real database passwords.

### PostgreSQL and Superset Analytics

Local analytics runs from `docker/analytics/docker-compose.yml` and starts:

- PostgreSQL 16
- Apache Superset with the PostgreSQL driver installed

The schema lives in `database/schema.sql`; analytics views live in
`database/views.sql`. Local Docker Compose does not automatically apply those
SQL files, so apply them with the commands in the local analytics runbook
below.

`AnalyticsStack` also provisions a demo EC2 host that runs PostgreSQL and
Superset with Docker Compose in the shared VPC. Its CloudFormation init applies
the schema and views during EC2 setup and is configured to fail loudly if setup
fails.

### Notification Stack

`NotificationStack` creates:

- SNS topic for pipeline alerts
- notification Lambda from `lambdas/notification_handler/handler.py`
- CloudWatch alarms for failed pipeline Lambda jobs
- Discord delivery through a webhook URL

The Discord webhook URL is mandatory for `NotificationStack`, but it can be
provided in either of these ways:

```bash
cdk synth NotificationStack \
  -c discord_webhook_url='replace-with-discord-webhook-url'
```

or:

```bash
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'
cdk synth NotificationStack
```

Use a real webhook only in your shell or deployment environment. Do not commit
it to the repository.

### CDK and IaC

CDK app entry point:

```text
infrastructure/app.py
```

Stacks:

- `DataLakeStack`
- `NetworkStack`
- `AnalyticsStack`
- `BronzeStack`
- `SilverStack`
- `GoldStack`
- `NotificationStack`

Infrastructure unit tests live under `infrastructure/tests/unit`.

## Repository Layout

```text
.
├── database/
│   ├── schema.sql
│   └── views.sql
├── docker/
│   └── analytics/
├── docs/
├── infrastructure/
├── lambdas/
│   ├── gold_to_postgres_loader/
│   ├── hn_gold_aggregation/
│   ├── hn_ingestion/
│   ├── hn_silver_normalization/
│   ├── notification_handler/
│   ├── x_gold_aggregation/
│   └── x_silver_normalization/
├── scripts/
└── tests/
```

## Local Setup

Application tests use the project root as `PYTHONPATH`.

Infrastructure tests in this runbook use a project-root `.venv`, matching the
`PYTHONPATH=../.venv/...` command shown below. Create it if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r infrastructure/requirements.txt
python -m pip install -r infrastructure/requirements-dev.txt
```

For local analytics smoke scripts, install the loader dependencies in your
active Python environment:

```bash
python -m pip install -r lambdas/gold_to_postgres_loader/requirements.txt
```

## Local Validation

Run these commands before presenting or opening a final PR.

Python syntax check:

```bash
python -m compileall -q lambdas scripts tests infrastructure/infrastructure
```

Application unit tests from the project root:

```bash
PYTHONPATH=. python -m pytest -q tests/unit
```

Infrastructure unit tests from the `infrastructure` directory:

```bash
cd infrastructure
PYTHONPATH=../.venv/lib/python3.12/site-packages:. python -m pytest -q tests/unit
cd ..
```

## Local PostgreSQL and Superset Validation

Start the local analytics stack:

```bash
cd docker/analytics
cp .env.example .env
docker compose config
docker compose up -d --build
docker compose ps
cd ../..
```

Apply the PostgreSQL schema and analytics views from the project root. This is
required for the local Docker Compose workflow because the compose file only
starts the services.

```bash
docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/schema.sql

docker exec -i social-analytics-postgres \
  psql -U superset -d social_analytics < database/views.sql
```

Run the local smoke tests:

```bash
python scripts/smoke_test_gold_to_postgres.py
python scripts/smoke_test_analytics_views.py
python scripts/seed_local_demo_gold_data.py
```

Expected result:

- the Docker containers are running,
- schema and views apply without SQL errors,
- the loader smoke test inserts sample rows,
- the analytics views smoke test validates all expected views,
- the demo seed script inserts multi-day dashboard data and verifies non-empty
  views.

## Superset Access

Open Superset locally:

```text
http://localhost:8088
```

Use the demo credentials from `docker/analytics/.env.example`:

- username: `admin`
- password: `admin`

For Superset running inside Docker, the PostgreSQL SQLAlchemy connection string
is:

```text
postgresql+psycopg2://superset:superset@postgres:5432/social_analytics
```

These are demo values only. Do not reuse them for a shared or public
deployment.

## CDK Synth and Deploy Examples

Bootstrap once per AWS account and region if needed:

```bash
cd infrastructure
source ../.venv/bin/activate
cdk bootstrap
```

For a demo or presentation, set `analytics_allowed_cidr` to your current public
IP as a `/32`:

```bash
ANALYTICS_ALLOWED_CIDR="$(curl -s https://checkip.amazonaws.com)/32"
```

Synthesize all stacks with placeholder values:

```bash
cd infrastructure
source ../.venv/bin/activate
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'

cdk synth \
  -c analytics_allowed_cidr="$ANALYTICS_ALLOWED_CIDR" \
  -c analytics_postgres_password='replace-with-demo-password' \
  -c analytics_superset_secret_key='replace-with-demo-secret-key' \
  -c postgres_password='replace-with-demo-password'
```

When `NotificationStack` is included, provide the Discord webhook through the
environment or a local-only CDK context value. Do not commit the value.

```bash
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'
```

Deploy the full shared-VPC demo app:

```bash
cd infrastructure
source ../.venv/bin/activate
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'

cdk deploy \
  DataLakeStack \
  NetworkStack \
  AnalyticsStack \
  BronzeStack \
  SilverStack \
  GoldStack \
  NotificationStack \
  -c analytics_allowed_cidr="$ANALYTICS_ALLOWED_CIDR" \
  -c analytics_instance_type='t3.micro' \
  -c analytics_postgres_password='replace-with-demo-password' \
  -c analytics_superset_secret_key='replace-with-demo-secret-key' \
  -c analytics_auto_stop_enabled=true \
  -c analytics_auto_stop_utc_hour=22 \
  -c postgres_password='replace-with-demo-password'
```

`NetworkStack` must be deployed with the pipeline and analytics stacks because
it owns the VPC, private subnets, NAT Gateway, S3 Gateway Endpoint, and shared
security groups.

Deploy a smaller subset only when you know its dependencies are already
available in the target environment. For example, after `DataLakeStack`,
`NetworkStack`, and `AnalyticsStack` exist:

```bash
cd infrastructure
source ../.venv/bin/activate
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'

cdk deploy BronzeStack SilverStack GoldStack NotificationStack \
  -c analytics_allowed_cidr="$ANALYTICS_ALLOWED_CIDR" \
  -c analytics_postgres_password='replace-with-demo-password' \
  -c analytics_superset_secret_key='replace-with-demo-secret-key' \
  -c postgres_password='replace-with-demo-password'
```

The gold-to-PostgreSQL loader no longer needs a public PostgreSQL host in the
deploy command. `app.py` wires `GoldStack` to
`analytics_stack.postgres_private_host`, so the deployed loader uses the private
PostgreSQL host from `AnalyticsStack`.

Deploy the notification stack with CDK context only for local one-off use:

```bash
cd infrastructure
source ../.venv/bin/activate

cdk deploy NotificationStack \
  -c discord_webhook_url='replace-with-discord-webhook-url'
```

Deploy the notification stack with an environment variable instead:

```bash
cd infrastructure
source ../.venv/bin/activate
export DISCORD_WEBHOOK_URL='replace-with-discord-webhook-url'

cdk deploy NotificationStack
```

The placeholders above are intentionally not real secrets, passwords, webhook
URLs, hosts, CIDRs, or AWS account identifiers.

## Final Manual Pipeline Flow

After the stacks are deployed, run the pipeline manually in this order for a
demo validation. These commands do not require opening PostgreSQL publicly.

Invoke Hacker News bronze ingestion for a specific date:

```bash
aws lambda invoke \
  --function-name hn-bronze-ingestion \
  --payload '{"date":"2026-05-18"}' \
  response.json
cat response.json
```

Upload the X dataset to the bronze S3 prefix. Use the deployed data lake bucket
name from `DataLakeStack` outputs:

```bash
python scripts/upload_x_dataset.py \
  --bucket replace-with-data-lake-bucket-name \
  --dataset-name x-synthetic-seed \
  --ingest-date 2026-05-30
```

Invoke Hacker News and X silver normalization:

```bash
aws lambda invoke \
  --function-name normalize-hn-silver \
  --payload fileb://lambdas/hn_silver_normalization/test_event.json \
  hn_silver_response.json \
  --cli-read-timeout 900
cat hn_silver_response.json

aws lambda invoke \
  --function-name normalize-x-silver \
  --payload fileb://lambdas/x_silver_normalization/test_event.json \
  x_silver_response.json \
  --cli-read-timeout 900
cat x_silver_response.json
```

Invoke Hacker News and X gold aggregation:

```bash
aws lambda invoke \
  --function-name build-hn-gold \
  --payload fileb://lambdas/hn_gold_aggregation/test_event.json \
  hn_gold_response.json \
  --cli-read-timeout 900
cat hn_gold_response.json

aws lambda invoke \
  --function-name build-x-gold \
  --payload fileb://lambdas/x_gold_aggregation/test_event.json \
  x_gold_response.json \
  --cli-read-timeout 900
cat x_gold_response.json
```

Invoke the gold-to-PostgreSQL loader after gold Parquet outputs exist. For the
shared-VPC AWS deployment, rely on the loader environment variables that CDK
wired at deploy time. Do not open PostgreSQL to `0.0.0.0/0`.

Create a local event file that does not override `postgres_host` with a public
host:

```bash
cat > gold_to_postgres_runtime_event.json <<'EOF'
{
  "bucket": "replace-with-data-lake-bucket-name",
  "gold_prefix": "gold",
  "data_date": "2026-05-20",
  "platforms": ["hacker-news", "x"],
  "datasets": null,
  "mode": "replace_date"
}
EOF
```

```bash
aws lambda invoke \
  --function-name gold-to-postgres-loader \
  --payload fileb://gold_to_postgres_runtime_event.json \
  gold_to_postgres_response.json \
  --cli-read-timeout 900
cat gold_to_postgres_response.json
```

Then open the `SupersetUrl` output in a browser from an IP allowed by
`analytics_allowed_cidr`, refresh datasets if needed, and view the dashboard.

Do not commit runtime event files containing real bucket names, credentials, or
host values.

## Security Checklist

Before presenting or opening a final PR, verify:

- No tcp/5432 ingress exists from `0.0.0.0/0`.
- Superset tcp/8088 ingress is restricted to `analytics_allowed_cidr`.
- Pipeline Lambdas synthesize with `VpcConfig`.
- `PipelineLambdaSecurityGroup` can reach `AnalyticsSecurityGroup` on tcp/5432.
- The S3 Gateway Endpoint exists in `NetworkStack`.
- The NAT Gateway exists for external APIs and the Discord webhook.
- `gold-to-postgres-loader` uses the private `AnalyticsStack` PostgreSQL host
  through `app.py` wiring.
- No real secrets, real IPs, real AWS account IDs, or real Discord webhook URLs
  are committed.

## Final Pre-Commit Checklist

- `PYTHONPATH=. python -m pytest -q tests/unit` passes.
- Infrastructure tests pass from `infrastructure`.
- Docker analytics stack starts with `docker compose up -d --build`.
- Local smoke tests pass.
- Superset dashboard or screenshots are prepared for the presentation.
- No `.env`, `.venv`, `.idea`, `cdk.out`, `__pycache__`, or real secrets are
  committed.

## Additional Docs

- `docs/kt2-deploy.md`
- `docs/gold-deploy.md`
- `docs/gold-to-postgres-loader.md`
- `docs/postgres-superset-ec2.md`
- `docs/superset-dashboard-guide.md`
- `docker/analytics/README.md`
