#!/usr/bin/env python3
import datetime as dt
import importlib.util
import os
from pathlib import Path


SEED_DATES = (
    "2026-05-18",
    "2026-05-19",
    "2026-05-20",
)

EXPECTED_VIEWS = (
    "vw_hn_daily_activity",
    "vw_x_daily_activity",
    "vw_hn_top_posts",
    "vw_hn_top_users",
    "vw_x_top_posts",
    "vw_x_top_users",
    "vw_x_hashtag_trends",
    "vw_data_quality_score",
)

HN_STORIES = (
    (
        "vector-database-indexing",
        "Designing Vector Database Indexes for Production Search",
        "https://example.com/vector-indexing",
        "arjun_ml",
    ),
    (
        "postgres-event-streams",
        "How We Run Event Streams Through PostgreSQL",
        "https://example.com/postgres-event-streams",
        "data_marta",
    ),
    (
        "python-cdk-observability",
        "Practical Observability for Python CDK Pipelines",
        "https://example.com/cdk-observability",
        "ops_kenji",
    ),
)

HN_JOBS = (
    (
        "analytics-platform-engineer",
        "Acme Data is hiring an Analytics Platform Engineer",
        "https://example.com/jobs/analytics-platform-engineer",
        "acme_data",
    ),
    (
        "backend-infra-engineer",
        "Northwind Labs is hiring a Backend Infrastructure Engineer",
        "https://example.com/jobs/backend-infra-engineer",
        "northwind_labs",
    ),
)

HN_TOP_USERS = (
    ("u-paul-g", "paul_g", 212340),
    ("u-lina-systems", "lina_systems", 178920),
    ("u-cassandraq", "cassandraq", 151480),
)

HN_BOTTOM_USERS = (
    ("u-newreader42", "newreader42", 3),
    ("u-sandbox_beta", "sandbox_beta", 8),
    ("u-lowkarmaops", "lowkarmaops", 12),
)

X_USERS = (
    ("x-cloud_digest", "cloud_digest", "Cloud Digest", 825000, 410, True),
    ("x-data_makers", "data_makers", "Data Makers", 612000, 725, True),
    ("x-ml_ops_daily", "ml_ops_daily", "MLOps Daily", 384000, 690, False),
)

X_POSTS = (
    (
        "x-cloud_digest",
        "cloud_digest",
        "A practical checklist for keeping local analytics demos realistic.",
        12800,
        2150,
        480,
        310,
    ),
    (
        "x-data_makers",
        "data_makers",
        "PostgreSQL views make Superset dashboards easier to maintain.",
        9400,
        1705,
        390,
        260,
    ),
    (
        "x-ml_ops_daily",
        "ml_ops_daily",
        "Batch metrics still need strong data quality signals.",
        7600,
        1320,
        275,
        190,
    ),
)

X_HASHTAGS = (
    ("DataEngineering", "hashtag", 430),
    ("PostgreSQL", "hashtag", 365),
    ("Superset", "hashtag", 285),
    ("MLOps", "hashtag", 240),
)

SOURCE_TABLE_COLUMN_COUNTS = {
    "hn_daily_item_counts": 12,
    "hn_daily_users_metric": 8,
    "hn_top_story_posts": 15,
    "hn_top_job_posts": 15,
    "hn_top_users_by_karma": 11,
    "hn_bottom_users_by_karma": 11,
    "x_daily_users_metric": 8,
    "x_top_users_by_followers": 14,
    "x_top_posts_by_engagement": 17,
    "x_hashtag_trends": 10,
}


def repo_root():
    return Path(__file__).resolve().parents[1]


def load_handler_module():
    handler_path = repo_root() / "lambdas" / "gold_to_postgres_loader" / "handler.py"
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


def date_context(data_date):
    parsed_date = dt.date.fromisoformat(data_date)
    processed_at = dt.datetime.combine(
        parsed_date,
        dt.time(hour=13, minute=30, tzinfo=dt.timezone.utc),
    )
    silver_processed_at = processed_at - dt.timedelta(minutes=20)
    return {
        "date": parsed_date,
        "year": f"{parsed_date.year:04d}",
        "month": f"{parsed_date.month:02d}",
        "day": f"{parsed_date.day:02d}",
        "ingest_date": parsed_date + dt.timedelta(days=1),
        "silver_processed_at_utc": silver_processed_at,
        "gold_processed_at_utc": processed_at,
    }


