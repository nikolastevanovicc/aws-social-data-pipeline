import datetime as dt
import os
from collections import defaultdict


HN_PLATFORM = "HackerNews"
HN_ITEM_TYPES = ("story", "ask", "comment", "job", "poll")
HN_SILVER_TABLES = (
    "users",
    "posts",
    "post_tags",
    "post_relations",
    "data_quality_report",
)


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_hn_gold_options(event):
    event = event if isinstance(event, dict) else {}

    return {
        "bucket": event.get("bucket") or os.getenv("DATA_LAKE_BUCKET"),
        "silver_prefix": event.get("silver_prefix")
        or os.getenv("SILVER_PREFIX")
        or "silver",
        "gold_prefix": event.get("gold_prefix")
        or os.getenv("HN_GOLD_PREFIX")
        or "gold/hacker-news",
        "data_date": event.get("data_date"),
        "mode": event.get("mode") or "overwrite_partitions",
    }


def safe_int(value):
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def date_parts(date_value):
    if not isinstance(date_value, str) or not date_value.strip():
        return {"year": None, "month": None, "day": None}

    try:
        parsed = dt.date.fromisoformat(date_value.strip())
    except ValueError:
        return {"year": None, "month": None, "day": None}

    return {
        "year": f"{parsed.year:04d}",
        "month": f"{parsed.month:02d}",
        "day": f"{parsed.day:02d}",
    }


def row_date(row):
    if row.get("data_date"):
        return row["data_date"]

    year = row.get("year")
    month = row.get("month")
    day = row.get("day")
    if year and month and day:
        return f"{year}-{month}-{day}"

    created_at = row.get("created_at_utc")
    if isinstance(created_at, str) and len(created_at) >= 10:
        return created_at[:10]

    return None


def filter_rows_by_data_date(rows, data_date):
    if not data_date:
        return list(rows or [])

    return [row for row in rows or [] if row_date(row) == data_date]


def base_metric_row(platform, date_value, processed_at_utc):
    parts = date_parts(date_value)
    return {
        "date": date_value,
        "platform": platform,
        "year": parts["year"],
        "month": parts["month"],
        "day": parts["day"],
        "gold_processed_at_utc": processed_at_utc,
    }


def build_daily_item_counts(posts, processed_at_utc):
    grouped_counts = defaultdict(lambda: {item_type: 0 for item_type in HN_ITEM_TYPES})

    for post in posts or []:
        if post.get("platform") != HN_PLATFORM:
            continue

        date_value = row_date(post)
        post_type = post.get("post_type")
        if not date_value or post_type not in HN_ITEM_TYPES:
            continue

        grouped_counts[date_value][post_type] += 1

    rows = []
    for date_value in sorted(grouped_counts):
        counts = grouped_counts[date_value]
        row = base_metric_row(HN_PLATFORM, date_value, processed_at_utc)
        for item_type in HN_ITEM_TYPES:
            row[f"{item_type}_count"] = counts[item_type]
        row["total_count"] = sum(counts.values())
        rows.append(row)

    return rows


def build_daily_users_metric(users, processed_at_utc):
    grouped_users = defaultdict(set)

    for user in users or []:
        if user.get("platform") != HN_PLATFORM:
            continue

        date_value = row_date(user)
        user_id = user.get("user_id")
        if not date_value or not user_id:
            continue

        grouped_users[date_value].add(user_id)

    rows = []
    for date_value in sorted(grouped_users):
        row = base_metric_row(HN_PLATFORM, date_value, processed_at_utc)
        row["total_users"] = len(grouped_users[date_value])
        row["active_users"] = len(grouped_users[date_value])
        rows.append(row)

    return rows


def build_top_posts_by_score(posts, post_type, processed_at_utc, limit=10):
    grouped_posts = defaultdict(list)

    for post in posts or []:
        if post.get("platform") != HN_PLATFORM:
            continue

        date_value = row_date(post)
        score = safe_int(post.get("score"))
        if not date_value or post.get("post_type") != post_type or score is None:
            continue

        row = dict(post)
        row["score"] = score
        grouped_posts[date_value].append(row)

    rows = []
    for date_value in sorted(grouped_posts):
        ranked_posts = sorted(
            grouped_posts[date_value],
            key=lambda row: (row["score"], row.get("source_post_id") or ""),
            reverse=True,
        )[:limit]

        for rank, post in enumerate(ranked_posts, start=1):
            row = base_metric_row(HN_PLATFORM, date_value, processed_at_utc)
            row.update(
                {
                    "rank": rank,
                    "post_id": post.get("post_id"),
                    "source_post_id": post.get("source_post_id"),
                    "author_user_id": post.get("author_user_id"),
                    "author_username": post.get("author_username"),
                    "post_type": post_type,
                    "title": post.get("title"),
                    "url": post.get("url"),
                    "score": post.get("score"),
                }
            )
            rows.append(row)

    return rows


def build_top_users_by_karma(users, processed_at_utc, descending=True, limit=10):
    grouped_users = defaultdict(list)

    for user in users or []:
        if user.get("platform") != HN_PLATFORM:
            continue

        date_value = row_date(user)
        karma_score = safe_int(user.get("karma_score"))
        if not date_value or karma_score is None:
            continue

        row = dict(user)
        row["karma_score"] = karma_score
        grouped_users[date_value].append(row)

    rows = []
    for date_value in sorted(grouped_users):
        ranked_users = sorted(
            grouped_users[date_value],
            key=lambda row: (row["karma_score"], row.get("username") or ""),
            reverse=descending,
        )[:limit]

        for rank, user in enumerate(ranked_users, start=1):
            row = base_metric_row(HN_PLATFORM, date_value, processed_at_utc)
            row.update(
                {
                    "rank": rank,
                    "user_id": user.get("user_id"),
                    "source_user_id": user.get("source_user_id"),
                    "username": user.get("username"),
                    "karma_score": user.get("karma_score"),
                }
            )
            rows.append(row)

    return rows


