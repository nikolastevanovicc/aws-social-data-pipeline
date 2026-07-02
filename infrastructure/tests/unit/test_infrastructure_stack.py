import json
from functools import lru_cache
from pathlib import Path

import aws_cdk as core
import aws_cdk.assertions as assertions
import pytest

from infrastructure.analytics_stack import AnalyticsStack
from infrastructure.bronze_stack import BronzeStack
from infrastructure.data_lake_stack import DataLakeStack
from infrastructure.gold_stack import GoldStack
from infrastructure.notification_stack import NotificationStack
from infrastructure.silver_stack import SilverStack


@lru_cache(maxsize=1)
def _stacks():
    app = core.App()
    data_lake_stack = DataLakeStack(app, "data-lake")
    bronze_stack = BronzeStack(
        app,
        "bronze",
        data_lake_bucket=data_lake_stack.data_lake_bucket,
    )
    silver_stack = SilverStack(
        app,
        "silver",
        data_lake_bucket=data_lake_stack.data_lake_bucket,
    )
    gold_stack = GoldStack(
        app,
        "gold",
        data_lake_bucket=data_lake_stack.data_lake_bucket,
    )
    return (
        assertions.Template.from_stack(data_lake_stack),
        assertions.Template.from_stack(bronze_stack),
        assertions.Template.from_stack(silver_stack),
        assertions.Template.from_stack(gold_stack),
    )


@lru_cache(maxsize=1)
def _analytics_stack():
    return _analytics_template()


def _analytics_template(context=None):
    default_context = {
        "analytics_allowed_cidr": "0.0.0.0/0",
        "analytics_postgres_password": "dummy",
        "analytics_superset_secret_key": "dummy",
    }
    if context is not None:
        default_context.update(context)

    app = core.App(context=default_context)
    analytics_stack = AnalyticsStack(app, "analytics")
    return assertions.Template.from_stack(analytics_stack)


def _notification_template(context=None):
    app = core.App(context=context or {})
    notification_stack = NotificationStack(app, "notification")
    return assertions.Template.from_stack(notification_stack)


def _all_templates():
    return (*_stacks(), _analytics_stack())


def test_s3_bucket_has_expected_security_properties():
    data_lake_template, _, _, _ = _stacks()
    data_lake_template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
            "VersioningConfiguration": {"Status": "Enabled"},
        },
    )


def test_bronze_lambda_has_expected_environment_variables():
    _, bronze_template, _, _ = _stacks()
    bronze_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "hn-bronze-ingestion",
            "Handler": "handler.lambda_handler",
            "Runtime": "python3.12",
            "Environment": {
                "Variables": {
                    "DATA_LAKE_BUCKET": assertions.Match.any_value(),
                    "HN_BRONZE_PREFIX": "bronze/hacker-news",
                }
            },
        },
    )


def test_bronze_eventbridge_rule_is_daily_at_0200_utc():
    _, bronze_template, _, _ = _stacks()
    bronze_template.has_resource_properties(
        "AWS::Events::Rule",
        {"ScheduleExpression": "cron(0 2 * * ? *)", "State": "ENABLED"},
    )


def test_silver_lambdas_have_expected_environment_variables():
    _, _, silver_template, _ = _stacks()
    expected_environment = {
        "Variables": {
            "DATA_LAKE_BUCKET": assertions.Match.any_value(),
            "BRONZE_HN_PREFIX": "bronze/hacker-news",
            "BRONZE_X_PREFIX": "bronze/x",
            "SILVER_PREFIX": "silver",
            "DEFAULT_X_DATASET_NAME": "x-synthetic-seed",
        }
    }

    silver_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "normalize-hn-silver",
            "Handler": "handler.lambda_handler",
            "Runtime": "python3.12",
            "Environment": expected_environment,
        },
    )
    silver_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "normalize-x-silver",
            "Handler": "handler.lambda_handler",
            "Runtime": "python3.12",
            "Environment": expected_environment,
        },
    )


