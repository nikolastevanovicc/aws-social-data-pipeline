from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_ec2 as ec2,
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
        vpc: ec2.IVpc | None = None,
        lambda_security_group: ec2.ISecurityGroup | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        lambda_network_config = self._lambda_network_config(
            vpc, lambda_security_group
        )

        silver_lambda_role = iam.Role(
            self,
            "SilverNormalizationLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for silver normalization Lambdas.",
        )
        self._add_vpc_access_policy_if_needed(silver_lambda_role, vpc)

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
        silver_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:DeleteObject"],
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

        aws_sdk_pandas_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "AwsSdkPandasPython312Layer",
            "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:27",
        )

        hn_silver_lambda = _lambda.Function(
            self,
            "HackerNewsSilverNormalizationFunction",
            function_name="normalize-hn-silver",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/hn_silver_normalization")
            ),
            layers=[aws_sdk_pandas_layer],
            role=silver_lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment=silver_environment,
            **lambda_network_config,
        )

        x_silver_lambda = _lambda.Function(
            self,
            "XSilverNormalizationFunction",
            function_name="normalize-x-silver",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).resolve().parents[2] / "lambdas/x_silver_normalization")
            ),
            layers=[aws_sdk_pandas_layer],
            role=silver_lambda_role,
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment=silver_environment,
            **lambda_network_config,
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
