# PostgreSQL and Superset on EC2

`AnalyticsStack` provisions a small demo analytics host that runs PostgreSQL and
Apache Superset on one public EC2 instance with Docker Compose. It is intended
for KT2 visualization work and simple demo/admin access, not as a production
database design.

The stack creates:

- a small public VPC with no NAT gateways
- one Amazon Linux 2023 EC2 instance, defaulting to `t3.small`
- a security group for Superset and PostgreSQL access
- EC2 user data that installs Docker, installs Docker Compose support, writes
  the analytics Docker Compose files, starts PostgreSQL and Superset, and
  applies `database/schema.sql`
- an optional in-instance daily auto-stop cron guardrail for demo cost control

## Synthesize

```bash
cd infrastructure

cdk synth AnalyticsStack \
  -c analytics_allowed_cidr=x.x.x.x/32 \
  -c analytics_postgres_password='replace-me' \
  -c analytics_superset_secret_key='replace-me'
```

## Deploy Only AnalyticsStack

```bash
cd infrastructure

cdk deploy AnalyticsStack \
  -c analytics_allowed_cidr=x.x.x.x/32 \
  -c analytics_instance_type=t3.micro \
  -c analytics_postgres_password='replace-me' \
  -c analytics_superset_secret_key='replace-me' \
  -c analytics_auto_stop_enabled=true \
  -c analytics_auto_stop_utc_hour=22
```

Do not commit real passwords, Superset admin credentials, or Superset secret
keys. CDK context values used here are rendered into the synthesized template
and EC2 user data.

`cdk synth` is safe for cost review because it only generates CloudFormation
templates locally. `cdk deploy` creates billable AWS resources.

## Configuration

Supported CDK context keys and environment variables:

| Purpose | Context key | Environment variable | Default |
| --- | --- | --- | --- |
| Inbound access CIDR | `analytics_allowed_cidr` | `ANALYTICS_ALLOWED_CIDR` | `0.0.0.0/0` |
| Optional EC2 SSH key pair | `analytics_key_name` | `ANALYTICS_KEY_NAME` | empty |
| EC2 instance type | `analytics_instance_type` | `ANALYTICS_INSTANCE_TYPE` | `t3.small` |
| Enable daily auto-stop | `analytics_auto_stop_enabled` | `ANALYTICS_AUTO_STOP_ENABLED` | `true` |
| Daily auto-stop UTC hour | `analytics_auto_stop_utc_hour` | `ANALYTICS_AUTO_STOP_UTC_HOUR` | `22` |
| PostgreSQL database | `analytics_postgres_db` | `ANALYTICS_POSTGRES_DB` | `social_analytics` |
| PostgreSQL user | `analytics_postgres_user` | `ANALYTICS_POSTGRES_USER` | `superset` |
| PostgreSQL password | `analytics_postgres_password` | `ANALYTICS_POSTGRES_PASSWORD` | `change-me` |
| Superset admin username | `analytics_superset_admin_username` | `ANALYTICS_SUPERSET_ADMIN_USERNAME` | `admin` |
| Superset admin password | `analytics_superset_admin_password` | `ANALYTICS_SUPERSET_ADMIN_PASSWORD` | `admin` |
| Superset secret key | `analytics_superset_secret_key` | `ANALYTICS_SUPERSET_SECRET_KEY` | `change-me` |

For real usage, set `analytics_allowed_cidr` to your own `/32` public IP.
The default `0.0.0.0/0` is only for demos and opens Superset and PostgreSQL to
the internet.

If `analytics_key_name` is set, the stack also opens TCP 22 from
`analytics_allowed_cidr` and attaches that EC2 key pair to the instance. If it
is not set, SSH is not opened.

`analytics_instance_type` can be lowered to `t3.micro` for a smaller demo. Keep
`t3.small` if Superset startup or dashboard usage needs more memory.

When `analytics_auto_stop_enabled` is true, EC2 user data creates
`/etc/cron.d/social-analytics-auto-stop`. The cron job runs at
`analytics_auto_stop_utc_hour` and calls `shutdown -h now`. The instance uses
instance-initiated shutdown behavior `STOP`, not `TERMINATE`, so the demo host
stops instead of deleting itself. The configured hour must be an integer from
`0` through `23`.

## Cost Safety

- Use `cdk synth` before deployment to inspect the generated template without
  creating resources.
- `cdk deploy AnalyticsStack` creates billable AWS resources.
- Stop the EC2 instance when you are not using Superset.
- Destroy `AnalyticsStack` after the demo if it is no longer needed.
- A stopped EC2 instance can still have storage and public IP related costs.
- Never leave `analytics_allowed_cidr=0.0.0.0/0` open longer than needed.
- Use your own `/32` public IP for demos whenever possible.

Deploy with a restricted CIDR:

```bash
cd infrastructure

cdk deploy AnalyticsStack \
  -c analytics_allowed_cidr=x.x.x.x/32 \
  -c analytics_instance_type=t3.micro \
  -c analytics_postgres_password='replace-me' \
  -c analytics_superset_secret_key='replace-me'
```

Stop the instance after a demo:

```bash
aws ec2 stop-instances --instance-ids INSTANCE_ID
```

Destroy the stack after a demo:

```bash
cd infrastructure
cdk destroy AnalyticsStack
```

## Access

After deployment, use the CloudFormation outputs:

- `SupersetUrl`: open this URL in a browser.
- `PostgresHost`: use this host for PostgreSQL clients.
- `PostgresPort`: `5432`.

Default Superset login values are:

- username: `admin`
- password: `admin`

Override the defaults for any shared demo environment.

PostgreSQL connection defaults are:

- database: `social_analytics`
- user: `superset`
- password: `change-me`
- host: `PostgresHost` output
- port: `5432`

## Loader Lambda Relationship

This stack only hosts PostgreSQL and Superset. The existing
`gold-to-postgres-loader` Lambda can be configured separately with PostgreSQL
host, port, database, user, and password values, but this feature does not solve
Lambda-to-EC2 networking. VPC placement, private routing, or more restrictive
network access for the loader Lambda is handled in a later feature.
