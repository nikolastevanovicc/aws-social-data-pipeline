#!/usr/bin/env python3
import aws_cdk as cdk

from infrastructure.bronze_stack import BronzeStack
from infrastructure.data_lake_stack import DataLakeStack
from infrastructure.silver_stack import SilverStack


app = cdk.App()
data_lake_stack = DataLakeStack(app, "DataLakeStack")
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

app.synth()
