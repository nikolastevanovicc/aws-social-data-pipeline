import aws_cdk as core
import aws_cdk.assertions as assertions

from infrastructure.bronze_stack import BronzeStack
from infrastructure.data_lake_stack import DataLakeStack
from infrastructure.gold_stack import GoldStack
from infrastructure.silver_stack import SilverStack


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
    for template in _stacks():
        template_json = template.to_json()
        policies = template_json["Resources"]

        for resource in policies.values():
            if resource["Type"] != "AWS::IAM::Policy":
                continue
            for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
                actions = statement["Action"]
                if isinstance(actions, str):
                    actions = [actions]
                assert "*" not in actions
                assert "s3:*" not in actions
                assert "iam:*" not in actions
