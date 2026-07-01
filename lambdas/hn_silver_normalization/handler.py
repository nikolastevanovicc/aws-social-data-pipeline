import datetime as dt
import os
import json
import boto3
import html
import re
import uuid
from botocore.exceptions import ClientError
import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

HN_ITEM_TYPES = ("story", "ask", "comment", "job", "poll")

PLATFORM_HACKER_NEWS = "HackerNews"

UUID_NAMESPACE = uuid.UUID("8f0f9f6b-4c3c-4f4a-9d2a-6c4c8f1f3b21")

s3_client = boto3.client("s3")

def utc_today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def resolve_hn_processing_options(event: dict) -> dict:
    event = event if isinstance(event, dict) else {}

    data_date = event.get("data_date")
    if not data_date:
        data_date = utc_today()

    ingest_date = event.get("ingest_date")
    if not ingest_date:
        ingest_date = data_date

    return {
        "bucket": event.get("bucket") or os.getenv("DATA_LAKE_BUCKET"),
        "bronze_prefix": event.get("bronze_prefix")
        or os.getenv("BRONZE_HN_PREFIX")
        or "bronze/hacker-news",
        "silver_prefix": event.get("silver_prefix")
        or os.getenv("SILVER_PREFIX")
        or "silver",
        "data_date": data_date,
        "ingest_date": ingest_date        
    }


def build_hn_bronze_base_prefix(
    bronze_prefix: str,
    ingest_date: str,
    data_date: str,
) -> str:
    bronze_prefix = bronze_prefix.rstrip("/")

    return (
        f"{bronze_prefix}/"
        f"ingest_date={ingest_date}/"
        f"data_date={data_date}"
    )


def build_hn_bronze_item_key(
    bronze_prefix: str,
    ingest_date: str,
    data_date: str,
    item_type: str,
) -> str:
    base_prefix = build_hn_bronze_base_prefix(
        bronze_prefix=bronze_prefix,
        ingest_date=ingest_date,
        data_date=data_date,
    )

    return f"{base_prefix}/{item_type}/part-000.json"


def build_hn_bronze_item_keys(
    bronze_prefix: str,
    ingest_date: str,
    data_date: str,
) -> dict[str, str]:
    return {
        item_type: build_hn_bronze_item_key(
            bronze_prefix=bronze_prefix,
            ingest_date=ingest_date,
            data_date=data_date,
            item_type=item_type,
        )
        for item_type in HN_ITEM_TYPES
    }

def read_json_from_s3(bucket: str, key: str) -> object:
    try:
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
        )

        body = response["Body"].read().decode("utf-8")
        return json.loads(body)

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")

        if error_code in ("NoSuchKey", "404"):
            raise FileNotFoundError(f"Missing S3 object: s3://{bucket}/{key}") from exc

        raise

def read_hn_bronze_items(
    bucket: str,
    bronze_item_keys: dict[str, str],
) -> list[dict]:
    all_items = []

    for item_type, key in bronze_item_keys.items():
        print(f"Reading HN bronze {item_type} items from s3://{bucket}/{key}")

        data = read_json_from_s3(bucket=bucket, key=key)

        if not isinstance(data, list):
            raise ValueError(
                f"Expected list in s3://{bucket}/{key}, got {type(data).__name__}"
            )

        valid_items = []

        for item in data:
            if isinstance(item, dict):
                item["_bronze_item_type"] = item_type
                valid_items.append(item)

        print(
            f"Read {len(data)} records from {item_type}, "
            f"valid dict items={len(valid_items)}"
        )

        all_items.extend(valid_items)

    print(f"Total HN bronze items read: {len(all_items)}")
    return all_items

def clean_html(value: object) -> str | None:
    if value is None:
        return None

    text = str(value)

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    cleaned = text.strip()

    return cleaned if cleaned else None