def common_metric_fields(context, platform):
    return {
        "date": context["date"],
        "platform": platform,
        "year": context["year"],
        "month": context["month"],
        "day": context["day"],
        "gold_processed_at_utc": context["gold_processed_at_utc"],
    }


def build_hn_daily_item_counts(context, day_index):
    story_count = 116 + day_index * 9
    ask_count = 18 + day_index * 2
    comment_count = 920 + day_index * 75
    job_count = 7 + day_index
    poll_count = 1
    return [
        {
            **common_metric_fields(context, "HackerNews"),
            "story_count": story_count,
            "ask_count": ask_count,
            "comment_count": comment_count,
            "job_count": job_count,
            "poll_count": poll_count,
            "total_count": (
                story_count + ask_count + comment_count + job_count + poll_count
            ),
        }
    ]


def build_hn_daily_users_metric(context, day_index):
    return [
        {
            **common_metric_fields(context, "HackerNews"),
            "total_users": 24800 + day_index * 520,
            "active_users": 3820 + day_index * 210,
        }
    ]


def build_hn_top_story_posts(context, day_index):
    rows = []
    for rank, (slug, title, url, username) in enumerate(HN_STORIES, start=1):
        score = 520 - rank * 48 + day_index * 37
        rows.append(
            {
                **common_metric_fields(context, "HackerNews"),
                "rank": rank,
                "post_id": f"hn-story-{context['day']}-{rank}",
                "source_post_id": f"{42000000 + day_index * 100 + rank}",
                "author_user_id": f"hn-user-{username}",
                "author_username": username,
                "post_type": "story",
                "title": title,
                "url": f"{url}?demo_day={context['day']}&topic={slug}",
                "score": score,
            }
        )
    return rows


def build_hn_top_job_posts(context, day_index):
    rows = []
    for rank, (slug, title, url, username) in enumerate(HN_JOBS, start=1):
        rows.append(
            {
                **common_metric_fields(context, "HackerNews"),
                "rank": rank,
                "post_id": f"hn-job-{context['day']}-{rank}",
                "source_post_id": f"{42100000 + day_index * 100 + rank}",
                "author_user_id": f"hn-user-{username}",
                "author_username": username,
                "post_type": "job",
                "title": title,
                "url": f"{url}?demo_day={context['day']}&role={slug}",
                "score": 96 - rank * 11 + day_index * 6,
            }
        )
    return rows


def build_hn_top_users_by_karma(context, day_index):
    rows = []
    for rank, (user_id, username, karma_score) in enumerate(HN_TOP_USERS, start=1):
        rows.append(
            {
                **common_metric_fields(context, "HackerNews"),
                "rank": rank,
                "user_id": user_id,
                "source_user_id": username,
                "username": username,
                "karma_score": karma_score + day_index * (1200 - rank * 110),
            }
        )
    return rows


def build_hn_bottom_users_by_karma(context, day_index):
    rows = []
    for rank, (user_id, username, karma_score) in enumerate(HN_BOTTOM_USERS, start=1):
        rows.append(
            {
                **common_metric_fields(context, "HackerNews"),
                "rank": rank,
                "user_id": user_id,
                "source_user_id": username,
                "username": username,
                "karma_score": karma_score + day_index,
            }
        )
    return rows


def data_quality_row(context, table_name, platform, row_count, score_offset):
    column_count = SOURCE_TABLE_COLUMN_COUNTS[table_name]
    total_cell_count = row_count * column_count
    data_quality_score = round(0.99 - score_offset, 2)
    return {
        "table_name": table_name,
        "platform": platform,
        "data_date": context["date"],
        "ingest_date": context["ingest_date"],
        "row_count": row_count,
        "column_count": column_count,
        "non_null_cell_count": int(total_cell_count * data_quality_score),
        "total_cell_count": total_cell_count,
        "data_quality_score": data_quality_score,
        "silver_processed_at_utc": context["silver_processed_at_utc"],
        "gold_processed_at_utc": context["gold_processed_at_utc"],
    }


