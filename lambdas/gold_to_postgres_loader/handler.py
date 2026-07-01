import datetime as dt
import os


PLATFORM_TO_SOURCE_PREFIX = {
    "hacker-news": "gold/hacker-news",
    "x": "gold/x",
}

PLATFORM_TO_ROW_VALUE = {
    "hacker-news": "HackerNews",
    "x": "X",
}

GOLD_DATASET_TO_POSTGRES_TABLE = {
    "hacker-news": {
        "daily_item_counts": "hn_daily_item_counts",
        "daily_users_metric": "hn_daily_users_metric",
        "top_story_posts": "hn_top_story_posts",
        "top_job_posts": "hn_top_job_posts",
        "top_users_by_karma": "hn_top_users_by_karma",
        "bottom_users_by_karma": "hn_bottom_users_by_karma",
        "data_quality_summary": "hn_data_quality_summary",
    },
    "x": {
        "daily_users_metric": "x_daily_users_metric",
        "top_users_by_followers": "x_top_users_by_followers",
        "top_posts_by_engagement": "x_top_posts_by_engagement",
        "hashtag_trends": "x_hashtag_trends",
        "data_quality_summary": "x_data_quality_summary",
    },
}

POSTGRES_TABLE_COLUMNS = {
    "hn_daily_item_counts": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "story_count",
        "ask_count",
        "comment_count",
        "job_count",
        "poll_count",
        "total_count",
    ],
    "hn_daily_users_metric": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "total_users",
        "active_users",
    ],
    "hn_top_story_posts": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "post_id",
        "source_post_id",
        "author_user_id",
        "author_username",
        "post_type",
        "title",
        "url",
        "score",
    ],
    "hn_top_job_posts": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "post_id",
        "source_post_id",
        "author_user_id",
        "author_username",
        "post_type",
        "title",
        "url",
        "score",
    ],
    "hn_top_users_by_karma": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "user_id",
        "source_user_id",
        "username",
        "karma_score",
    ],
    "hn_bottom_users_by_karma": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "user_id",
        "source_user_id",
        "username",
        "karma_score",
    ],
    "hn_data_quality_summary": [
        "table_name",
        "platform",
        "data_date",
        "ingest_date",
        "row_count",
        "column_count",
        "non_null_cell_count",
        "total_cell_count",
        "data_quality_score",
        "silver_processed_at_utc",
        "gold_processed_at_utc",
    ],
    "x_daily_users_metric": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "total_users",
        "active_users",
    ],
    "x_top_users_by_followers": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "user_id",
        "source_user_id",
        "username",
        "display_name",
        "followers_count",
        "following_count",
        "is_verified",
    ],
    "x_top_posts_by_engagement": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "post_id",
        "source_post_id",
        "author_user_id",
        "author_username",
        "post_type",
        "content_text",
        "like_count",
        "retweet_count",
        "reply_count",
        "quote_count",
        "engagement_count",
    ],
    "x_hashtag_trends": [
        "date",
        "platform",
        "year",
        "month",
        "day",
        "gold_processed_at_utc",
        "rank",
        "tag",
        "tag_type",
        "post_count",
    ],
    "x_data_quality_summary": [
        "table_name",
        "platform",
        "data_date",
        "ingest_date",
        "row_count",
        "column_count",
        "non_null_cell_count",
        "total_cell_count",
        "data_quality_score",
        "silver_processed_at_utc",
        "gold_processed_at_utc",
    ],
}

SUPPORTED_MODES = {"replace_date"}


def _as_list(value):
    if isinstance(value, str):
        return [value]

    try:
        return list(value)
    except TypeError as exc:
        raise ValueError(f"Expected a list-compatible value, got: {value}") from exc


def utc_today_iso():
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def date_parts(data_date):
    if not isinstance(data_date, str) or not data_date.strip():
        return {"year": None, "month": None, "day": None}

    try:
        parsed = dt.date.fromisoformat(data_date.strip())
    except ValueError:
        return {"year": None, "month": None, "day": None}

    return {
        "year": f"{parsed.year:04d}",
        "month": f"{parsed.month:02d}",
        "day": f"{parsed.day:02d}",
    }


