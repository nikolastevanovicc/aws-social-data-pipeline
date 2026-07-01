import importlib.util
from pathlib import Path

import pytest


HANDLER_PATH = (
    Path(__file__).resolve().parents[2]
    / "lambdas"
    / "gold_to_postgres_loader"
    / "handler.py"
)
SPEC = importlib.util.spec_from_file_location("gold_to_postgres_loader_handler", HANDLER_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


DATA_DATE = "2026-05-20"
POSTGRES_ENV_KEYS = [
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DATABASE",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
]


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, values=None):
        self.calls.append(("execute", sql, values))

    def executemany(self, sql, values):
        self.calls.append(("executemany", sql, list(values)))


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closes += 1


class FakeContext:
    aws_request_id = "request-123"


def clear_postgres_env(monkeypatch):
    for key in POSTGRES_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_resolve_loader_options_defaults():
    options = handler.resolve_loader_options({})

    assert options["platforms"] == ["hacker-news", "x"]
    assert options["mode"] == "replace_date"
    assert options["gold_prefix"] == "gold"
    assert options["datasets"] is None


def test_resolve_loader_options_explicit_values():
    options = handler.resolve_loader_options(
        {
            "bucket": "analytics-bucket",
            "gold_prefix": "custom-gold",
            "data_date": DATA_DATE,
            "platforms": ["x"],
            "datasets": ["daily_users_metric"],
            "mode": "replace_date",
        }
    )

    assert options == {
        "bucket": "analytics-bucket",
        "gold_prefix": "custom-gold",
        "data_date": DATA_DATE,
        "platforms": ["x"],
        "datasets": ["daily_users_metric"],
        "mode": "replace_date",
    }


def test_resolve_loader_options_rejects_unsupported_platform():
    with pytest.raises(ValueError, match="Unsupported platform"):
        handler.resolve_loader_options({"platforms": ["mastodon"]})


def test_resolve_loader_options_rejects_unsupported_mode():
    with pytest.raises(ValueError, match="Unsupported loader mode"):
        handler.resolve_loader_options({"mode": "append"})


def test_resolve_postgres_options_explicit_event_values():
    options = handler.resolve_postgres_options(
        {
            "postgres_host": "db.example.com",
            "postgres_port": "6543",
            "postgres_database": "analytics",
            "postgres_user": "loader",
            "postgres_password": "secret",
        }
    )

    assert options == {
        "host": "db.example.com",
        "port": 6543,
        "database": "analytics",
        "user": "loader",
        "password": "secret",
    }


def test_resolve_postgres_options_env_fallback(monkeypatch):
    clear_postgres_env(monkeypatch)
    monkeypatch.setenv("POSTGRES_HOST", "env-db.example.com")
    monkeypatch.setenv("POSTGRES_PORT", "7654")
    monkeypatch.setenv("POSTGRES_DB", "env_analytics")
    monkeypatch.setenv("POSTGRES_USER", "env_loader")
    monkeypatch.setenv("POSTGRES_PASSWORD", "env_secret")

    options = handler.resolve_postgres_options(None)

    assert options == {
        "host": "env-db.example.com",
        "port": 7654,
        "database": "env_analytics",
        "user": "env_loader",
        "password": "env_secret",
    }


def test_resolve_postgres_options_missing_host_raises(monkeypatch):
    clear_postgres_env(monkeypatch)

    with pytest.raises(ValueError, match="POSTGRES_HOST is required"):
        handler.resolve_postgres_options(
            {
                "postgres_database": "analytics",
                "postgres_user": "loader",
                "postgres_password": "secret",
            }
        )


def test_resolve_postgres_options_missing_database_raises(monkeypatch):
    clear_postgres_env(monkeypatch)

    with pytest.raises(ValueError, match="POSTGRES_DATABASE is required"):
        handler.resolve_postgres_options(
            {
                "postgres_host": "db.example.com",
                "postgres_user": "loader",
                "postgres_password": "secret",
            }
        )


def test_resolve_postgres_options_missing_user_raises(monkeypatch):
    clear_postgres_env(monkeypatch)

    with pytest.raises(ValueError, match="POSTGRES_USER is required"):
        handler.resolve_postgres_options(
            {
                "postgres_host": "db.example.com",
                "postgres_database": "analytics",
                "postgres_password": "secret",
            }
        )


def test_resolve_postgres_options_missing_password_raises(monkeypatch):
    clear_postgres_env(monkeypatch)

    with pytest.raises(ValueError, match="POSTGRES_PASSWORD is required"):
        handler.resolve_postgres_options(
            {
                "postgres_host": "db.example.com",
                "postgres_database": "analytics",
                "postgres_user": "loader",
            }
        )


