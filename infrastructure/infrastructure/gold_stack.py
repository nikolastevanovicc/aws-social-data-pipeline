import os
import shutil
import subprocess
import sys
from pathlib import Path

import jsii
from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    Duration,
    ILocalBundling,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
)
from constructs import Construct


@jsii.implements(ILocalBundling)
class _PythonRequirementsBundler:
    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def try_bundle(
        self,
        output_dir,
        *,
        image,
        entrypoint=None,
        command=None,
        volumes=None,
        volumesFrom=None,
        environment=None,
        workingDirectory=None,
        user=None,
        local=None,
        outputType=None,
        securityOpt=None,
        network=None,
        bundlingFileAccess=None,
        platform=None,
    ):
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-compile",
                "-r",
                str(self.source_path / "requirements.txt"),
                "-t",
                output_dir,
            ],
            env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        )
        shutil.copytree(
            self.source_path,
            output_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        return True


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

        gold_to_postgres_loader_path = (
            Path(__file__).resolve().parents[2] / "lambdas/gold_to_postgres_loader"
        )

        def context_or_env(context_key: str, env_key: str, default: str) -> str:
            return str(
                self.node.try_get_context(context_key) or os.getenv(env_key, default)
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

        gold_to_postgres_loader_lambda = _lambda.Function(
            self,
            "GoldToPostgresLoaderFunction",
            function_name="gold-to-postgres-loader",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(gold_to_postgres_loader_path),
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install --no-compile -r requirements.txt "
                        "-t /asset-output && cp -au . /asset-output",
                    ],
                    local=_PythonRequirementsBundler(gold_to_postgres_loader_path),
                ),
            ),
            layers=[aws_sdk_pandas_layer],
            timeout=Duration.minutes(5),
            memory_size=1024,
            environment={
                "DATA_LAKE_BUCKET": data_lake_bucket.bucket_name,
                "GOLD_PREFIX": "gold",
                "POSTGRES_HOST": context_or_env(
                    "postgres_host", "POSTGRES_HOST", ""
                ),
                "POSTGRES_PORT": context_or_env(
                    "postgres_port", "POSTGRES_PORT", "5432"
                ),
                "POSTGRES_DATABASE": context_or_env(
                    "postgres_database",
                    "POSTGRES_DATABASE",
                    "social_analytics",
                ),
                "POSTGRES_USER": context_or_env(
                    "postgres_user", "POSTGRES_USER", "superset"
                ),
                "POSTGRES_PASSWORD": context_or_env(
                    "postgres_password", "POSTGRES_PASSWORD", ""
                ),
            },
        )
        data_lake_bucket.grant_read(gold_to_postgres_loader_lambda, "gold/*")

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
        CfnOutput(
            self,
            "GoldToPostgresLoaderFunctionName",
            value=gold_to_postgres_loader_lambda.function_name,
        )
