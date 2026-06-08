import datetime as dt
import os


def lambda_handler(event, context):
    data_date = event.get("data_date") if isinstance(event, dict) else None
    ingest_date = event.get("ingest_date") if isinstance(event, dict) else None

    return {
        "source": "hacker-news",
        "layer": "silver",
        "status": "placeholder",
        "data_date": data_date,
        "ingest_date": ingest_date,
        "bucket": os.getenv("DATA_LAKE_BUCKET"),
        "bronze_prefix": os.getenv("BRONZE_HN_PREFIX", "bronze/hacker-news"),
        "silver_prefix": os.getenv("SILVER_PREFIX", "silver"),
        "processed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "message": "HN silver normalization implementation is assigned to Student 2.",
        "request_id": getattr(context, "aws_request_id", None),
    }