def test_resolve_postgres_options_invalid_port_raises(monkeypatch):
    clear_postgres_env(monkeypatch)

    with pytest.raises(ValueError, match="POSTGRES_PORT must be an integer"):
        handler.resolve_postgres_options(
            {
                "postgres_host": "db.example.com",
                "postgres_port": "not-a-port",
                "postgres_database": "analytics",
                "postgres_user": "loader",
                "postgres_password": "secret",
            }
        )


def test_get_supported_datasets_hacker_news():
    assert handler.get_supported_datasets("hacker-news") == [
        "daily_item_counts",
        "daily_users_metric",
        "top_story_posts",
        "top_job_posts",
        "top_users_by_karma",
        "bottom_users_by_karma",
        "data_quality_summary",
    ]


def test_get_supported_datasets_x():
    assert handler.get_supported_datasets("x") == [
        "daily_users_metric",
        "top_users_by_followers",
        "top_posts_by_engagement",
        "hashtag_trends",
        "data_quality_summary",
    ]


def test_get_supported_datasets_rejects_unsupported_platform():
    with pytest.raises(ValueError, match="Unsupported platform"):
        handler.get_supported_datasets("reddit")


def test_get_platform_row_value():
    assert handler.get_platform_row_value("hacker-news") == "HackerNews"
    assert handler.get_platform_row_value("x") == "X"


def test_get_platform_row_value_rejects_unsupported_platform():
    with pytest.raises(ValueError, match="Unsupported platform"):
        handler.get_platform_row_value("reddit")


def test_resolve_datasets_for_platform_defaults_to_all_supported():
    assert handler.resolve_datasets_for_platform("x") == handler.get_supported_datasets("x")


def test_resolve_datasets_for_platform_accepts_single_string():
    assert handler.resolve_datasets_for_platform("x", "daily_users_metric") == [
        "daily_users_metric"
    ]


def test_resolve_datasets_for_platform_accepts_list():
    assert handler.resolve_datasets_for_platform(
        "hacker-news",
        ["daily_item_counts", "top_users_by_karma"],
    ) == ["daily_item_counts", "top_users_by_karma"]


def test_resolve_datasets_for_platform_rejects_unsupported_dataset():
    with pytest.raises(ValueError, match="Unsupported dataset"):
        handler.resolve_datasets_for_platform("x", ["top_users_by_karma"])


@pytest.mark.parametrize(
    ("platform", "dataset_name", "expected_table_name"),
    [
        ("hacker-news", "daily_item_counts", "hn_daily_item_counts"),
        ("hacker-news", "top_users_by_karma", "hn_top_users_by_karma"),
        ("x", "daily_users_metric", "x_daily_users_metric"),
        ("x", "hashtag_trends", "x_hashtag_trends"),
    ],
)
def test_get_postgres_table_name(platform, dataset_name, expected_table_name):
    assert handler.get_postgres_table_name(platform, dataset_name) == expected_table_name


def test_get_postgres_table_name_rejects_unsupported_dataset():
    with pytest.raises(ValueError, match="Unsupported dataset"):
        handler.get_postgres_table_name("x", "daily_item_counts")


def test_build_gold_s3_prefix():
    assert (
        handler.build_gold_s3_prefix(
            "gold",
            "x",
            "daily_users_metric",
            DATA_DATE,
        )
        == "gold/x/daily_users_metric/"
    )
    assert (
        handler.build_gold_s3_prefix(
            "/gold/",
            "hacker-news",
            "daily_item_counts",
            DATA_DATE,
        )
        == "gold/hacker-news/daily_item_counts/"
    )


def test_build_gold_s3_prefix_rejects_unsupported_dataset():
    with pytest.raises(ValueError, match="Unsupported dataset"):
        handler.build_gold_s3_prefix("gold", "x", "daily_item_counts", DATA_DATE)


def test_date_parts():
    assert handler.date_parts(DATA_DATE) == {
        "year": "2026",
        "month": "05",
        "day": "20",
    }
    assert handler.date_parts("invalid") == {"year": None, "month": None, "day": None}
    assert handler.date_parts(None) == {"year": None, "month": None, "day": None}


