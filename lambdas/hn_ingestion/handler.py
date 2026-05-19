import datetime as dt
import os


def _resolve_data_date(event: dict) -> str:
    if isinstance(event, dict) and event.get("date"):
        return str(event["date"])
    previous_day = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    return previous_day.isoformat()


def lambda_handler(event, context):
    data_date = _resolve_data_date(event if isinstance(event, dict) else {})
    ingest_date = dt.datetime.now(dt.timezone.utc).date().isoformat()
    bucket = os.getenv("DATA_LAKE_BUCKET", "")
    prefix = os.getenv("HN_BRONZE_PREFIX", "bronze/hacker-news")

    # Placeholder for Student 2 implementation:
    # fetch HN raw items, split by type, and write files under the bronze prefix.
    return {
        "source": "hacker-news",
        "status": "placeholder",
        "data_date": data_date,
        "ingest_date": ingest_date,
        "bucket": bucket,
        "prefix": prefix,
        "counts": {"story": 0, "ask": 0, "comment": 0, "job": 0, "poll": 0},
        "message": "Infrastructure baseline is ready. Implement ingestion logic next.",
        "request_id": getattr(context, "aws_request_id", None),
    }
