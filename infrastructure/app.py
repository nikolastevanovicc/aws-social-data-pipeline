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
AnalyticsStack(
    app,
    "AnalyticsStack",
    vpc=network_stack.vpc,
    analytics_security_group=network_stack.analytics_security_group,
)
BronzeStack(
    app,
    "BronzeStack",
    data_lake_bucket=data_lake_stack.data_lake_bucket,
)
SilverStack(
    app,
    "SilverStack",
    data_lake_bucket=data_lake_stack.data_lake_bucket,
)
GoldStack(
    app,
    "GoldStack",
    data_lake_bucket=data_lake_stack.data_lake_bucket,
)
NotificationStack(app, "NotificationStack")
app.synth()