@pytest.mark.parametrize(
    ("platform", "dataset_name", "expected_values"),
    [
        (
            "x",
            "daily_users_metric",
            {
                "platform": "X",
                "year": "2026",
                "month": "05",
                "day": "20",
            },
        ),
        (
            "hacker-news",
            "daily_item_counts",
            {
                "platform": "HackerNews",
                "year": "2026",
                "month": "05",
                "day": "20",
            },
        ),
        (
            "x",
            "data_quality_summary",
            {
                "platform": "X",
                "data_date": DATA_DATE,
            },
        ),
        (
            "hacker-news",
            "data_quality_summary",
            {
                "platform": "HackerNews",
                "data_date": DATA_DATE,
            },
        ),
    ],
)
def test_build_gold_partition_filter_values(platform, dataset_name, expected_values):
    assert (
        handler.build_gold_partition_filter_values(platform, dataset_name, DATA_DATE)
        == expected_values
    )


def test_build_s3_uri():
    assert (
        handler.build_s3_uri("bucket", "gold/x/daily_users_metric/")
        == "s3://bucket/gold/x/daily_users_metric/"
    )
    assert (
        handler.build_s3_uri("bucket", "/gold/x/daily_users_metric/")
        == "s3://bucket/gold/x/daily_users_metric/"
    )


def test_build_s3_uri_rejects_missing_bucket():
    with pytest.raises(ValueError, match="DATA_LAKE_BUCKET is required"):
        handler.build_s3_uri("", "gold/x/daily_users_metric/")


def test_build_s3_uri_rejects_missing_key():
    with pytest.raises(ValueError, match="S3 key or prefix is required"):
        handler.build_s3_uri("bucket", "")


def test_read_gold_dataset_rows(monkeypatch):
    rows = [
        {"date": DATA_DATE, "platform": "X", "total_users": 10},
        {"date": DATA_DATE, "platform": "X", "total_users": 12},
    ]
    observed = {}

    def fake_read_parquet_rows_from_s3(s3_uri, partition_filter_values=None):
        observed["s3_uri"] = s3_uri
        observed["partition_filter_values"] = partition_filter_values
        return rows

    monkeypatch.setattr(
        handler,
        "read_parquet_rows_from_s3",
        fake_read_parquet_rows_from_s3,
    )

    result = handler.read_gold_dataset_rows(
        "bucket",
        "gold",
        "x",
        "daily_users_metric",
        DATA_DATE,
    )

    assert result["platform"] == "x"
    assert result["dataset_name"] == "daily_users_metric"
    assert result["postgres_table"] == "x_daily_users_metric"
    assert result["s3_uri"] == "s3://bucket/gold/x/daily_users_metric/"
    assert result["partition_filter_values"] == {
        "platform": "X",
        "year": "2026",
        "month": "05",
        "day": "20",
    }
    assert result["row_count"] == 2
    assert result["rows"] == rows
    assert observed == {
        "s3_uri": "s3://bucket/gold/x/daily_users_metric/",
        "partition_filter_values": {
            "platform": "X",
            "year": "2026",
            "month": "05",
            "day": "20",
        },
    }


def test_read_requested_gold_datasets(monkeypatch):
    def fake_read_gold_dataset_rows(bucket, gold_prefix, platform, dataset_name, data_date):
        return {
            "platform": platform,
            "dataset_name": dataset_name,
            "postgres_table": f"{platform}_{dataset_name}",
            "s3_uri": f"s3://{bucket}/{gold_prefix}/{platform}/{dataset_name}/",
            "partition_filter_values": {"data_date": data_date},
            "rows": [{"id": 1}],
            "row_count": 1,
        }

    monkeypatch.setattr(
        handler,
        "read_gold_dataset_rows",
        fake_read_gold_dataset_rows,
    )

    result = handler.read_requested_gold_datasets(
        "bucket",
        "gold",
        DATA_DATE,
        ["x"],
        ["daily_users_metric"],
    )

    assert result == {
        "x": {
            "daily_users_metric": {
                "postgres_table": "x_daily_users_metric",
                "s3_uri": "s3://bucket/gold/x/daily_users_metric/",
                "partition_filter_values": {"data_date": DATA_DATE},
                "row_count": 1,
                "rows": [{"id": 1}],
            }
        }
    }


def test_get_table_columns_x_daily_users_metric():
    columns = handler.get_table_columns("x_daily_users_metric")

    assert "date" in columns
    assert "platform" in columns
    assert "total_users" in columns
    assert "active_users" in columns


def test_get_table_columns_hn_daily_item_counts():
    columns = handler.get_table_columns("hn_daily_item_counts")

    assert "story_count" in columns
    assert "ask_count" in columns
    assert "comment_count" in columns
    assert "job_count" in columns
    assert "poll_count" in columns
    assert "total_count" in columns


def test_get_table_columns_rejects_unsupported_table():
    with pytest.raises(ValueError, match="Unsupported PostgreSQL table"):
        handler.get_table_columns("unsupported_table")