def normalize_hn_timestamp(value: object) -> tuple[str | None, str | None, str | None, str | None]:
    if value is None:
        return None, None, None, None

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None, None, None, None

    created_at = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)

    return (
        created_at.isoformat().replace("+00:00", "Z"),
        f"{created_at.year:04d}",
        f"{created_at.month:02d}",
        f"{created_at.day:02d}",
    )


def stable_uuid(*parts: object) -> str:
    normalized_parts = ["" if part is None else str(part) for part in parts]
    raw_value = "|".join(normalized_parts)

    return str(uuid.uuid5(UUID_NAMESPACE, raw_value))


def infer_hn_post_type(item: dict) -> str:
    bronze_item_type = item.get("_bronze_item_type")

    if bronze_item_type in HN_ITEM_TYPES:
        return str(bronze_item_type)

    tags = item.get("_tags", [])

    if isinstance(tags, list):
        if "comment" in tags:
            return "comment"
        if "job" in tags:
            return "job"
        if "poll" in tags:
            return "poll"
        if "ask_hn" in tags:
            return "ask"
        if "story" in tags:
            return "story"

    return "unknown"

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def normalize_hn_users(
    items: list[dict],
    data_date: str,
    ingest_date: str,
    silver_processed_at_utc: str,
) -> list[dict]:
    users_by_username = {}

    for item in items:
        username = item.get("author")

        if not username:
            continue

        username = str(username).strip()

        if not username:
            continue

        user_key = username.lower()

        if user_key in users_by_username:
            continue

        users_by_username[user_key] = {
            "user_id": stable_uuid(PLATFORM_HACKER_NEWS, username),
            "platform": PLATFORM_HACKER_NEWS,
            "source_user_id": username,
            "username": username,
            "display_name": None,
            "karma_score": None,
            "followers_count": None,
            "following_count": None,
            "is_verified": None,
            "user_created_at_utc": None,
            "data_date": data_date,
            "ingest_date": ingest_date,
            "silver_processed_at_utc": silver_processed_at_utc,
        }

    users = list(users_by_username.values())
    print(f"Normalized HN users: {len(users)}")
    return users

def normalize_hn_posts(
    items: list[dict],
    data_date: str,
    ingest_date: str,
    silver_processed_at_utc: str,
) -> list[dict]:
    posts_by_source_id = {}

    for item in items:
        source_post_id = item.get("objectID")

        if not source_post_id:
            continue

        source_post_id = str(source_post_id).strip()

        if not source_post_id:
            continue

        if source_post_id in posts_by_source_id:
            continue

        author_username = item.get("author")
        if author_username:
            author_username = str(author_username).strip()
        else:
            author_username = None

        author_user_id = (
            stable_uuid(PLATFORM_HACKER_NEWS, author_username)
            if author_username
            else None
        )

        created_at_utc, year, month, day = normalize_hn_timestamp(
            item.get("created_at_i")
        )

        post_type = infer_hn_post_type(item)

        if post_type == "comment":
            title = clean_html(item.get("story_title"))
            content_text = clean_html(item.get("comment_text"))
        else:
            title = clean_html(item.get("title"))
            content_text = clean_html(item.get("story_text"))

        score = item.get("points")
        try:
            score = int(score) if score is not None else None
        except (TypeError, ValueError):
            score = None

        posts_by_source_id[source_post_id] = {
            "post_id": stable_uuid(PLATFORM_HACKER_NEWS, source_post_id),
            "platform": PLATFORM_HACKER_NEWS,
            "source_post_id": source_post_id,
            "author_user_id": author_user_id,
            "author_username": author_username,
            "post_type": post_type,
            "title": title,
            "content_text": content_text,
            "url": item.get("url"),
            "score": score,
            "like_count": None,
            "retweet_count": None,
            "reply_count": None,
            "quote_count": None,
            "lang": None,
            "source": None,
            "created_at_utc": created_at_utc,
            "year": year,
            "month": month,
            "day": day,
            "data_date": data_date,
            "ingest_date": ingest_date,
            "silver_processed_at_utc": silver_processed_at_utc,
        }

    posts = list(posts_by_source_id.values())
    print(f"Normalized HN posts: {len(posts)}")
    return posts

