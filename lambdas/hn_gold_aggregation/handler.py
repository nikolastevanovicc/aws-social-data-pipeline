import datetime as dt
import os


def lambda_handler(event, context):
    event = event if isinstance(event, dict) else {}

    return {
        "source": "hacker-news",
        "layer": "gold",
        "status": "placeholder",
        "bucket": event.get("bucket") or os.getenv("DATA_LAKE_BUCKET"),
        "silver_prefix": event.get("silver_prefix")
        or os.getenv("SILVER_PREFIX", "silver"),
        "gold_prefix": event.get("gold_prefix")
        or os.getenv("HN_GOLD_PREFIX", "gold/hacker-news"),
        "processed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "message": "HN gold aggregation will run after HN silver outputs are available.",
        "request_id": getattr(context, "aws_request_id", None),
    }