@pytest.mark.parametrize(
    ("table_name", "expected_sql"),
    [
        (
            "x_daily_users_metric",
            "DELETE FROM x_daily_users_metric WHERE date = %s AND platform = %s",
        ),
        (
            "x_data_quality_summary",
            "DELETE FROM x_data_quality_summary WHERE data_date = %s AND platform = %s",
        ),
    ],
)
def test_build_delete_sql(table_name, expected_sql):
    assert handler.build_delete_sql(table_name) == expected_sql


@pytest.mark.parametrize(
    "table_name",
    [
        "x_daily_users_metric",
        "x_data_quality_summary",
    ],
)
def test_delete_values_for_table(table_name):
    assert handler.delete_values_for_table(table_name, DATA_DATE, "X") == (
        DATA_DATE,
        "X",
    )


def test_build_insert_sql():
    sql = handler.build_insert_sql("x_daily_users_metric")
    columns = handler.POSTGRES_TABLE_COLUMNS["x_daily_users_metric"]

    assert sql.startswith("INSERT INTO x_daily_users_metric")
    for column in columns:
        assert column in sql
    assert sql.count("%s") == len(columns)


def test_row_to_insert_values():
    row = {
        "date": DATA_DATE,
        "platform": "X",
        "year": "2026",
        "month": "05",
        "day": "20",
        "gold_processed_at_utc": "2026-05-21T10:00:00Z",
        "total_users": 10,
    }

    values = handler.row_to_insert_values(row, "x_daily_users_metric")

    assert isinstance(values, tuple)
    assert values == tuple(
        row.get(column)
        for column in handler.POSTGRES_TABLE_COLUMNS["x_daily_users_metric"]
    )
    assert values[
        handler.POSTGRES_TABLE_COLUMNS["x_daily_users_metric"].index("active_users")
    ] is None


def test_execute_replace_table_rows():
    connection = FakeConnection()
    rows = [
        {
            "date": DATA_DATE,
            "platform": "X",
            "year": "2026",
            "month": "05",
            "day": "20",
            "gold_processed_at_utc": "2026-05-21T10:00:00Z",
            "total_users": 10,
            "active_users": 8,
        },
        {
            "date": DATA_DATE,
            "platform": "X",
            "year": "2026",
            "month": "05",
            "day": "20",
            "gold_processed_at_utc": "2026-05-21T10:00:00Z",
            "total_users": 12,
            "active_users": 9,
        },
    ]

    result = handler.execute_replace_table_rows(
        connection,
        "x_daily_users_metric",
        rows,
        DATA_DATE,
        "X",
    )

    expected_insert_values = [
        tuple(
            row.get(column)
            for column in handler.POSTGRES_TABLE_COLUMNS["x_daily_users_metric"]
        )
        for row in rows
    ]
    assert connection.cursor_obj.calls[0] == (
        "execute",
        "DELETE FROM x_daily_users_metric WHERE date = %s AND platform = %s",
        (DATA_DATE, "X"),
    )
    assert connection.cursor_obj.calls[1] == (
        "executemany",
        handler.build_insert_sql("x_daily_users_metric"),
        expected_insert_values,
    )
    assert result["inserted_row_count"] == 2
    assert connection.commits == 0


def test_execute_replace_table_rows_empty_rows():
    connection = FakeConnection()

    result = handler.execute_replace_table_rows(
        connection,
        "x_daily_users_metric",
        [],
        DATA_DATE,
        "X",
    )

    assert connection.cursor_obj.calls == [
        (
            "execute",
            "DELETE FROM x_daily_users_metric WHERE date = %s AND platform = %s",
            (DATA_DATE, "X"),
        )
    ]
    assert result["inserted_row_count"] == 0
    assert connection.commits == 0


def test_write_loaded_datasets_to_postgres():
    connection = FakeConnection()
    rows = [
        {
            "date": DATA_DATE,
            "platform": "X",
            "year": "2026",
            "month": "05",
            "day": "20",
            "gold_processed_at_utc": "2026-05-21T10:00:00Z",
            "total_users": 10,
            "active_users": 8,
        },
        {
            "date": DATA_DATE,
            "platform": "X",
            "year": "2026",
            "month": "05",
            "day": "20",
            "gold_processed_at_utc": "2026-05-21T10:00:00Z",
            "total_users": 12,
            "active_users": 9,
        },
    ]
    loaded_datasets = {
        "x": {
            "daily_users_metric": {
                "postgres_table": "x_daily_users_metric",
                "rows": rows,
                "row_count": 2,
            }
        }
    }

    result = handler.write_loaded_datasets_to_postgres(
        connection,
        loaded_datasets,
        DATA_DATE,
    )

    assert result == {
        "x": {
            "daily_users_metric": {
                "postgres_table": "x_daily_users_metric",
                "inserted_row_count": 2,
            }
        }
    }
    assert connection.cursor_obj.calls[0][2] == (DATA_DATE, "X")


