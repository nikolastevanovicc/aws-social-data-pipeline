import datetime as dt
import os


def lambda_handler(event, context):
    ingest_date = event.get("ingest_date") if isinstance(event, dict) else None
    dataset_name = (
        event.get("x_dataset_name")
        if isinstance(event, dict) and event.get("x_dataset_name")
        else os.getenv("DEFAULT_X_DATASET_NAME", "x-synthetic-seed")
    )

    return {
        "source": "x",
        "layer": "silver",
        "status": "placeholder",
        "ingest_date": ingest_date,
        "dataset_name": dataset_name,
        "bucket": os.getenv("DATA_LAKE_BUCKET"),
        "bronze_prefix": os.getenv("BRONZE_X_PREFIX", "bronze/x"),
        "silver_prefix": os.getenv("SILVER_PREFIX", "silver"),
        "processed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "message": "X silver normalization implementation is assigned to Student 3.",
        "request_id": getattr(context, "aws_request_id", None),
    }
