from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
    aws_ec2 as ec2,
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
        vpc: ec2.IVpc | None = None,
        lambda_security_group: ec2.ISecurityGroup | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        lambda_network_config = self._lambda_network_config(
            vpc, lambda_security_group
        )

        lambda_role = iam.Role(
            self,
            "HackerNewsIngestionLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for Hacker News bronze ingestion Lambda.",
        )
        self._add_vpc_access_policy_if_needed(lambda_role, vpc)

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
            **lambda_network_config,
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
