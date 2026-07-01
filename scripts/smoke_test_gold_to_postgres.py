#!/usr/bin/env python3
import datetime as dt
import importlib.util
import os
from pathlib import Path


DATA_DATE = "2026-05-20"


def load_handler_module():
    repo_root = Path(__file__).resolve().parents[1]
    handler_path = repo_root / "lambdas" / "gold_to_postgres_loader" / "handler.py"
    spec = importlib.util.spec_from_file_location(
        "gold_to_postgres_loader_handler",
        handler_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load handler module from {handler_path}")

    handler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(handler)
    return handler


def build_postgres_event():
    return {
        "postgres_host": os.getenv("POSTGRES_HOST") or "localhost",
        "postgres_port": os.getenv("POSTGRES_PORT") or "5432",
        "postgres_database": (
            os.getenv("POSTGRES_DATABASE")
            or os.getenv("POSTGRES_DB")
            or "social_analytics"
        ),
        "postgres_user": os.getenv("POSTGRES_USER") or "superset",
        "postgres_password": os.getenv("POSTGRES_PASSWORD") or "superset",
    }


def build_loaded_datasets():
    data_date = dt.date.fromisoformat(DATA_DATE)
    processed_at = dt.datetime(2026, 5, 20, 12, 0, tzinfo=dt.timezone.utc)

    return {
        "x": {
            "daily_users_metric": {
                "postgres_table": "x_daily_users_metric",
                "rows": [
                    {
                        "date": data_date,
                        "platform": "X",
                        "year": "2026",
                        "month": "05",
                        "day": "20",
                        "gold_processed_at_utc": processed_at,
                        "total_users": 1250,
                        "active_users": 870,
                    },
                    {
                        "date": data_date,
                        "platform": "X",
                        "year": "2026",
                        "month": "05",
                        "day": "20",
                        "gold_processed_at_utc": processed_at,
                        "total_users": 1265,
                        "active_users": 884,
                    },
                ],
            }
        },
        "hacker-news": {
            "daily_item_counts": {
                "postgres_table": "hn_daily_item_counts",
                "rows": [
                    {
                        "date": data_date,
                        "platform": "HackerNews",
                        "year": "2026",
                        "month": "05",
                        "day": "20",
                        "gold_processed_at_utc": processed_at,
                        "story_count": 42,
                        "ask_count": 8,
                        "comment_count": 315,
                        "job_count": 3,
                        "poll_count": 1,
                        "total_count": 369,
                    }
                ],
            }
        },
    }


def fetch_count(connection, table_name, platform):
    sql = f"SELECT COUNT(*) FROM {table_name} WHERE date = %s AND platform = %s"
    cursor = connection.cursor()
    cursor.execute(sql, (dt.date.fromisoformat(DATA_DATE), platform))
    return cursor.fetchone()[0]


def assert_count(connection, table_name, platform, expected_count):
    actual_count = fetch_count(connection, table_name, platform)
    if actual_count != expected_count:
        raise AssertionError(
            f"{table_name} expected {expected_count} row(s) for "
            f"{DATA_DATE}/{platform}, found {actual_count}"
        )
    return actual_count


def main():
    handler = load_handler_module()
    postgres_options = handler.resolve_postgres_options(build_postgres_event())
    loaded_datasets = build_loaded_datasets()

    connection = None
    try:
        connection = handler.connect_to_postgres(postgres_options)
        handler.write_loaded_datasets_to_postgres(
            connection,
            loaded_datasets,
            DATA_DATE,
        )
        counts = {
            "x_daily_users_metric": assert_count(
                connection,
                "x_daily_users_metric",
                "X",
                2,
            ),
            "hn_daily_item_counts": assert_count(
                connection,
                "hn_daily_item_counts",
                "HackerNews",
                1,
            ),
        }
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()

    print("Gold-to-Postgres smoke test passed.")
    print("Inserted rows:")
    print(f"- x_daily_users_metric: {counts['x_daily_users_metric']}")
    print(f"- hn_daily_item_counts: {counts['hn_daily_item_counts']}")


if __name__ == "__main__":
    main()