def resolve_loader_options(event):
    event = event if isinstance(event, dict) else {}

    platforms = event.get("platforms") or ["hacker-news", "x"]
    platforms = _as_list(platforms)

    invalid_platforms = [
        platform
        for platform in platforms
        if platform not in PLATFORM_TO_SOURCE_PREFIX
    ]
    if invalid_platforms:
        invalid_values = ", ".join(str(platform) for platform in invalid_platforms)
        raise ValueError(f"Unsupported platform(s): {invalid_values}")

    mode = event.get("mode") or "replace_date"
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported loader mode: {mode}")

    return {
        "bucket": event.get("bucket") or os.getenv("DATA_LAKE_BUCKET"),
        "gold_prefix": event.get("gold_prefix")
        or os.getenv("GOLD_PREFIX")
        or "gold",
        "data_date": event.get("data_date") or utc_today_iso(),
        "platforms": platforms,
        "datasets": event.get("datasets") or None,
        "mode": mode,
    }


def get_supported_datasets(platform):
    if platform not in GOLD_DATASET_TO_POSTGRES_TABLE:
        raise ValueError(f"Unsupported platform: {platform}")

    return list(GOLD_DATASET_TO_POSTGRES_TABLE[platform])


def get_platform_row_value(platform):
    row_value = PLATFORM_TO_ROW_VALUE.get(platform)
    if row_value is None:
        raise ValueError(f"Unsupported platform: {platform}")

    return row_value


def resolve_datasets_for_platform(platform, requested_datasets=None):
    supported_datasets = get_supported_datasets(platform)
    if requested_datasets is None:
        return supported_datasets

    requested_datasets = _as_list(requested_datasets)
    unsupported_datasets = [
        dataset
        for dataset in requested_datasets
        if dataset not in GOLD_DATASET_TO_POSTGRES_TABLE[platform]
    ]
    if unsupported_datasets:
        invalid_values = ", ".join(str(dataset) for dataset in unsupported_datasets)
        raise ValueError(
            "Unsupported dataset(s) for "
            f"{platform}: {invalid_values}"
        )

    return list(requested_datasets)


def get_postgres_table_name(platform, dataset_name):
    if platform not in GOLD_DATASET_TO_POSTGRES_TABLE:
        raise ValueError(f"Unsupported platform: {platform}")

    table_name = GOLD_DATASET_TO_POSTGRES_TABLE[platform].get(dataset_name)
    if not table_name:
        raise ValueError(f"Unsupported dataset for {platform}: {dataset_name}")

    return table_name


def build_gold_s3_prefix(gold_prefix, platform, dataset_name, data_date):
    get_postgres_table_name(platform, dataset_name)

    normalized_gold_prefix = (gold_prefix or "").strip("/")
    prefix_parts = [
        part.strip("/")
        for part in (normalized_gold_prefix, platform, dataset_name)
        if part and part.strip("/")
    ]
    return "/".join(prefix_parts) + "/"


def build_gold_partition_filter_values(platform, dataset_name, data_date):
    get_postgres_table_name(platform, dataset_name)
    platform_row_value = get_platform_row_value(platform)

    if dataset_name == "data_quality_summary":
        return {
            "platform": platform_row_value,
            "data_date": data_date,
        }

    parts = date_parts(data_date)
    return {
        "platform": platform_row_value,
        "year": parts["year"],
        "month": parts["month"],
        "day": parts["day"],
    }


def get_table_columns(table_name):
    columns = POSTGRES_TABLE_COLUMNS.get(table_name)
    if columns is None:
        raise ValueError(f"Unsupported PostgreSQL table: {table_name}")

    return list(columns)


def build_delete_sql(table_name):
    columns = get_table_columns(table_name)
    date_column = "data_date" if "data_date" in columns else "date"
    where_clauses = [f"{date_column} = %s"]

    if "platform" in columns:
        where_clauses.append("platform = %s")

    return f"DELETE FROM {table_name} WHERE {' AND '.join(where_clauses)}"


def build_insert_sql(table_name):
    columns = get_table_columns(table_name)
    column_names = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    return f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"


def row_to_insert_values(row, table_name):
    columns = get_table_columns(table_name)
    return tuple(row.get(column) for column in columns)


def lambda_handler(event, context):
    options = resolve_loader_options(event)
    datasets_by_platform = {
        platform: resolve_datasets_for_platform(platform, options["datasets"])
        for platform in options["platforms"]
    }

    return {
        "source": "gold-to-postgres",
        "status": "configured",
        "mode": options["mode"],
        "data_date": options["data_date"],
        "platforms": options["platforms"],
        "datasets_by_platform": datasets_by_platform,
        "request_id": getattr(context, "aws_request_id", None),
    }
