#!/usr/bin/env python3
import os
from pathlib import Path

import pg8000.dbapi


EXPECTED_VIEWS = {
    "vw_hn_daily_activity",
    "vw_x_daily_activity",
    "vw_hn_top_posts",
    "vw_hn_top_users",
    "vw_x_top_posts",
    "vw_x_top_users",
    "vw_x_hashtag_trends",
    "vw_data_quality_score",
}


def postgres_options():
    return {
        "host": os.getenv("POSTGRES_HOST") or "localhost",
        "port": int(os.getenv("POSTGRES_PORT") or "5432"),
        "database": (
            os.getenv("POSTGRES_DATABASE")
            or os.getenv("POSTGRES_DB")
            or "social_analytics"
        ),
        "user": os.getenv("POSTGRES_USER") or "superset",
        "password": os.getenv("POSTGRES_PASSWORD") or "superset",
    }


def read_views_sql():
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "database" / "views.sql"


def execute_views_sql(connection, views_sql_path):
    cursor = connection.cursor()
    statements = [
        statement.strip()
        for statement in views_sql_path.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    for statement in statements:
        cursor.execute(statement)


def fetch_existing_views(connection):
    cursor = connection.cursor()
    expected_view_names = sorted(EXPECTED_VIEWS)
    placeholders = ", ".join(["%s"] * len(expected_view_names))
    cursor.execute(
        f"""
        SELECT table_name
        FROM information_schema.views
        WHERE table_schema = 'public'
          AND table_name IN ({placeholders})
        """,
        tuple(expected_view_names),
    )
    return {row[0] for row in cursor.fetchall()}


def assert_expected_views_exist(existing_views):
    missing_views = sorted(EXPECTED_VIEWS - existing_views)
    if missing_views:
        raise AssertionError(
            "Missing analytics view(s): " + ", ".join(missing_views)
        )


def main():
    options = postgres_options()
    views_sql_path = read_views_sql()

    connection = None
    try:
        connection = pg8000.dbapi.connect(**options)
        execute_views_sql(connection, views_sql_path)
        existing_views = fetch_existing_views(connection)
        assert_expected_views_exist(existing_views)
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()

    print("Analytics views smoke test passed.")
    print("Applied SQL:")
    print(f"- {views_sql_path}")
    print("Validated views:")
    for view_name in sorted(EXPECTED_VIEWS):
        print(f"- {view_name}")


if __name__ == "__main__":
    main()