def build_data_quality_summary(data_quality_rows, processed_at_utc):
    rows = []

    for quality_row in data_quality_rows or []:
        if quality_row.get("platform") != HN_PLATFORM:
            continue

        row = dict(quality_row)
        row["gold_processed_at_utc"] = processed_at_utc
        rows.append(row)

    return rows


def build_hn_gold_tables(silver_tables, processed_at_utc):
    users = silver_tables.get("users", [])
    posts = silver_tables.get("posts", [])
    data_quality_report = silver_tables.get("data_quality_report", [])

    return {
        "daily_item_counts": build_daily_item_counts(posts, processed_at_utc),
        "daily_users_metric": build_daily_users_metric(users, processed_at_utc),
        "top_story_posts": build_top_posts_by_score(
            posts, "story", processed_at_utc
        ),
        "top_job_posts": build_top_posts_by_score(posts, "job", processed_at_utc),
        "top_users_by_karma": build_top_users_by_karma(
            users, processed_at_utc, descending=True
        ),
        "bottom_users_by_karma": build_top_users_by_karma(
            users, processed_at_utc, descending=False
        ),
        "data_quality_summary": build_data_quality_summary(
            data_quality_report, processed_at_utc
        ),
    }


def build_hn_silver_table_path(bucket, silver_prefix, table_name, platform, data_date):
    normalized_prefix = silver_prefix.strip("/")

    if not data_date:
        return f"s3://{bucket}/{normalized_prefix}/{table_name}/"

    parts = date_parts(data_date)
    if not all((parts["year"], parts["month"], parts["day"])):
        raise ValueError("data_date must be in YYYY-MM-DD format")

    if table_name == "data_quality_report":
        return (
            f"s3://{bucket}/{normalized_prefix}/{table_name}/"
            f"platform={platform}/data_date={data_date}/"
        )

    return (
        f"s3://{bucket}/{normalized_prefix}/{table_name}/"
        f"platform={platform}/year={parts['year']}/"
        f"month={parts['month']}/day={parts['day']}/"
    )


def read_silver_table(bucket, silver_prefix, table_name, platform, data_date=None):
    import awswrangler as wr  # type: ignore[import-not-found]

    path = build_hn_silver_table_path(
        bucket, silver_prefix, table_name, platform, data_date
    )
    read_options = {"path": path, "dataset": True}
    if not data_date:
        read_options["partition_filter"] = (
            lambda partition: partition.get("platform") == platform
        )

    dataframe = wr.s3.read_parquet(**read_options)
    return dataframe.to_dict("records")


def write_gold_table(bucket, gold_prefix, table_name, rows, partition_cols, mode):
    normalized_prefix = gold_prefix.strip("/")
    path = f"s3://{bucket}/{normalized_prefix}/{table_name}/"
    rows = rows or []

    if not rows:
        return {"row_count": 0, "s3_path": path, "written": False}

    import awswrangler as wr  # type: ignore[import-not-found]
    import pandas as pd  # type: ignore[import-not-found]

    dataframe = pd.DataFrame(rows)
    wr.s3.to_parquet(
        df=dataframe,
        path=path,
        dataset=True,
        mode=mode,
        partition_cols=partition_cols,
    )
    return {"row_count": len(rows), "s3_path": path, "written": True}


def write_hn_gold_tables(bucket, gold_prefix, gold_tables, mode):
    partition_columns = {
        "daily_item_counts": ["platform", "year", "month", "day"],
        "daily_users_metric": ["platform", "year", "month", "day"],
        "top_story_posts": ["platform", "year", "month", "day"],
        "top_job_posts": ["platform", "year", "month", "day"],
        "top_users_by_karma": ["platform", "year", "month", "day"],
        "bottom_users_by_karma": ["platform", "year", "month", "day"],
        "data_quality_summary": ["platform", "data_date"],
    }

    return {
        table_name: write_gold_table(
            bucket,
            gold_prefix,
            table_name,
            gold_tables.get(table_name, []),
            table_partition_columns,
            mode,
        )
        for table_name, table_partition_columns in partition_columns.items()
    }


def lambda_handler(event, context):
    options = resolve_hn_gold_options(event)
    bucket = options["bucket"]
    if not bucket:
        raise ValueError("DATA_LAKE_BUCKET is required")

    data_date = options["data_date"]
    silver_tables = {
        table_name: read_silver_table(
            bucket,
            options["silver_prefix"],
            table_name,
            HN_PLATFORM,
            data_date=data_date,
        )
        for table_name in HN_SILVER_TABLES
    }

    if data_date:
        silver_tables = {
            table_name: filter_rows_by_data_date(rows, data_date)
            for table_name, rows in silver_tables.items()
        }

    processed_at_utc = utc_now_iso()
    gold_tables = build_hn_gold_tables(silver_tables, processed_at_utc)
    write_results = write_hn_gold_tables(
        bucket, options["gold_prefix"], gold_tables, options["mode"]
    )

    return {
        "source": "hacker-news",
        "layer": "gold",
        "status": "success",
        "bucket": bucket,
        "silver_prefix": options["silver_prefix"],
        "gold_prefix": options["gold_prefix"],
        "data_date": data_date,
        "mode": options["mode"],
        "tables": write_results,
        "processed_at_utc": processed_at_utc,
        "request_id": getattr(context, "aws_request_id", None),
    }