def build_hn_data_quality_summary(context, day_index):
    return [
        data_quality_row(context, "hn_daily_item_counts", "HackerNews", 1, 0.02),
        data_quality_row(context, "hn_daily_users_metric", "HackerNews", 1, 0.03),
        data_quality_row(context, "hn_top_story_posts", "HackerNews", 3, 0.01),
        data_quality_row(context, "hn_top_job_posts", "HackerNews", 2, 0.04),
        data_quality_row(
            context,
            "hn_top_users_by_karma",
            "HackerNews",
            3,
            0.05 - day_index * 0.01,
        ),
        data_quality_row(
            context,
            "hn_bottom_users_by_karma",
            "HackerNews",
            3,
            0.07 - day_index * 0.01,
        ),
    ]


def build_x_daily_users_metric(context, day_index):
    return [
        {
            **common_metric_fields(context, "X"),
            "total_users": 980000 + day_index * 16500,
            "active_users": 214000 + day_index * 7200,
        }
    ]


def build_x_top_users_by_followers(context, day_index):
    rows = []
    for rank, user in enumerate(X_USERS, start=1):
        user_id, username, display_name, followers, following, verified = user
        rows.append(
            {
                **common_metric_fields(context, "X"),
                "rank": rank,
                "user_id": user_id,
                "source_user_id": username,
                "username": username,
                "display_name": display_name,
                "followers_count": followers + day_index * (2800 - rank * 240),
                "following_count": following + day_index * 6,
                "is_verified": verified,
            }
        )
    return rows


def build_x_top_posts_by_engagement(context, day_index):
    rows = []
    for rank, post in enumerate(X_POSTS, start=1):
        author_user_id, author_username, content_text, likes, retweets, replies, quotes = (
            post
        )
        like_count = likes + day_index * (850 - rank * 90)
        retweet_count = retweets + day_index * (210 - rank * 18)
        reply_count = replies + day_index * (44 - rank * 5)
        quote_count = quotes + day_index * (36 - rank * 4)
        rows.append(
            {
                **common_metric_fields(context, "X"),
                "rank": rank,
                "post_id": f"x-post-{context['day']}-{rank}",
                "source_post_id": f"{9900000000 + day_index * 100 + rank}",
                "author_user_id": author_user_id,
                "author_username": author_username,
                "post_type": "tweet",
                "content_text": content_text,
                "like_count": like_count,
                "retweet_count": retweet_count,
                "reply_count": reply_count,
                "quote_count": quote_count,
                "engagement_count": (
                    like_count + retweet_count + reply_count + quote_count
                ),
            }
        )
    return rows


def build_x_hashtag_trends(context, day_index):
    rows = []
    for rank, (tag, tag_type, post_count) in enumerate(X_HASHTAGS, start=1):
        rows.append(
            {
                **common_metric_fields(context, "X"),
                "rank": rank,
                "tag": tag,
                "tag_type": tag_type,
                "post_count": post_count + day_index * (34 - rank * 3),
            }
        )
    return rows


def build_x_data_quality_summary(context, day_index):
    return [
        data_quality_row(context, "x_daily_users_metric", "X", 1, 0.02),
        data_quality_row(context, "x_top_users_by_followers", "X", 3, 0.01),
        data_quality_row(context, "x_top_posts_by_engagement", "X", 3, 0.03),
        data_quality_row(
            context,
            "x_hashtag_trends",
            "X",
            4,
            0.06 - day_index * 0.01,
        ),
    ]


