from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
)
from constructs import Construct


class BronzeStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        data_lake_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_role = iam.Role(
            self,
            "HackerNewsIngestionLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for Hacker News bronze ingestion Lambda.",
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:*"],
            )
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*:*"
                ],
            )
        )
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[data_lake_bucket.arn_for_objects("bronze/*")],
            )
        )

        hn_ingestion_lambda = _lambda.Function(
            self,
            "HackerNewsIngestionFunction",
            function_name="hn-bronze-ingestion",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/hn_ingestion")
            ),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "DATA_LAKE_BUCKET": data_lake_bucket.bucket_name,
                "HN_BRONZE_PREFIX": "bronze/hacker-news",
            },
        )

        events.Rule(
            self,
            "HackerNewsDailySchedule",
            description="Runs Hacker News bronze ingestion every day at 02:00 UTC.",
            schedule=events.Schedule.cron(minute="0", hour="2"),
            targets=[targets.LambdaFunction(hn_ingestion_lambda)],
        )

        CfnOutput(
            self,
            "HackerNewsLambdaName",
            value=hn_ingestion_lambda.function_name,
        )