def test_silver_lambdas_include_aws_sdk_pandas_layer():
    _, _, silver_template, _ = _stacks()
    expected_layer = [
        "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:27"
    ]

    silver_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "normalize-hn-silver",
            "Architectures": ["x86_64"],
            "Layers": expected_layer,
        },
    )
    silver_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "normalize-x-silver",
            "Architectures": ["x86_64"],
            "Layers": expected_layer,
        },
    )


def test_silver_iam_policy_has_bronze_read_and_silver_write_access():
    _, _, silver_template, _ = _stacks()
    silver_template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {"Action": "s3:ListBucket", "Effect": "Allow"}
                        ),
                        assertions.Match.object_like(
                            {"Action": "s3:GetObject", "Effect": "Allow"}
                        ),
                        assertions.Match.object_like(
                            {"Action": "s3:PutObject", "Effect": "Allow"}
                        ),
                    ]
                )
            }
        },
    )


def test_gold_lambdas_have_expected_environment_variables():
    _, _, _, gold_template = _stacks()
    expected_environment = {
        "Variables": {
            "DATA_LAKE_BUCKET": assertions.Match.any_value(),
            "SILVER_PREFIX": "silver",
            "GOLD_PREFIX": "gold",
            "HN_GOLD_PREFIX": "gold/hacker-news",
            "X_GOLD_PREFIX": "gold/x",
        }
    }

    gold_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "build-hn-gold",
            "Handler": "handler.lambda_handler",
            "Runtime": "python3.12",
            "Environment": expected_environment,
        },
    )
    gold_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "build-x-gold",
            "Handler": "handler.lambda_handler",
            "Runtime": "python3.12",
            "Environment": expected_environment,
        },
    )


def test_gold_lambdas_include_aws_sdk_pandas_layer():
    _, _, _, gold_template = _stacks()
    expected_layer = [
        "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:27"
    ]

    gold_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "build-hn-gold",
            "Architectures": ["x86_64"],
            "Layers": expected_layer,
        },
    )
    gold_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "build-x-gold",
            "Architectures": ["x86_64"],
            "Layers": expected_layer,
        },
    )


def test_gold_to_postgres_loader_has_expected_configuration():
    _, _, _, gold_template = _stacks()

    gold_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "gold-to-postgres-loader",
            "Handler": "handler.lambda_handler",
            "Runtime": "python3.12",
            "Architectures": ["x86_64"],
            "Timeout": 300,
            "MemorySize": 1024,
            "Environment": {
                "Variables": {
                    "DATA_LAKE_BUCKET": assertions.Match.any_value(),
                    "GOLD_PREFIX": "gold",
                    "POSTGRES_HOST": assertions.Match.any_value(),
                    "POSTGRES_PORT": assertions.Match.any_value(),
                    "POSTGRES_DATABASE": assertions.Match.any_value(),
                    "POSTGRES_USER": assertions.Match.any_value(),
                    "POSTGRES_PASSWORD": assertions.Match.any_value(),
                }
            },
        },
    )


def test_gold_to_postgres_loader_includes_aws_sdk_pandas_layer():
    _, _, _, gold_template = _stacks()
    expected_layer = [
        "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:27"
    ]

    gold_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "gold-to-postgres-loader",
            "Layers": expected_layer,
        },
    )


def test_gold_to_postgres_loader_has_gold_s3_read_access():
    _, _, _, gold_template = _stacks()
    template_json = gold_template.to_json()

    statements = []
    for resource in template_json["Resources"].values():
        if resource["Type"] != "AWS::IAM::Policy":
            continue
        policy_statements = resource["Properties"]["PolicyDocument"]["Statement"]
        statements.extend(policy_statements)

    assert any(
        statement["Effect"] == "Allow"
        and "s3:GetObject*" in _as_list(statement["Action"])
        and "gold/*" in repr(statement["Resource"])
        for statement in statements
    )


