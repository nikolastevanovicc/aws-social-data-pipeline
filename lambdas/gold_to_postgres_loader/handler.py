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


class MissingGoldDatasetFiles(Exception):
    pass


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
        for part in (normalized_gold_prefix, dataset_name)
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


def build_s3_uri(bucket, key_or_prefix):
    if not bucket:
        raise ValueError("DATA_LAKE_BUCKET is required")
    if not key_or_prefix:
        raise ValueError("S3 key or prefix is required")

    normalized_bucket = str(bucket).strip().strip("/")
    normalized_key = str(key_or_prefix).strip().lstrip("/")
    if not normalized_bucket:
        raise ValueError("DATA_LAKE_BUCKET is required")
    if not normalized_key:
        raise ValueError("S3 key or prefix is required")

    return f"s3://{normalized_bucket}/{normalized_key}"


def is_no_files_found_error(error, awswrangler_module):
    wr_exceptions = getattr(awswrangler_module, "exceptions", None)
    no_files_found = getattr(wr_exceptions, "NoFilesFound", None)
    if no_files_found is not None and isinstance(error, no_files_found):
        return True

    return error.__class__.__name__ == "NoFilesFound"


def read_parquet_rows_from_s3(s3_uri, partition_filter_values=None):
    import awswrangler as wr

    read_kwargs = {
        "path": s3_uri,
        "dataset": True,
    }

    if partition_filter_values is not None:

        def partition_filter(partitions):
            return all(
                str(partitions.get(key)) == str(expected_value)
                for key, expected_value in partition_filter_values.items()
            )

        read_kwargs["partition_filter"] = partition_filter

    try:
        df = wr.s3.read_parquet(**read_kwargs)
    except Exception as exc:
        if is_no_files_found_error(exc, wr):
            raise MissingGoldDatasetFiles(str(exc)) from exc
        raise

    if df.empty:
        return []

    return df.to_dict(orient="records")


def read_gold_dataset_rows(bucket, gold_prefix, platform, dataset_name, data_date):
    postgres_table = get_postgres_table_name(platform, dataset_name)
    root_prefix = build_gold_s3_prefix(gold_prefix, platform, dataset_name, data_date)
    s3_uri = build_s3_uri(bucket, root_prefix)
    partition_filter_values = build_gold_partition_filter_values(
        platform,
        dataset_name,
        data_date,
    )
    missing_files = False
    try:
        rows = read_parquet_rows_from_s3(s3_uri, partition_filter_values)
    except MissingGoldDatasetFiles:
        rows = []
        missing_files = True

    return {
        "platform": platform,
        "dataset_name": dataset_name,
        "postgres_table": postgres_table,
        "s3_uri": s3_uri,
        "partition_filter_values": partition_filter_values,
        "rows": rows,
        "row_count": len(rows),
        "missing_files": missing_files,
    }


def read_requested_gold_datasets(
    bucket,
    gold_prefix,
    data_date,
    platforms,
    requested_datasets=None,
):
    results = {}
    for platform in platforms:
        results[platform] = {}
        dataset_names = resolve_datasets_for_platform(platform, requested_datasets)
        for dataset_name in dataset_names:
            dataset_result = read_gold_dataset_rows(
                bucket,
                gold_prefix,
                platform,
                dataset_name,
                data_date,
            )
            results[platform][dataset_name] = {
                "postgres_table": dataset_result["postgres_table"],
                "s3_uri": dataset_result["s3_uri"],
                "partition_filter_values": dataset_result["partition_filter_values"],
                "row_count": dataset_result["row_count"],
                "rows": dataset_result["rows"],
            }
            if dataset_result.get("missing_files"):
                results[platform][dataset_name]["missing_files"] = True

    return results


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


def resolve_postgres_options(event):
    event = event if isinstance(event, dict) else {}

    raw_port = event.get("postgres_port") or os.getenv("POSTGRES_PORT") or 5432
    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise ValueError("POSTGRES_PORT must be an integer") from exc

    options = {
        "host": event.get("postgres_host") or os.getenv("POSTGRES_HOST"),
        "port": port,
        "database": event.get("postgres_database")
        or os.getenv("POSTGRES_DATABASE")
        or os.getenv("POSTGRES_DB"),
        "user": event.get("postgres_user") or os.getenv("POSTGRES_USER"),
        "password": event.get("postgres_password") or os.getenv("POSTGRES_PASSWORD"),
    }

    required_fields = {
        "host": "POSTGRES_HOST is required",
        "database": "POSTGRES_DATABASE is required",
        "user": "POSTGRES_USER is required",
        "password": "POSTGRES_PASSWORD is required",
    }
    for field_name, error_message in required_fields.items():
        if not options[field_name]:
            raise ValueError(error_message)

    return options