def build_loaded_datasets_for_date(data_date):
    day_index = SEED_DATES.index(data_date)
    context = date_context(data_date)
    return {
        "hacker-news": {
            "daily_item_counts": {
                "postgres_table": "hn_daily_item_counts",
                "rows": build_hn_daily_item_counts(context, day_index),
            },
            "daily_users_metric": {
                "postgres_table": "hn_daily_users_metric",
                "rows": build_hn_daily_users_metric(context, day_index),
            },
            "top_story_posts": {
                "postgres_table": "hn_top_story_posts",
                "rows": build_hn_top_story_posts(context, day_index),
            },
            "top_job_posts": {
                "postgres_table": "hn_top_job_posts",
                "rows": build_hn_top_job_posts(context, day_index),
            },
            "top_users_by_karma": {
                "postgres_table": "hn_top_users_by_karma",
                "rows": build_hn_top_users_by_karma(context, day_index),
            },
            "bottom_users_by_karma": {
                "postgres_table": "hn_bottom_users_by_karma",
                "rows": build_hn_bottom_users_by_karma(context, day_index),
            },
            "data_quality_summary": {
                "postgres_table": "hn_data_quality_summary",
                "rows": build_hn_data_quality_summary(context, day_index),
            },
        },
        "x": {
            "daily_users_metric": {
                "postgres_table": "x_daily_users_metric",
                "rows": build_x_daily_users_metric(context, day_index),
            },
            "top_users_by_followers": {
                "postgres_table": "x_top_users_by_followers",
                "rows": build_x_top_users_by_followers(context, day_index),
            },
            "top_posts_by_engagement": {
                "postgres_table": "x_top_posts_by_engagement",
                "rows": build_x_top_posts_by_engagement(context, day_index),
            },
            "hashtag_trends": {
                "postgres_table": "x_hashtag_trends",
                "rows": build_x_hashtag_trends(context, day_index),
            },
            "data_quality_summary": {
                "postgres_table": "x_data_quality_summary",
                "rows": build_x_data_quality_summary(context, day_index),
            },
        },
    }


def validate_dataset_columns(handler, loaded_datasets):
    for platform_results in loaded_datasets.values():
        for dataset_result in platform_results.values():
            table_name = dataset_result["postgres_table"]
            expected_columns = set(handler.POSTGRES_TABLE_COLUMNS[table_name])
            for row in dataset_result["rows"]:
                actual_columns = set(row)
                if actual_columns != expected_columns:
                    missing = sorted(expected_columns - actual_columns)
                    extra = sorted(actual_columns - expected_columns)
                    raise AssertionError(
                        f"{table_name} row does not match loader columns. "
                        f"Missing: {missing}. Extra: {extra}."
                    )


def execute_views_sql(connection):
    views_sql_path = repo_root() / "database" / "views.sql"
    statements = [
        statement.strip()
        for statement in views_sql_path.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    cursor = connection.cursor()
    for statement in statements:
        cursor.execute(statement)


def fetch_view_counts(connection):
    counts = {}
    cursor = connection.cursor()
    for view_name in EXPECTED_VIEWS:
        cursor.execute(f"SELECT COUNT(*) FROM {view_name}")
        counts[view_name] = cursor.fetchone()[0]
    return counts


def assert_non_empty_views(view_counts):
    empty_views = [
        view_name
        for view_name, row_count in view_counts.items()
        if row_count == 0
    ]
    if empty_views:
        raise AssertionError(
            "Expected analytics view(s) to contain rows: "
            + ", ".join(empty_views)
        )


def print_report(view_counts):
    print("Local demo gold data seeded successfully.")
    print("Seeded dates:")
    for data_date in SEED_DATES:
        print(f"- {data_date}")

    print()
    print("Validated views:")
    for view_name in EXPECTED_VIEWS:
        print(f"- {view_name}: {view_counts[view_name]} rows")


def main():
    handler = load_handler_module()
    postgres_options = handler.resolve_postgres_options(build_postgres_event())

    connection = None
    try:
        connection = handler.connect_to_postgres(postgres_options)
        for data_date in SEED_DATES:
            loaded_datasets = build_loaded_datasets_for_date(data_date)
            validate_dataset_columns(handler, loaded_datasets)
            handler.write_loaded_datasets_to_postgres(
                connection,
                loaded_datasets,
                data_date,
            )

        execute_views_sql(connection)
        view_counts = fetch_view_counts(connection)
        assert_non_empty_views(view_counts)
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()

    print_report(view_counts)


if __name__ == "__main__":
    main()
