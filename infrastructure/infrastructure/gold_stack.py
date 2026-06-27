from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
)
from constructs import Construct


class GoldStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        data_lake_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        gold_lambda_role = iam.Role(
            self,
            "GoldAggregationLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for gold aggregation Lambdas.",
        )

        gold_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:*"],
            )
        )
        gold_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*:*"
                ],
            )
        )
        gold_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[data_lake_bucket.bucket_arn],
                conditions={
                    "StringLike": {
                        "s3:prefix": [
                            "silver/*",
                            "gold/*",
                        ]
                    }
                },
            )
        )
        gold_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[data_lake_bucket.arn_for_objects("silver/*")],
            )
        )
        gold_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[data_lake_bucket.arn_for_objects("gold/*")],
            )
        )
        gold_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:DeleteObject"],
                resources=[data_lake_bucket.arn_for_objects("gold/*")],
            )
        )

        gold_environment = {
            "DATA_LAKE_BUCKET": data_lake_bucket.bucket_name,
            "SILVER_PREFIX": "silver",
            "GOLD_PREFIX": "gold",
            "HN_GOLD_PREFIX": "gold/hacker-news",
            "X_GOLD_PREFIX": "gold/x",
        }

        aws_sdk_pandas_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "AwsSdkPandasPython312Layer",
            "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:27",
        )

        hn_gold_lambda = _lambda.Function(
            self,
            "HackerNewsGoldAggregationFunction",
            function_name="build-hn-gold",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/hn_gold_aggregation")
            ),
            layers=[aws_sdk_pandas_layer],
            role=gold_lambda_role,
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment=gold_environment,
        )

        x_gold_lambda = _lambda.Function(
            self,
            "XGoldAggregationFunction",
            function_name="build-x-gold",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/x_gold_aggregation")
            ),
            layers=[aws_sdk_pandas_layer],
            role=gold_lambda_role,
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment=gold_environment,
        )

        CfnOutput(
            self,
            "BuildHnGoldLambdaName",
            value=hn_gold_lambda.function_name,
        )
        CfnOutput(
            self,
            "BuildXGoldLambdaName",
            value=x_gold_lambda.function_name,
        )
