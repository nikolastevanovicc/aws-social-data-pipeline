#!/usr/bin/env python3
import aws_cdk as cdk

from infrastructure.analytics_stack import AnalyticsStack
from infrastructure.bronze_stack import BronzeStack
from infrastructure.data_lake_stack import DataLakeStack
from infrastructure.gold_stack import GoldStack
from infrastructure.silver_stack import SilverStack
from infrastructure.notification_stack import NotificationStack

app = cdk.App()
data_lake_stack = DataLakeStack(app, "DataLakeStack")
analytics_stack=AnalyticsStack(app, "AnalyticsStack")
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
    analytics_vpc=analytics_stack.vpc,
    analytics_security_group=analytics_stack.analytics_security_group,
    postgres_host=analytics_stack.analytics_instance.instance_private_ip,
)
NotificationStack(app, "NotificationStack")
app.synth()
