import datetime as dt
import os
import json
import urllib.request
import urllib.error
import urllib.parse
import boto3
import time

HN_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_SEARCH_API_BASE_URL = "https://hn.algolia.com/api/v1"

s3_client = boto3.client("s3")
def _resolve_data_date(event: dict) -> str:
    if isinstance(event, dict) and event.get("date"):
        try:
            parsed_date = dt.date.fromisoformat(str(event["date"]))
            return parsed_date.isoformat()
        except ValueError as exc:
            raise ValueError("Event field 'date' must be in YYYY-MM-DD format.") from exc

    previous_day = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    return previous_day.isoformat()

def _date_to_utc_range(data_date: str) -> tuple[int, int]:
    parsed_date = dt.date.fromisoformat(data_date)

    start_datetime = dt.datetime.combine(
        parsed_date,
        dt.time.min,
        tzinfo=dt.timezone.utc,
    )

    end_datetime = start_datetime + dt.timedelta(days=1)

    return int(start_datetime.timestamp()), int(end_datetime.timestamp())


def _http_get_json(
    url: str,
    max_retries: int = 3,
) -> dict | int | list | None:

    for attempt in range(max_retries):

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)

        except urllib.error.HTTPError as exc:
            print(
                f"HTTP error while requesting {url} "
                f"(attempt {attempt + 1}/{max_retries}): {exc}"
            )

        except urllib.error.URLError as exc:
            print(
                f"URL error while requesting {url} "
                f"(attempt {attempt + 1}/{max_retries}): {exc}"
            )

        except Exception as exc:
            print(
                f"Unexpected error while requesting {url} "
                f"(attempt {attempt + 1}/{max_retries}): {exc}"
            )

        if attempt < max_retries - 1:
            time.sleep(1)

    print(f"Giving up after {max_retries} attempts: {url}")
    return None
    

def fetch_max_item() -> int:
    url = f"{HN_API_BASE_URL}/maxitem.json"

    result = _http_get_json(url,max_retries= 3)

    if not isinstance(result, int):
        raise RuntimeError("Failed to fetch Hacker News max item id.")

    return result

def fetch_item(item_id: int) -> dict | None:
    url = f"{HN_API_BASE_URL}/item/{item_id}.json"

    result = _http_get_json(url,max_retries= 3)

    if not isinstance(result, dict):
        return None

    return result

def collect_items_for_day(start_ts: int, end_ts: int, max_pages_per_window: int = 5) -> list[dict]:
    collected_items = []
    seen_object_ids = set()

    window_size_seconds = 60 * 60  # 1 sat
    window_start = start_ts

    print("Starting HN Search API collection by hourly windows.")
    print(f"Target timestamp range: start_ts={start_ts}, end_ts={end_ts}")
    print(f"Max pages per window: {max_pages_per_window}")

    while window_start < end_ts:
        window_end = min(window_start + window_size_seconds, end_ts)

        print(f"Collecting window: window_start={window_start}, window_end={window_end}")

        page = 0

        while page < max_pages_per_window:
            query_params = {
                "tags": "(story,comment,poll,ask_hn,job)",
                "numericFilters": f"created_at_i>={window_start},created_at_i<{window_end}",
                "hitsPerPage": "1000",
                "page": str(page),
            }

            url = f"{HN_SEARCH_API_BASE_URL}/search_by_date?{urllib.parse.urlencode(query_params)}"

            response = _http_get_json(url,max_retries= 3)

            if not isinstance(response, dict):
                print(f"Stopping window: invalid response for page={page}")
                break

            hits = response.get("hits", [])

            if not isinstance(hits, list):
                print(f"Stopping window: hits field is not a list for page={page}")
                break

            print(
                f"Fetched window_start={window_start}, window_end={window_end}, "
                f"page={page}, hits={len(hits)}"
            )

            if len(hits) == 0:
                break

            for hit in hits:
                if not isinstance(hit, dict):
                    continue

                object_id = hit.get("objectID")

                if object_id and object_id in seen_object_ids:
                    continue

                if object_id:
                    seen_object_ids.add(object_id)

                collected_items.append(hit)

            nb_pages = response.get("nbPages")
            print(f"API reports nbPages={nb_pages} for window_start={window_start}")

            if isinstance(nb_pages, int) and page >= nb_pages - 1:
                break

            page += 1

        window_start = window_end

    print(f"Collected {len(collected_items)} raw HN Search API items.")
    return collected_items

