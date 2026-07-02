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
AnalyticsStack(app, "AnalyticsStack")
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
