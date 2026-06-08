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


class SilverStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        data_lake_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        silver_lambda_role = iam.Role(
            self,
            "SilverNormalizationLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for silver normalization Lambdas.",
        )

        silver_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup"],
                resources=[f"arn:aws:logs:{self.region}:{self.account}:*"],
            )
        )
        silver_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*:*"
                ],
            )
        )
        silver_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[data_lake_bucket.bucket_arn],
                conditions={
                    "StringLike": {
                        "s3:prefix": [
                            "bronze/*",
                            "silver/*",
                        ]
                    }
                },
            )
        )
        silver_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[data_lake_bucket.arn_for_objects("bronze/*")],
            )
        )
        silver_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[data_lake_bucket.arn_for_objects("silver/*")],
            )
        )

        silver_environment = {
            "DATA_LAKE_BUCKET": data_lake_bucket.bucket_name,
            "BRONZE_HN_PREFIX": "bronze/hacker-news",
            "BRONZE_X_PREFIX": "bronze/x",
            "SILVER_PREFIX": "silver",
            "DEFAULT_X_DATASET_NAME": "x-synthetic-seed",
        }

        hn_silver_lambda = _lambda.Function(
            self,
            "HackerNewsSilverNormalizationFunction",
            function_name="normalize-hn-silver",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/hn_silver_normalization")
            ),
            role=silver_lambda_role,
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment=silver_environment,
        )

        x_silver_lambda = _lambda.Function(
            self,
            "XSilverNormalizationFunction",
            function_name="normalize-x-silver",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/x_silver_normalization")
            ),
            role=silver_lambda_role,
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment=silver_environment,
        )

        CfnOutput(
            self,
            "NormalizeHnSilverLambdaName",
            value=hn_silver_lambda.function_name,
        )
        CfnOutput(
            self,
            "NormalizeXSilverLambdaName",
            value=x_silver_lambda.function_name,
        )
