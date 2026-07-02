import os
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_ec2 as ec2,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct


class NotificationStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc | None = None,
        lambda_security_group: ec2.ISecurityGroup | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        lambda_network_config = self._lambda_network_config(
            vpc, lambda_security_group
        )

        discord_webhook_url = self.node.try_get_context(
            "discord_webhook_url"
        ) or os.getenv("DISCORD_WEBHOOK_URL")

        if not discord_webhook_url:
            raise ValueError(
                "Missing Discord webhook URL. Provide it with "
                "-c discord_webhook_url=... or DISCORD_WEBHOOK_URL."
            )

        alerts_topic = sns.Topic(
            self,
            "PipelineAlertsTopic",
            topic_name="pipeline-alerts-topic",
        )

        notification_lambda_role = iam.Role(
            self,
            "PipelineNotificationLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for pipeline notification Lambda.",
        )

        notification_lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        )
        self._add_vpc_access_policy_if_needed(notification_lambda_role, vpc)

        notification_lambda = _lambda.Function(
            self,
            "PipelineNotificationFunction",
            function_name="pipeline-notification-handler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/notification_handler")
            ),
            role=notification_lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "DISCORD_WEBHOOK_URL": discord_webhook_url,
            },
            **lambda_network_config,
        )

        alerts_topic.add_subscription(
            subscriptions.LambdaSubscription(notification_lambda)
        )

        monitored_lambda_names = [
            "hn-bronze-ingestion",
            "normalize-hn-silver",
            "normalize-x-silver",
            "build-hn-gold",
            "build-x-gold",
            "gold-to-postgres-loader",
        ]

        for function_name in monitored_lambda_names:
            error_metric = cloudwatch.Metric(
                namespace="AWS/Lambda",
                metric_name="Errors",
                dimensions_map={
                    "FunctionName": function_name,
                },
                statistic="Sum",
                period=Duration.minutes(5),
            )

            alarm = cloudwatch.Alarm(
                self,
                f"{function_name}-ErrorsAlarm",
                alarm_name=f"{function_name}-errors",
                metric=error_metric,
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )

            alarm.add_alarm_action(
                cloudwatch_actions.SnsAction(alerts_topic)
            )

        CfnOutput(
            self,
            "PipelineAlertsTopicName",
            value=alerts_topic.topic_name,
        )

        CfnOutput(
            self,
            "NotificationLambdaName",
            value=notification_lambda.function_name,
        )

    def _lambda_network_config(
        self,
        vpc: ec2.IVpc | None,
        lambda_security_group: ec2.ISecurityGroup | None,
    ) -> dict:
        if (vpc is None) != (lambda_security_group is None):
            raise ValueError(
                "vpc and lambda_security_group must be provided together."
            )
        if vpc is None or lambda_security_group is None:
            return {}
        return {
            "vpc": vpc,
            "vpc_subnets": ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            "security_groups": [lambda_security_group],
        }

    def _add_vpc_access_policy_if_needed(
        self, role: iam.Role, vpc: ec2.IVpc | None
    ) -> None:
        if vpc is None:
            return
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole"
            )
        )