def connect_to_postgres(postgres_options):
    import pg8000.dbapi

    return pg8000.dbapi.connect(
        host=postgres_options["host"],
        port=postgres_options["port"],
        database=postgres_options["database"],
        user=postgres_options["user"],
        password=postgres_options["password"],
    )


def delete_values_for_table(table_name, data_date, platform=None):
    columns = get_table_columns(table_name)
    values = [data_date]

    if "platform" in columns:
        values.append(platform)

    return tuple(values)


def execute_replace_table_rows(connection, table_name, rows, data_date, platform):
    delete_sql = build_delete_sql(table_name)
    delete_values = delete_values_for_table(table_name, data_date, platform)
    insert_sql = build_insert_sql(table_name)
    insert_values = [
        row_to_insert_values(row, table_name)
        for row in rows
    ]

    cursor = connection.cursor()
    cursor.execute(delete_sql, delete_values)

    if insert_values:
        if hasattr(cursor, "executemany"):
            cursor.executemany(insert_sql, insert_values)
        else:
            for values in insert_values:
                cursor.execute(insert_sql, values)

    return {
        "table_name": table_name,
        "deleted_for_date": data_date,
        "platform": platform,
        "inserted_row_count": len(rows),
    }


def write_loaded_datasets_to_postgres(connection, loaded_datasets, data_date):
    results = {}

    for platform, platform_results in loaded_datasets.items():
        results[platform] = {}
        platform_row_value = get_platform_row_value(platform)

        for dataset_name, dataset_result in platform_results.items():
            table_name = dataset_result["postgres_table"]
            rows = dataset_result.get("rows") or []
            write_result = execute_replace_table_rows(
                connection,
                table_name,
                rows,
                data_date,
                platform_row_value,
            )
            results[platform][dataset_name] = {
                "postgres_table": table_name,
                "inserted_row_count": write_result["inserted_row_count"],
            }

    return results


def lambda_handler(event, context):
    options = resolve_loader_options(event)
    if not options["bucket"]:
        raise ValueError("DATA_LAKE_BUCKET is required")

    loaded_datasets = read_requested_gold_datasets(
        options["bucket"],
        options["gold_prefix"],
        options["data_date"],
        options["platforms"],
        options["datasets"],
    )
    postgres_options = resolve_postgres_options(event)

    connection = None
    try:
        connection = connect_to_postgres(postgres_options)
        write_results = write_loaded_datasets_to_postgres(
            connection,
            loaded_datasets,
            options["data_date"],
        )
        connection.commit()
    except Exception:
        if connection is not None and hasattr(connection, "rollback"):
            connection.rollback()
        raise
    finally:
        if connection is not None and hasattr(connection, "close"):
            connection.close()

    tables = {}
    for platform, platform_results in loaded_datasets.items():
        tables[platform] = {}
        for dataset_name, dataset_result in platform_results.items():
            table_result = {
                "postgres_table": dataset_result["postgres_table"],
                "s3_uri": dataset_result["s3_uri"],
                "partition_filter_values": dataset_result["partition_filter_values"],
                "loaded_row_count": dataset_result["row_count"],
                "inserted_row_count": write_results[platform][dataset_name][
                    "inserted_row_count"
                ],
            }
            if dataset_result.get("missing_files"):
                table_result["missing_files"] = True
                table_result["skipped"] = True
            tables[platform][dataset_name] = table_result

    return {
        "source": "gold-to-postgres",
        "status": "written",
        "mode": options["mode"],
        "bucket": options["bucket"],
        "gold_prefix": options["gold_prefix"],
        "data_date": options["data_date"],
        "platforms": options["platforms"],
        "datasets": options["datasets"],
        "tables": tables,
        "request_id": getattr(context, "aws_request_id", None),
    }