def infer_hn_tag_type(tag: str) -> str:
    if tag in HN_ITEM_TYPES or tag == "ask_hn":
        return "post_type"

    if tag.startswith("author_"):
        return "author"

    if tag.startswith("story_"):
        return "story_reference"

    if tag.startswith("comment_"):
        return "comment_reference"

    if tag.startswith("poll_"):
        return "poll_reference"

    if tag.startswith("job_"):
        return "job_reference"

    return "hn_tag"

def normalize_hn_tags(
    items: list[dict],
    data_date: str,
    ingest_date: str,
    silver_processed_at_utc: str,
) -> list[dict]:
    tags_by_key = {}

    for item in items:
        source_post_id = item.get("objectID")

        if not source_post_id:
            continue

        source_post_id = str(source_post_id).strip()

        if not source_post_id:
            continue

        post_id = stable_uuid(PLATFORM_HACKER_NEWS, source_post_id)

        created_at_utc, year, month, day = normalize_hn_timestamp(
            item.get("created_at_i")
        )

        raw_tags = item.get("_tags", [])

        if not isinstance(raw_tags, list):
            continue

        for tag in raw_tags:
            if tag is None:
                continue

            tag_value = str(tag).strip()

            if not tag_value:
                continue

            tag_type = infer_hn_tag_type(tag_value)

            tag_key = (
                post_id,
                tag_value.lower(),
                tag_type,
            )

            if tag_key in tags_by_key:
                continue

            tags_by_key[tag_key] = {
                "post_id": post_id,
                "platform": PLATFORM_HACKER_NEWS,
                "tag": tag_value,
                "tag_type": tag_type,
                "created_at_utc": created_at_utc,
                "year": year,
                "month": month,
                "day": day,
                "data_date": data_date,
                "ingest_date": ingest_date,
                "silver_processed_at_utc": silver_processed_at_utc,
            }

    tags = list(tags_by_key.values())
    print(f"Normalized HN post_tags: {len(tags)}")
    return tags

def normalize_hn_relations(
    items: list[dict],
    data_date: str,
    ingest_date: str,
    silver_processed_at_utc: str,
) -> list[dict]:
    relations_by_key = {}

    for item in items:
        source_post_id = item.get("objectID")

        if not source_post_id:
            continue

        source_post_id = str(source_post_id).strip()

        if not source_post_id:
            continue

        post_id = stable_uuid(PLATFORM_HACKER_NEWS, source_post_id)

        created_at_utc, year, month, day = normalize_hn_timestamp(
            item.get("created_at_i")
        )

        possible_relations = [
            ("parent", item.get("parent_id")),
            ("story", item.get("story_id")),
        ]

        for relation_type, related_source_post_id in possible_relations:
            if related_source_post_id is None or related_source_post_id == "":
                continue

            related_source_post_id = str(related_source_post_id).strip()

            if not related_source_post_id:
                continue

            relation_key = (
                post_id,
                related_source_post_id,
                relation_type,
            )

            if relation_key in relations_by_key:
                continue

            relations_by_key[relation_key] = {
                "post_id": post_id,
                "platform": PLATFORM_HACKER_NEWS,
                "related_source_post_id": related_source_post_id,
                "relation_type": relation_type,
                "created_at_utc": created_at_utc,
                "year": year,
                "month": month,
                "day": day,
                "data_date": data_date,
                "ingest_date": ingest_date,
                "silver_processed_at_utc": silver_processed_at_utc,
            }

    relations = list(relations_by_key.values())
    print(f"Normalized HN post_relations: {len(relations)}")
    return relations

