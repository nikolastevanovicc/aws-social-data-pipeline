import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_handler(relative_path, module_name):
    handler_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, handler_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hn_gold = load_handler(
    Path("lambdas") / "hn_gold_aggregation" / "handler.py",
    "hn_gold_handler",
)
x_gold = load_handler(
    Path("lambdas") / "x_gold_aggregation" / "handler.py",
    "x_gold_handler",
)

sys.modules.setdefault(
    "boto3",
    types.SimpleNamespace(client=lambda *_args, **_kwargs: object()),
)
botocore_module = types.ModuleType("botocore")
botocore_exceptions_module = types.ModuleType("botocore.exceptions")


class FakeClientError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.response = kwargs.get("response", {"Error": {"Code": "Fake"}})


botocore_exceptions_module.ClientError = FakeClientError
sys.modules.setdefault("botocore", botocore_module)
sys.modules.setdefault("botocore.exceptions", botocore_exceptions_module)
sys.modules.setdefault("pandas", types.ModuleType("pandas"))
sys.modules.setdefault("pyarrow", types.ModuleType("pyarrow"))
sys.modules.setdefault("pyarrow.parquet", types.ModuleType("pyarrow.parquet"))
hn_silver = load_handler(
    Path("lambdas") / "hn_silver_normalization" / "handler.py",
    "hn_silver_handler",
)


PROCESSED_AT_UTC = "2026-05-21T10:00:00Z"


def test_hn_daily_item_counts_groups_required_types():
    posts = [
        {"platform": "HackerNews", "data_date": "2026-05-20", "post_type": "story"},
        {"platform": "HackerNews", "data_date": "2026-05-20", "post_type": "story"},
        {"platform": "HackerNews", "data_date": "2026-05-20", "post_type": "job"},
        {"platform": "HackerNews", "data_date": "2026-05-20", "post_type": "comment"},
        {"platform": "X", "data_date": "2026-05-20", "post_type": "story"},
    ]

    rows = hn_gold.build_daily_item_counts(posts, PROCESSED_AT_UTC)

    assert rows == [
        {
            "date": "2026-05-20",
            "platform": "HackerNews",
            "year": "2026",
            "month": "05",
            "day": "20",
            "gold_processed_at_utc": PROCESSED_AT_UTC,
            "story_count": 2,
            "ask_count": 0,
            "comment_count": 1,
            "job_count": 1,
            "poll_count": 0,
            "total_count": 4,
        }
    ]


def test_hn_silver_users_include_karma_from_profiles():
    users = hn_silver.normalize_hn_users(
        items=[{"author": "alice"}, {"author": "Alice"}, {"author": "bob"}],
        data_date="2026-05-20",
        ingest_date="2026-05-21",
        silver_processed_at_utc=PROCESSED_AT_UTC,
        user_profiles={
            "alice": {"karma": 123, "created": 1735689600},
            "bob": {"karma": "7"},
        },
    )

    users_by_name = {user["username"].lower(): user for user in users}

    assert len(users) == 2
    assert users_by_name["alice"]["karma_score"] == 123
    assert users_by_name["alice"]["user_created_at_utc"] == "2025-01-01T00:00:00Z"
    assert users_by_name["bob"]["karma_score"] == 7
    assert (users_by_name["alice"]["year"], users_by_name["alice"]["month"]) == (
        "2026",
        "05",
    )


def test_hn_top_posts_by_score_filters_type_and_ranks():
    posts = [
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "post_type": "story",
            "source_post_id": "1",
            "score": 10,
            "title": "First",
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "post_type": "story",
            "source_post_id": "2",
            "score": 30,
            "title": "Second",
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "post_type": "job",
            "source_post_id": "3",
            "score": 100,
            "title": "Job",
        },
    ]

    rows = hn_gold.build_top_posts_by_score(posts, "story", PROCESSED_AT_UTC)

    assert [row["source_post_id"] for row in rows] == ["2", "1"]
    assert [row["rank"] for row in rows] == [1, 2]
    assert all(row["post_type"] == "story" for row in rows)


def test_hn_top_users_by_karma_skips_missing_karma():
    users = [
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "username": "alice",
            "karma_score": 42,
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "username": "bob",
            "karma_score": None,
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "username": "carol",
            "karma_score": 100,
        },
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "username": "x-user",
            "karma_score": 500,
        },
    ]

    top_rows = hn_gold.build_top_users_by_karma(
        users, PROCESSED_AT_UTC, descending=True
    )
    bottom_rows = hn_gold.build_top_users_by_karma(
        users, PROCESSED_AT_UTC, descending=False
    )

    assert [row["username"] for row in top_rows] == ["carol", "alice"]
    assert [row["username"] for row in bottom_rows] == ["alice", "carol"]


def test_x_top_users_by_followers_ranks_users():
    users = [
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "user_id": "u1",
            "username": "alice",
            "followers_count": 10,
        },
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "user_id": "u2",
            "username": "bob",
            "followers_count": 50,
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "user_id": "u3",
            "username": "hn-user",
            "followers_count": 500,
        },
    ]

    rows = x_gold.build_top_users_by_followers(users, PROCESSED_AT_UTC)

    assert [row["username"] for row in rows] == ["bob", "alice"]
    assert [row["rank"] for row in rows] == [1, 2]


