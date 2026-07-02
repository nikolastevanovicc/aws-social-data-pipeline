#!/usr/bin/env python3
import aws_cdk as cdk

from infrastructure.analytics_stack import AnalyticsStack
from infrastructure.bronze_stack import BronzeStack
from infrastructure.data_lake_stack import DataLakeStack
from infrastructure.gold_stack import GoldStack
from infrastructure.network_stack import NetworkStack
from infrastructure.silver_stack import SilverStack
from infrastructure.notification_stack import NotificationStack

app = cdk.App()
data_lake_stack = DataLakeStack(app, "DataLakeStack")
network_stack = NetworkStack(
    app,
    "NetworkStack",
    analytics_allowed_cidr=(
        app.node.try_get_context("analytics_allowed_cidr") or "127.0.0.1/32"
    ),
)
analytics_stack = AnalyticsStack(
    app,
    "AnalyticsStack",
    vpc=network_stack.vpc,
    analytics_security_group=network_stack.analytics_security_group,
)
BronzeStack(
    app,
    "BronzeStack",
    data_lake_bucket=data_lake_stack.data_lake_bucket,
    vpc=network_stack.vpc,
    lambda_security_group=network_stack.pipeline_lambda_security_group,
)
SilverStack(
    app,
    "SilverStack",
    data_lake_bucket=data_lake_stack.data_lake_bucket,
    vpc=network_stack.vpc,
    lambda_security_group=network_stack.pipeline_lambda_security_group,
)
GoldStack(
    app,
    "GoldStack",
    data_lake_bucket=data_lake_stack.data_lake_bucket,
    vpc=network_stack.vpc,
    lambda_security_group=network_stack.pipeline_lambda_security_group,
    postgres_host=analytics_stack.postgres_private_host,
)
NotificationStack(
    app,
    "NotificationStack",
    vpc=network_stack.vpc,
    lambda_security_group=network_stack.pipeline_lambda_security_group,
)
app.synth()
