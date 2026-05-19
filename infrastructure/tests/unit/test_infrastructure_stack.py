import aws_cdk as core
import aws_cdk.assertions as assertions

from infrastructure.infrastructure_stack import InfrastructureStack


def _template():
    app = core.App()
    stack = InfrastructureStack(app, "infrastructure")
    return assertions.Template.from_stack(stack)


def test_s3_bucket_has_expected_security_properties():
    template = _template()
    template.has_resource_properties(
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


def test_lambda_has_bucket_environment_variable():
    template = _template()
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
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


def test_eventbridge_rule_is_daily_at_0200_utc():
    template = _template()
    template.has_resource_properties(
        "AWS::Events::Rule",
        {"ScheduleExpression": "cron(0 2 * * ? *)", "State": "ENABLED"},
    )


def test_iam_policy_does_not_grant_admin_wildcards():
    template = _template()
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