def test_x_top_posts_by_engagement_sums_metrics():
    posts = [
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "source_post_id": "1",
            "like_count": 1,
            "retweet_count": 2,
            "reply_count": 3,
            "quote_count": 4,
        },
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "source_post_id": "2",
            "like_count": 20,
            "retweet_count": 0,
            "reply_count": 0,
            "quote_count": 0,
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "source_post_id": "3",
            "like_count": 100,
            "retweet_count": 100,
            "reply_count": 100,
            "quote_count": 100,
        },
    ]

    rows = x_gold.build_top_posts_by_engagement(posts, PROCESSED_AT_UTC)

    assert [row["source_post_id"] for row in rows] == ["2", "1"]
    assert [row["engagement_count"] for row in rows] == [20, 10]


def test_x_hashtag_trends_counts_tags_per_day():
    post_tags = [
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "tag": "AWS",
            "tag_type": "hashtag",
        },
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "tag": "aws",
            "tag_type": "hashtag",
        },
        {
            "platform": "X",
            "data_date": "2026-05-20",
            "tag": "cloud",
            "tag_type": "hashtag",
        },
        {
            "platform": "X",
            "data_date": "2026-05-21",
            "tag": "aws",
            "tag_type": "hashtag",
        },
        {
            "platform": "HackerNews",
            "data_date": "2026-05-20",
            "tag": "ignored",
            "tag_type": "hashtag",
        },
    ]

    rows = x_gold.build_hashtag_trends(post_tags, PROCESSED_AT_UTC)
    rows_0520 = [row for row in rows if row["date"] == "2026-05-20"]

    assert [(row["tag"], row["post_count"]) for row in rows_0520] == [
        ("aws", 2),
        ("cloud", 1),
    ]


def test_hn_gold_reads_requested_hacker_news_silver_partition(monkeypatch):
    calls = []

    class FakeDataFrame:
        def to_dict(self, orient):
            assert orient == "records"
            return []

    class FakeS3:
        def read_parquet(self, **kwargs):
            calls.append(kwargs)
            return FakeDataFrame()

    monkeypatch.setitem(sys.modules, "awswrangler", types.SimpleNamespace(s3=FakeS3()))

    rows = hn_gold.read_silver_table(
        "bucket-name",
        "silver",
        "users",
        "HackerNews",
        data_date="2026-05-20",
    )

    assert rows == []
    assert (
        calls[0]["path"]
        == "s3://bucket-name/silver/users/platform=HackerNews/year=2026/month=05/day=20/"
    )
    assert calls[0]["dataset"] is True
    assert "partition_filter" not in calls[0]


def test_hn_gold_lambda_reads_only_requested_silver_partition_paths(monkeypatch):
    calls = []

    class FakeDataFrame:
        def to_dict(self, orient):
            assert orient == "records"
            return []

    class FakeS3:
        def read_parquet(self, **kwargs):
            calls.append(kwargs)
            return FakeDataFrame()

    monkeypatch.setitem(sys.modules, "awswrangler", types.SimpleNamespace(s3=FakeS3()))
    monkeypatch.setattr(
        hn_gold,
        "write_hn_gold_tables",
        lambda *_args, **_kwargs: {},
    )

    result = hn_gold.lambda_handler(
        {
            "bucket": "bucket-name",
            "silver_prefix": "silver",
            "gold_prefix": "gold/hacker-news",
            "data_date": "2026-05-20",
            "mode": "overwrite_partitions",
        },
        types.SimpleNamespace(aws_request_id="request-1"),
    )

    paths = [call["path"] for call in calls]

    assert result["status"] == "success"
    assert paths == [
        "s3://bucket-name/silver/users/platform=HackerNews/year=2026/month=05/day=20/",
        "s3://bucket-name/silver/posts/platform=HackerNews/year=2026/month=05/day=20/",
        "s3://bucket-name/silver/post_tags/platform=HackerNews/year=2026/month=05/day=20/",
        "s3://bucket-name/silver/post_relations/platform=HackerNews/year=2026/month=05/day=20/",
        "s3://bucket-name/silver/data_quality_report/platform=HackerNews/data_date=2026-05-20/",
    ]
    assert "s3://bucket-name/silver/users/" not in paths
    assert "s3://bucket-name/silver/posts/" not in paths


def test_x_gold_reads_only_x_silver_partitions(monkeypatch):
    calls = []

    class FakeDataFrame:
        def to_dict(self, orient):
            assert orient == "records"
            return []

    class FakeS3:
        def read_parquet(self, **kwargs):
            calls.append(kwargs)
            return FakeDataFrame()

    monkeypatch.setitem(sys.modules, "awswrangler", types.SimpleNamespace(s3=FakeS3()))

    rows = x_gold.read_silver_table("bucket-name", "silver", "users", "X")

    assert rows == []
    assert calls[0]["path"] == "s3://bucket-name/silver/users/"
    assert calls[0]["dataset"] is True
    assert calls[0]["partition_filter"]({"platform": "X"}) is True
    assert calls[0]["partition_filter"]({"platform": "HackerNews"}) is False
