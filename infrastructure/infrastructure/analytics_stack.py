import os
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Fn,
    Stack,
    Tags,
    aws_ec2 as ec2,
)
from constructs import Construct


class AnalyticsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo_root = Path(__file__).resolve().parents[2]
        compose_content = (
            repo_root / "docker" / "analytics" / "docker-compose.yml"
        ).read_text(encoding="utf-8")
        superset_init_content = (
            repo_root / "docker" / "analytics" / "superset-init.sh"
        ).read_text(encoding="utf-8")
        superset_dockerfile_content = (
            repo_root / "docker" / "analytics" / "superset" / "Dockerfile"
        ).read_text(encoding="utf-8")
        schema_content = (repo_root / "database" / "schema.sql").read_text(
            encoding="utf-8"
        )
        views_content = (repo_root / "database" / "views.sql").read_text(
            encoding="utf-8"
        )

        allowed_cidr = self._context_or_env(
            "analytics_allowed_cidr", "ANALYTICS_ALLOWED_CIDR", "0.0.0.0/0"
        )
        key_name = self._context_or_env(
            "analytics_key_name", "ANALYTICS_KEY_NAME", ""
        )
        instance_type_value = self._context_or_env(
            "analytics_instance_type", "ANALYTICS_INSTANCE_TYPE", "t3.small"
        )
        auto_stop_enabled = self._context_or_env_bool(
            "analytics_auto_stop_enabled",
            "ANALYTICS_AUTO_STOP_ENABLED",
            True,
        )
        auto_stop_utc_hour = self._context_or_env_int(
            "analytics_auto_stop_utc_hour",
            "ANALYTICS_AUTO_STOP_UTC_HOUR",
            22,
        )
        if not 0 <= auto_stop_utc_hour <= 23:
            raise ValueError(
                "analytics_auto_stop_utc_hour must be an integer between 0 and 23."
            )

        postgres_db = self._context_or_env(
            "analytics_postgres_db",
            "ANALYTICS_POSTGRES_DB",
            "social_analytics",
        )
        postgres_user = self._context_or_env(
            "analytics_postgres_user",
            "ANALYTICS_POSTGRES_USER",
            "superset",
        )
        postgres_password = self._context_or_env(
            "analytics_postgres_password",
            "ANALYTICS_POSTGRES_PASSWORD",
            "change-me",
        )
        superset_admin_username = self._context_or_env(
            "analytics_superset_admin_username",
            "ANALYTICS_SUPERSET_ADMIN_USERNAME",
            "admin",
        )
        superset_admin_password = self._context_or_env(
            "analytics_superset_admin_password",
            "ANALYTICS_SUPERSET_ADMIN_PASSWORD",
            "admin",
        )
        superset_secret_key = self._context_or_env(
            "analytics_superset_secret_key",
            "ANALYTICS_SUPERSET_SECRET_KEY",
            "change-me",
        )

        vpc = ec2.Vpc(
            self,
            "AnalyticsVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )
        Tags.of(vpc).add("Name", "social-analytics-vpc")

        security_group = ec2.SecurityGroup(
            self,
            "AnalyticsSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
            description="Security group for PostgreSQL and Superset analytics EC2.",
        )
        Tags.of(security_group).add("Name", "social-analytics-sg")

        analytics_peer = ec2.Peer.ipv4(allowed_cidr)
        security_group.add_ingress_rule(
            analytics_peer,
            ec2.Port.tcp(8088),
            "Superset web UI access.",
        )
        security_group.add_ingress_rule(
            analytics_peer,
            ec2.Port.tcp(5432),
            "PostgreSQL demo/admin access.",
        )
        if key_name:
            security_group.add_ingress_rule(
                analytics_peer,
                ec2.Port.tcp(22),
                "SSH access for configured key pair.",
            )

        user_data = ec2.UserData.for_linux()
        user_data_commands = [
            "set -euxo pipefail",
            "dnf update -y",
            "dnf install -y docker curl",
        ]
        if auto_stop_enabled:
            user_data_commands.extend(
                [
                    "# Demo cost guardrail: keep cron in UTC for predictable auto-stop.",
                    "timedatectl set-timezone UTC",
                    "dnf install -y cronie",
                    "systemctl enable --now crond",
                    self._write_file_command(
                        "/etc/cron.d/social-analytics-auto-stop",
                        "\n".join(
                            [
                                (
                                    "# Demo cost guardrail: stop this EC2 instance "
                                    "daily to reduce accidental runtime cost."
                                ),
                                (
                                    f"0 {auto_stop_utc_hour} * * * root "
                                    "/sbin/shutdown -h now"
                                ),
                            ]
                        ),
                    ),
                    "chmod 644 /etc/cron.d/social-analytics-auto-stop",
                ]
            )
        user_data_commands.extend(
            [
                "systemctl enable --now docker",
                "mkdir -p /usr/local/lib/docker/cli-plugins",
                (
                    "if ! docker compose version >/dev/null 2>&1; then "
                    "ARCH=$(uname -m); "
                    "case \"$ARCH\" in x86_64) COMPOSE_ARCH=x86_64 ;; "
                    "aarch64) COMPOSE_ARCH=aarch64 ;; "
                    "*) echo \"Unsupported architecture: $ARCH\" >&2; exit 1 ;; "
                    "esac; "
                    "curl -SL "
                    "https://github.com/docker/compose/releases/download/v2.29.7/"
                    "docker-compose-linux-${COMPOSE_ARCH} "
                    "-o /usr/local/lib/docker/cli-plugins/docker-compose; "
                    "chmod +x /usr/local/lib/docker/cli-plugins/docker-compose; "
                    "fi"
                ),
                "mkdir -p /opt/social-analytics/superset",
                "cd /opt/social-analytics",
                self._write_file_command("docker-compose.yml", compose_content),
                self._write_file_command(
                    "superset/Dockerfile", superset_dockerfile_content
                ),
                self._write_file_command(
                    ".env",
                    "\n".join(
                        [
                            f"POSTGRES_DB={postgres_db}",
                            f"POSTGRES_USER={postgres_user}",
                            f"POSTGRES_PASSWORD={postgres_password}",
                            f"SUPERSET_ADMIN_USERNAME={superset_admin_username}",
                            f"SUPERSET_ADMIN_PASSWORD={superset_admin_password}",
                            "SUPERSET_ADMIN_FIRST_NAME=Admin",
                            "SUPERSET_ADMIN_LAST_NAME=User",
                            "SUPERSET_ADMIN_EMAIL=admin@example.com",
                            f"SUPERSET_SECRET_KEY={superset_secret_key}",
                        ]
                    ),
                ),
                self._write_file_command("superset-init.sh", superset_init_content),
                self._write_file_command("schema.sql", schema_content),
                self._write_file_command("views.sql", views_content),
                "chmod 600 .env",
                "chmod +x superset-init.sh",
                "docker compose pull postgres",
                "docker compose up -d --build",
                (
                    "POSTGRES_READY=0; "
                    "for attempt in $(seq 1 60); do "
                    "if docker inspect -f '{{.State.Health.Status}}' "
                    "social-analytics-postgres | grep -q healthy; then "
                    "POSTGRES_READY=1; break; "
                    "fi; "
                    "sleep 5; "
                    "done; "
                    "if [ \"$POSTGRES_READY\" != \"1\" ]; then "
                    "docker logs social-analytics-postgres; "
                    "exit 1; "
                    "fi"
                ),
                (
                    "docker compose exec -T postgres sh -c "
                    "'psql -v ON_ERROR_STOP=1 -U \"$POSTGRES_USER\" "
                    "-d \"$POSTGRES_DB\"' < schema.sql"
                ),
                (
                    "docker compose exec -T postgres sh -c "
                    "'psql -v ON_ERROR_STOP=1 -U \"$POSTGRES_USER\" "
                    "-d \"$POSTGRES_DB\"' < views.sql"
                ),
            ]
        )
        user_data.add_commands(*user_data_commands)

        instance_kwargs = {}
        if key_name:
            instance_kwargs["key_name"] = key_name

        analytics_instance = ec2.Instance(
            self,
            "AnalyticsInstance",
            instance_name="social-analytics-ec2",
            instance_type=ec2.InstanceType(instance_type_value),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=security_group,
            associate_public_ip_address=True,
            instance_initiated_shutdown_behavior=(
                ec2.InstanceInitiatedShutdownBehavior.STOP
            ),
            user_data=user_data,
            **instance_kwargs,
        )
        Tags.of(analytics_instance).add("Name", "social-analytics-ec2")

        CfnOutput(
            self,
            "AnalyticsInstanceId",
            value=analytics_instance.instance_id,
        )
        CfnOutput(
            self,
            "AnalyticsPublicIp",
            value=analytics_instance.instance_public_ip,
        )
        CfnOutput(
            self,
            "AnalyticsPublicDnsName",
            value=analytics_instance.instance_public_dns_name,
        )
        CfnOutput(
            self,
            "SupersetUrl",
            value=Fn.join(
                "",
                ["http://", analytics_instance.instance_public_dns_name, ":8088"],
            ),
        )
        CfnOutput(
            self,
            "PostgresHost",
            value=analytics_instance.instance_public_dns_name,
        )
        CfnOutput(
            self,
            "PostgresPort",
            value="5432",
        )
        if auto_stop_enabled:
            CfnOutput(
                self,
                "AnalyticsAutoStopUtcHour",
                value=str(auto_stop_utc_hour),
            )

    def _context_or_env(self, context_key: str, env_key: str, default: str) -> str:
        value = self.node.try_get_context(context_key)
        if value is None:
            value = os.getenv(env_key, default)
        return str(value)

    def _context_or_env_bool(
        self, context_key: str, env_key: str, default: bool
    ) -> bool:
        raw_value = self.node.try_get_context(context_key)
        if raw_value is None:
            raw_value = os.getenv(env_key)
        if raw_value is None:
            return default
        if isinstance(raw_value, bool):
            return raw_value

        normalized_value = str(raw_value).strip().lower()
        if normalized_value in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized_value in {"0", "false", "no", "n", "off"}:
            return False
        raise ValueError(f"{context_key} must be true or false.")

    def _context_or_env_int(
        self, context_key: str, env_key: str, default: int
    ) -> int:
        raw_value = self.node.try_get_context(context_key)
        if raw_value is None:
            raw_value = os.getenv(env_key)
        if raw_value is None:
            return default
        try:
            return int(str(raw_value))
        except ValueError as error:
            raise ValueError(f"{context_key} must be an integer.") from error

    def _write_file_command(self, path: str, content: str) -> str:
        return f"cat > {path} <<'EOF_SOCIAL_ANALYTICS'\n{content.rstrip()}\nEOF_SOCIAL_ANALYTICS"