def test_gold_to_postgres_loader_output_is_synthesized():
    _, _, _, gold_template = _stacks()

    gold_template.has_output(
        "GoldToPostgresLoaderFunctionName",
        {"Value": assertions.Match.any_value()},
    )


def test_gold_to_postgres_loader_sample_event_is_valid_json():
    repo_root = Path(__file__).resolve().parents[3]
    event_path = (
        repo_root
        / "lambdas"
        / "gold_to_postgres_loader"
        / "test_event.example.json"
    )

    event = json.loads(event_path.read_text(encoding="utf-8"))

    assert event["bucket"] == "replace-with-data-lake-bucket-name"
    assert event["gold_prefix"] == "gold"
    assert event["data_date"] == "2026-05-20"
    assert event["platforms"] == ["hacker-news", "x"]
    assert event["datasets"] is None
    assert event["mode"] == "replace_date"


def test_gold_iam_policy_has_silver_read_and_gold_write_access():
    _, _, _, gold_template = _stacks()
    gold_template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {"Action": "s3:ListBucket", "Effect": "Allow"}
                        ),
                        assertions.Match.object_like(
                            {"Action": "s3:GetObject", "Effect": "Allow"}
                        ),
                        assertions.Match.object_like(
                            {"Action": "s3:PutObject", "Effect": "Allow"}
                        ),
                    ]
                )
            }
        },
    )


def test_iam_policies_do_not_grant_admin_wildcards():
    for template in _all_templates():
        template_json = template.to_json()
        policies = template_json["Resources"]

        for resource in policies.values():
            if resource["Type"] not in {"AWS::IAM::Policy", "AWS::IAM::ManagedPolicy"}:
                continue
            policy_document = resource["Properties"]["PolicyDocument"]
            for statement in policy_document["Statement"]:
                actions = statement["Action"]
                if isinstance(actions, str):
                    actions = [actions]
                assert "*" not in actions
                assert "s3:*" not in actions
                assert "iam:*" not in actions
                assert "ec2:*" not in actions


def test_analytics_stack_synthesizes_ec2_instance():
    analytics_template = _analytics_stack()

    analytics_template.resource_count_is("AWS::EC2::Instance", 1)
    analytics_template.has_resource_properties(
        "AWS::EC2::Instance",
        {
            "InstanceType": "t3.small",
            "Tags": assertions.Match.array_with(
                [{"Key": "Name", "Value": "social-analytics-ec2"}]
            ),
        },
    )


def test_analytics_instance_type_can_be_configured():
    analytics_template = _analytics_template({"analytics_instance_type": "t3.micro"})

    analytics_template.has_resource_properties(
        "AWS::EC2::Instance",
        {"InstanceType": "t3.micro"},
    )


def test_analytics_security_group_allows_superset_and_postgres_ports():
    analytics_template = _analytics_stack()

    analytics_template.has_resource_properties(
        "AWS::EC2::SecurityGroup",
        {
            "SecurityGroupIngress": assertions.Match.array_with(
                [
                    assertions.Match.object_like(
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 8088,
                            "ToPort": 8088,
                            "CidrIp": "0.0.0.0/0",
                        }
                    )
                ]
            )
        },
    )
    analytics_template.has_resource_properties(
        "AWS::EC2::SecurityGroup",
        {
            "SecurityGroupIngress": assertions.Match.array_with(
                [
                    assertions.Match.object_like(
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 5432,
                            "ToPort": 5432,
                            "CidrIp": "0.0.0.0/0",
                        }
                    )
                ]
            )
        },
    )


def test_analytics_outputs_are_synthesized():
    analytics_template = _analytics_stack()

    for output_name in [
        "AnalyticsInstanceId",
        "AnalyticsPublicIp",
        "AnalyticsPublicDnsName",
        "SupersetUrl",
        "PostgresHost",
        "PostgresPort",
        "AnalyticsAutoStopUtcHour",
    ]:
        analytics_template.has_output(
            output_name,
            {"Value": assertions.Match.any_value()},
        )