def group_items_by_type(items: list[dict]) -> dict[str, list[dict]]:
    grouped_items = {
        "story": [],
        "ask": [],
        "comment": [],
        "job": [],
        "poll": [],
    }

    for item in items:
        tags = item.get("_tags", [])

        if not isinstance(tags, list):
            continue

        if "comment" in tags:
            grouped_items["comment"].append(item)
        elif "job" in tags:
            grouped_items["job"].append(item)
        elif "poll" in tags:
            grouped_items["poll"].append(item)
        elif "ask_hn" in tags:
            grouped_items["ask"].append(item)
        elif "story" in tags:
            grouped_items["story"].append(item)

    return grouped_items

def write_json_to_s3(bucket: str, key: str, data: object) -> None:
    body = json.dumps(data, ensure_ascii=False, indent=2)

    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json",
    )

    print(f"Wrote s3://{bucket}/{key}")

def write_grouped_items_to_s3(
    bucket: str,
    prefix: str,
    ingest_date: str,
    data_date: str,
    grouped_items: dict[str, list[dict]],
) -> dict[str, str]:
    written_keys = {}

    base_key = f"{prefix}/ingest_date={ingest_date}/data_date={data_date}"

    for item_type, items in grouped_items.items():
        key = f"{base_key}/{item_type}/part-000.json"

        write_json_to_s3(
            bucket=bucket,
            key=key,
            data=items,
        )

        written_keys[item_type] = key

    return written_keys

def build_metadata(
    data_date: str,
    prefix: str,
    ingest_date: str,
    start_ts: int,
    end_ts: int,
    counts: dict[str, int],
    written_keys: dict[str, str],
    total_collected_count: int,
) -> dict:
    return {
        "source": "hacker-news",
        "api": "hn-search-api",
        "status": "success",
        "data_date": data_date,
        "ingest_date": ingest_date,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "counts": counts,
        "total_collected_count": total_collected_count,
        "written_keys": written_keys,
        "base_prefix": f"{prefix}/ingest_date={ingest_date}/data_date={data_date}",
    }

def lambda_handler(event, context):
    data_date = _resolve_data_date(event if isinstance(event, dict) else {})
    start_ts, end_ts = _date_to_utc_range(data_date)

    collected_items = collect_items_for_day(start_ts, end_ts, max_pages_per_window=5)
    grouped_items = group_items_by_type(collected_items)
    counts = {item_type: len(items) for item_type, items in grouped_items.items()}
    
    ingest_date = dt.datetime.now(dt.timezone.utc).date().isoformat()
    bucket = os.getenv("DATA_LAKE_BUCKET", "")
    if not bucket:
        raise RuntimeError("DATA_LAKE_BUCKET environment variable is not set.")
    prefix = os.getenv("HN_BRONZE_PREFIX", "bronze/hacker-news")
    written_keys = write_grouped_items_to_s3(
        bucket=bucket,
        prefix=prefix,
        ingest_date=ingest_date,
        data_date=data_date,
        grouped_items=grouped_items,
    )

    metadata = build_metadata(
        data_date=data_date,
        prefix=prefix,
        ingest_date=ingest_date,
        start_ts=start_ts,
        end_ts=end_ts,
        counts=counts,
        written_keys=written_keys,
        total_collected_count=len(collected_items),
    )

    metadata_key = f"{prefix}/ingest_date={ingest_date}/data_date={data_date}/metadata/metadata.json"

    write_json_to_s3(
        bucket=bucket,
        key=metadata_key,
        data=metadata,
    )

    return {
        "source": "hacker-news",
        "status": "success",
        "data_date": data_date,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "ingest_date": ingest_date,
        "bucket": bucket,
        "prefix": prefix,
        "total_collected_count": len(collected_items),
        "counts": counts,
        "written_keys": written_keys,
        "metadata_key": metadata_key,
        "request_id": getattr(context, "aws_request_id", None),
    }