def test_lambda_handler(monkeypatch):
    connection = FakeConnection()

    def fake_read_requested_gold_datasets(
        bucket,
        gold_prefix,
        data_date,
        platforms,
        requested_datasets=None,
    ):
        assert bucket == "bucket"
        assert gold_prefix == "gold"
        assert data_date == DATA_DATE
        assert platforms == ["x"]
        assert requested_datasets == ["daily_users_metric"]
        return {
            "x": {
                "daily_users_metric": {
                    "postgres_table": "x_daily_users_metric",
                    "s3_uri": "s3://bucket/gold/x/daily_users_metric/",
                    "partition_filter_values": {
                        "platform": "X",
                        "year": "2026",
                        "month": "05",
                        "day": "20",
                    },
                    "row_count": 2,
                    "rows": [{"id": 1}, {"id": 2}],
                }
            }
        }

    def fake_resolve_postgres_options(event):
        assert event["bucket"] == "bucket"
        return {
            "host": "db.example.com",
            "port": 5432,
            "database": "analytics",
            "user": "loader",
            "password": "secret",
        }

    def fake_connect_to_postgres(postgres_options):
        assert postgres_options["host"] == "db.example.com"
        return connection

    monkeypatch.setattr(
        handler,
        "read_requested_gold_datasets",
        fake_read_requested_gold_datasets,
    )
    monkeypatch.setattr(
        handler,
        "resolve_postgres_options",
        fake_resolve_postgres_options,
    )
    monkeypatch.setattr(handler, "connect_to_postgres", fake_connect_to_postgres)

    response = handler.lambda_handler(
        {
            "bucket": "bucket",
            "data_date": DATA_DATE,
            "platforms": ["x"],
            "datasets": ["daily_users_metric"],
            "mode": "replace_date",
        },
        FakeContext(),
    )

    assert response["source"] == "gold-to-postgres"
    assert response["status"] == "written"
    assert response["bucket"] == "bucket"
    assert response["data_date"] == DATA_DATE
    assert response["platforms"] == ["x"]
    assert response["request_id"] == "request-123"
    assert response["tables"]["x"]["daily_users_metric"] == {
        "postgres_table": "x_daily_users_metric",
        "s3_uri": "s3://bucket/gold/x/daily_users_metric/",
        "partition_filter_values": {
            "platform": "X",
            "year": "2026",
            "month": "05",
            "day": "20",
        },
        "loaded_row_count": 2,
        "inserted_row_count": 2,
    }
    assert "rows" not in response["tables"]["x"]["daily_users_metric"]
    assert connection.commits == 1
    assert connection.closes == 1


def test_lambda_handler_rolls_back_and_closes_on_write_error(monkeypatch):
    connection = FakeConnection()

    def fake_read_requested_gold_datasets(*args, **kwargs):
        return {
            "x": {
                "daily_users_metric": {
                    "postgres_table": "x_daily_users_metric",
                    "s3_uri": "s3://bucket/gold/x/daily_users_metric/",
                    "partition_filter_values": {
                        "platform": "X",
                        "year": "2026",
                        "month": "05",
                        "day": "20",
                    },
                    "row_count": 1,
                    "rows": [{"date": DATA_DATE, "platform": "X"}],
                }
            }
        }

    def fake_write_loaded_datasets_to_postgres(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(
        handler,
        "read_requested_gold_datasets",
        fake_read_requested_gold_datasets,
    )
    monkeypatch.setattr(
        handler,
        "resolve_postgres_options",
        lambda event: {
            "host": "db.example.com",
            "port": 5432,
            "database": "analytics",
            "user": "loader",
            "password": "secret",
        },
    )
    monkeypatch.setattr(handler, "connect_to_postgres", lambda options: connection)
    monkeypatch.setattr(
        handler,
        "write_loaded_datasets_to_postgres",
        fake_write_loaded_datasets_to_postgres,
    )

    with pytest.raises(RuntimeError, match="write failed"):
        handler.lambda_handler(
            {
                "bucket": "bucket",
                "data_date": DATA_DATE,
                "platforms": ["x"],
                "datasets": ["daily_users_metric"],
            },
            None,
        )

    assert connection.rollbacks == 1
    assert connection.closes == 1
    assert connection.commits == 0