def test_analytics_cloudformation_init_is_synthesized():
    analytics_template = _analytics_stack()
    user_data = _analytics_instance_user_data(analytics_template)
    init_metadata = _analytics_instance_init_metadata(analytics_template)

    assert "cfn-init" in user_data
    assert "docker compose up -d --build" not in user_data
    assert "docker compose up -d --build" in init_metadata
    assert "social-analytics-postgres" in init_metadata
    assert "/opt/social-analytics/superset/Dockerfile" in init_metadata
    assert "psycopg2-binary" in init_metadata
    assert "/opt/social-analytics/schema.sql" in init_metadata
    assert "/opt/social-analytics/views.sql" in init_metadata
    assert "docker-compose-linux-${COMPOSE_ARCH}" in init_metadata
    assert "curl -fSL" in init_metadata
    assert "cfn-signal -e 0" in user_data
    assert init_metadata.index("< schema.sql") < init_metadata.index("< views.sql")


def test_analytics_instance_has_ssm_managed_policy():
    analytics_template = _analytics_stack()

    assert "AmazonSSMManagedInstanceCore" in repr(analytics_template.to_json())


def test_analytics_cloudformation_init_contains_default_shutdown_cron():
    analytics_template = _analytics_stack()
    init_metadata = _analytics_instance_init_metadata(analytics_template)

    assert "Demo cost guardrail" in init_metadata
    assert "social-analytics-auto-stop" in init_metadata
    assert "/sbin/shutdown -h now" in init_metadata
    assert "0 22 * * * root" in init_metadata
    assert "docker compose pull postgres" in init_metadata
    assert init_metadata.index("social-analytics-auto-stop") < init_metadata.index(
        "docker compose pull postgres"
    )


def test_analytics_auto_stop_can_be_disabled():
    analytics_template = _analytics_template({"analytics_auto_stop_enabled": "false"})
    template_json = analytics_template.to_json()
    init_metadata = _analytics_instance_init_metadata(analytics_template)

    assert "social-analytics-auto-stop" not in init_metadata
    assert "/sbin/shutdown -h now" not in init_metadata
    assert "AnalyticsAutoStopUtcHour" not in template_json.get("Outputs", {})


def test_analytics_invalid_auto_stop_hour_raises_value_error():
    with pytest.raises(ValueError, match="between 0 and 23"):
        _analytics_template({"analytics_auto_stop_utc_hour": "24"})


def test_notification_stack_synthesizes_with_discord_webhook_context(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    notification_template = _notification_template(
        {"discord_webhook_url": "https://example.com/discord-context"}
    )

    notification_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "pipeline-notification-handler",
            "Environment": {
                "Variables": {
                    "DISCORD_WEBHOOK_URL": "https://example.com/discord-context"
                }
            },
        },
    )


def test_notification_stack_synthesizes_with_discord_webhook_env(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/discord-env")

    notification_template = _notification_template()

    notification_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "pipeline-notification-handler",
            "Environment": {
                "Variables": {
                    "DISCORD_WEBHOOK_URL": "https://example.com/discord-env"
                }
            },
        },
    )


def test_notification_stack_requires_discord_webhook_url(monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    with pytest.raises(ValueError) as error:
        _notification_template()

    message = str(error.value)
    assert "-c discord_webhook_url=..." in message
    assert "DISCORD_WEBHOOK_URL" in message


def _analytics_instance_user_data(analytics_template):
    instance = _analytics_instance(analytics_template)
    return repr(instance["Properties"].get("UserData"))


def _analytics_instance_init_metadata(analytics_template):
    instance = _analytics_instance(analytics_template)
    return repr(instance["Metadata"].get("AWS::CloudFormation::Init"))


def _analytics_instance(analytics_template):
    template_json = analytics_template.to_json()
    instances = [
        resource
        for resource in template_json["Resources"].values()
        if resource["Type"] == "AWS::EC2::Instance"
    ]

    assert len(instances) == 1
    return instances[0]


def _as_list(value):
    if isinstance(value, list):
        return value
    return [value]