def calculate_data_quality_score(rows: list[dict]) -> dict:
    if not rows:
        return {
            "row_count": 0,
            "column_count": 0,
            "non_null_cell_count": 0,
            "total_cell_count": 0,
            "data_quality_score": 0.0,
        }

    columns = {key for row in rows if isinstance(row, dict) for key in row}

    row_count = len(rows)
    column_count = len(columns)
    total_cell_count = row_count * column_count

    non_null_cell_count = sum(
        1
        for row in rows
        for column in columns
        if isinstance(row, dict)
        and row.get(column) is not None
        and row.get(column) != ""
    )

    data_quality_score = (
        round(non_null_cell_count / total_cell_count * 100, 2)
        if total_cell_count
        else 0.0
    )

    return {
        "row_count": row_count,
        "column_count": column_count,
        "non_null_cell_count": non_null_cell_count,
        "total_cell_count": total_cell_count,
        "data_quality_score": data_quality_score,
    }


def build_hn_data_quality_report_rows(
    normalized_tables: dict[str, list[dict]],
    data_date: str,
    ingest_date: str,
    silver_processed_at_utc: str,
) -> list[dict]:
    report_rows = []

    for table_name in ("users", "posts", "post_tags", "post_relations"):
        quality = calculate_data_quality_score(
            normalized_tables.get(table_name, [])
        )

        report_rows.append(
            {
                "table_name": table_name,
                "platform": PLATFORM_HACKER_NEWS,
                "data_date": data_date,
                "ingest_date": ingest_date,
                "row_count": quality["row_count"],
                "column_count": quality["column_count"],
                "non_null_cell_count": quality["non_null_cell_count"],
                "total_cell_count": quality["total_cell_count"],
                "data_quality_score": quality["data_quality_score"],
                "silver_processed_at_utc": silver_processed_at_utc,
            }
        )

    return report_rows

def dataframe_to_parquet_bytes(
    dataframe: pd.DataFrame,
) -> bytes:

    buffer = io.BytesIO()

    table = pa.Table.from_pandas(
        dataframe,
        preserve_index=False,
    )

    pq.write_table(
        table,
        buffer,
        compression="snappy",
    )

    buffer.seek(0)

    return buffer.read()

def build_partition_path(row: dict, partition_cols: list[str]) -> str:
    partition_parts = []

    for column in partition_cols:
        value = row.get(column)

        if value is None or value == "":
            value = "unknown"

        partition_parts.append(f"{column}={value}")

    return "/".join(partition_parts)

def write_parquet_table_to_s3(
    bucket: str,
    silver_prefix: str,
    table_name: str,
    rows: list[dict],
    partition_cols: list[str],
) -> dict:
    silver_prefix = silver_prefix.strip("/")
    rows = rows or []

    base_key = f"{silver_prefix}/{table_name}" if silver_prefix else table_name

    if not rows:
        print(f"Skipping empty table: {table_name}")
        return {
            "table_name": table_name,
            "row_count": 0,
            "written": False,
            "partitions_written": 0,
        }

    partitions: dict[str, list[dict]] = {}

    for row in rows:
        partition_path = build_partition_path(
            row=row,
            partition_cols=partition_cols,
        )

        partitions.setdefault(partition_path, []).append(row)

    written_keys = []

    for partition_path, partition_rows in partitions.items():
        dataframe = pd.DataFrame(partition_rows)

        parquet_bytes = dataframe_to_parquet_bytes(dataframe)

        key = f"{base_key}/{partition_path}/part-000.parquet"

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=parquet_bytes,
            ContentType="application/octet-stream",
        )

        print(
            f"Wrote {len(partition_rows)} rows to "
            f"s3://{bucket}/{key}"
        )

        written_keys.append(key)

    return {
        "table_name": table_name,
        "row_count": len(rows),
        "written": True,
        "partitions_written": len(written_keys),
        "written_keys": written_keys,
    }

