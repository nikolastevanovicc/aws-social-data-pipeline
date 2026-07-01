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


def test_lambda_handler():
    response = handler.lambda_handler(
        {
            "data_date": DATA_DATE,
            "platforms": ["x"],
            "datasets": ["daily_users_metric"],
            "mode": "replace_date",
        },
        None,
    )

    assert response["source"] == "gold-to-postgres"
    assert response["status"] == "configured"
    assert response["data_date"] == DATA_DATE
    assert response["platforms"] == ["x"]
    assert response["datasets_by_platform"] == {"x": ["daily_users_metric"]}
