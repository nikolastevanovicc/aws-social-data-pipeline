from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
)
from constructs import Construct


class NotificationStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        discord_webhook_url = self.node.try_get_context("discord_webhook_url")

        if not discord_webhook_url:
            raise ValueError(
                "Missing CDK context value: discord_webhook_url"
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