def write_hn_silver_tables(
    bucket: str,
    silver_prefix: str,
    normalized_tables: dict[str, list[dict]],
) -> dict:
    partition_columns = {
        "users": ["platform", "data_date"],
        "posts": ["platform", "year", "month", "day"],
        "post_tags": ["platform", "year", "month", "day"],
        "post_relations": ["platform", "year", "month", "day"],
        "data_quality_report": ["platform", "data_date"],
    }

    write_results = {}

    for table_name, partition_cols in partition_columns.items():
        write_results[table_name] = write_parquet_table_to_s3(
            bucket=bucket,
            silver_prefix=silver_prefix,
            table_name=table_name,
            rows=normalized_tables.get(table_name, []),
            partition_cols=partition_cols,
        )

    return write_results

def build_hn_bronze_metadata_key(
    bronze_prefix: str,
    ingest_date: str,
    data_date: str,
) -> str:
    base_prefix = build_hn_bronze_base_prefix(
        bronze_prefix=bronze_prefix,
        ingest_date=ingest_date,
        data_date=data_date,
    )

    return f"{base_prefix}/metadata/metadata.json"


def lambda_handler(event, context):
    options = resolve_hn_processing_options(event)

    bucket = options["bucket"]
    if not bucket:
        raise ValueError("DATA_LAKE_BUCKET is required")

    bronze_item_keys = build_hn_bronze_item_keys(
        bronze_prefix=options["bronze_prefix"],
        ingest_date=options["ingest_date"],
        data_date=options["data_date"],
    )

    bronze_metadata_key = build_hn_bronze_metadata_key(
        bronze_prefix=options["bronze_prefix"],
        ingest_date=options["ingest_date"],
        data_date=options["data_date"],
    )

    bronze_items = read_hn_bronze_items(
        bucket=bucket,
        bronze_item_keys=bronze_item_keys,
    )

    silver_processed_at_utc = utc_now_iso()

    users = normalize_hn_users(
        items=bronze_items,
        data_date=options["data_date"],
        ingest_date=options["ingest_date"],
        silver_processed_at_utc=silver_processed_at_utc,
    )

    posts = normalize_hn_posts(
        items=bronze_items,
        data_date=options["data_date"],
        ingest_date=options["ingest_date"],
        silver_processed_at_utc=silver_processed_at_utc,
    )

    post_tags = normalize_hn_tags(
        items=bronze_items,
        data_date=options["data_date"],
        ingest_date=options["ingest_date"],
        silver_processed_at_utc=silver_processed_at_utc,
    )

    post_relations = normalize_hn_relations(
        items=bronze_items,
        data_date=options["data_date"],
        ingest_date=options["ingest_date"],
        silver_processed_at_utc=silver_processed_at_utc,
    )

    normalized_tables = {
        "users": users,
        "posts": posts,
        "post_tags": post_tags,
        "post_relations": post_relations,
    }

    data_quality_report = build_hn_data_quality_report_rows(
        normalized_tables=normalized_tables,
        data_date=options["data_date"],
        ingest_date=options["ingest_date"],
        silver_processed_at_utc=silver_processed_at_utc,
    )

    normalized_tables["data_quality_report"] = data_quality_report
    
    write_results = write_hn_silver_tables(
        bucket=bucket,
        silver_prefix=options["silver_prefix"],
        normalized_tables=normalized_tables,
    )

    return {
    "source": "hacker-news",
    "layer": "silver",
    "status": "success",
    "bucket": bucket,
    "bronze_prefix": options["bronze_prefix"],
    "silver_prefix": options["silver_prefix"],
    "data_date": options["data_date"],
    "ingest_date": options["ingest_date"],
    "total_bronze_items_read": len(bronze_items),
    "tables": write_results,
    "data_quality_report": data_quality_report,
    "silver_processed_at_utc": silver_processed_at_utc,
    "request_id": getattr(context, "aws_request_id", None),
    }
