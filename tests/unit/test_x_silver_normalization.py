import importlib.util
from pathlib import Path


HANDLER_PATH = (
    Path(__file__).resolve().parents[2]
    / "lambdas"
    / "x_silver_normalization"
    / "handler.py"
)
SPEC = importlib.util.spec_from_file_location("x_silver_normalization_handler", HANDLER_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


DATA_DATE = "2026-05-20"
INGEST_DATE = "2026-05-21"
PROCESSED_AT_UTC = "2026-05-21T10:00:00Z"


def test_parse_iso_timestamp():
    assert handler.parse_iso_timestamp("2026-05-20T08:14:22Z").endswith("Z")
    assert handler.parse_iso_timestamp("invalid") is None
    assert handler.parse_iso_timestamp(None) is None


def test_extract_date_parts():
    parts = handler.extract_date_parts("2026-05-20T08:14:22Z")

    assert parts["year"] == "2026"
    assert parts["month"] == "05"
    assert parts["day"] == "20"


def test_infer_x_post_type():
    assert handler.infer_x_post_type({}) == "tweet"
    assert (
        handler.infer_x_post_type({"referenced_tweets": [{"type": "retweeted"}]})
        == "retweet"
    )
    assert (
        handler.infer_x_post_type({"referenced_tweets": [{"type": "replied_to"}]})
        == "reply"
    )
    assert (
        handler.infer_x_post_type({"referenced_tweets": [{"type": "quoted"}]})
        == "quote"
    )


def test_extract_x_hashtags():
    assert handler.extract_x_hashtags({"hashtags": ["AWS", "#Cloud", "aws"]}) == [
        "aws",
        "cloud",
    ]
    assert handler.extract_x_hashtags(
        {"hashtags": [{"tag": "AWS"}, {"text": "#Cloud"}, {"tag": "aws"}]}
    ) == ["aws", "cloud"]
    assert handler.extract_x_hashtags(
        {"entities": {"hashtags": [{"tag": "AWS"}, {"text": "#Cloud"}]}}
    ) == ["aws", "cloud"]


def test_normalize_x_users_deduplicates_and_maps_fields():
    tweets = [
        {
            "user": {
                "id": 42,
                "username": "  Alice  ",
                "followers_count": "12",
                "verified": "true",
            }
        },
        {"user": {"id": "42", "username": "duplicate"}},
    ]

    users = handler.normalize_x_users(
        tweets, DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )

    assert len(users) == 1
    assert users[0]["platform"] == "X"
    assert users[0]["username"] == "Alice"
    assert users[0]["followers_count"] == 12
    assert users[0]["is_verified"] is True
    assert users[0]["karma_score"] is None
    assert users[0]["user_id"]
    assert users[0]["user_id"] == handler.normalize_x_users(
        tweets, DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )[0]["user_id"]


def test_normalize_x_posts_maps_fields():
    tweet = {
        "id": 101,
        "text": "  Hello &amp;   world  ",
        "created_at": "2026-05-20T08:14:22Z",
        "user": {"id": 42, "username": "alice"},
        "metrics": {
            "like_count": "7",
            "retweet_count": "2",
            "reply_count": "3",
            "quote_count": "1",
        },
        "lang": "en",
        "source": "X Web App",
        "referenced_tweets": [{"type": "quoted", "id": "100"}],
    }

    posts = handler.normalize_x_posts(
        [tweet], DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )

    assert len(posts) == 1
    assert posts[0]["source_post_id"] == "101"
    assert posts[0]["platform"] == "X"
    assert posts[0]["post_type"] == "quote"
    assert posts[0]["content_text"] == "Hello & world"
    assert posts[0]["like_count"] == 7
    assert posts[0]["retweet_count"] == 2
    assert posts[0]["reply_count"] == 3
    assert posts[0]["quote_count"] == 1
    assert (posts[0]["year"], posts[0]["month"], posts[0]["day"]) == (
        "2026",
        "05",
        "20",
    )
    assert posts[0]["post_id"]
    assert posts[0]["post_id"] == handler.normalize_x_posts(
        [tweet], DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )[0]["post_id"]


def test_normalize_x_post_tags_deduplicates_tags():
    tweets = [
        {
            "id": "101",
            "created_at": "2026-05-20T08:14:22Z",
            "hashtags": ["AWS", "#aws", "#Cloud"],
        }
    ]

    post_tags = handler.normalize_x_post_tags(
        tweets, DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )

    assert [row["tag"] for row in post_tags] == ["aws", "cloud"]
    assert all(row["platform"] == "X" for row in post_tags)
    assert all(row["tag_type"] == "hashtag" for row in post_tags)
    assert all(
        (row["year"], row["month"], row["day"]) == ("2026", "05", "20")
        for row in post_tags
    )


def test_normalize_x_post_relations_keeps_only_valid_unique_relations():
    tweets = [
        {
            "id": "101",
            "created_at": "2026-05-20T08:14:22Z",
            "referenced_tweets": [
                {"type": "retweeted", "id": "123"},
                {"type": "retweeted", "id": "123"},
                {"type": "unsupported", "id": "456"},
                {"type": "quoted"},
            ],
        }
    ]

    relations = handler.normalize_x_post_relations(
        tweets, DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )

    assert len(relations) == 1
    assert relations[0]["related_source_post_id"] == "123"
    assert relations[0]["relation_type"] == "retweeted"


def test_calculate_data_quality_score():
    quality = handler.calculate_data_quality_score(
        [
            {"a": 1, "b": None, "c": ""},
            {"a": 0, "b": False, "c": "value"},
        ]
    )

    assert quality == {
        "row_count": 2,
        "column_count": 3,
        "non_null_cell_count": 4,
        "total_cell_count": 6,
        "data_quality_score": 66.67,
    }


def test_build_data_quality_report_rows():
    normalized_tables = {
        "users": [{"user_id": "1", "platform": "X"}],
        "posts": [{"post_id": "2", "platform": "X"}],
        "post_tags": [],
        "post_relations": [],
    }

    report = handler.build_data_quality_report_rows(
        normalized_tables, DATA_DATE, INGEST_DATE, PROCESSED_AT_UTC
    )

    assert len(report) == 4
    assert {row["table_name"] for row in report} == {
        "users",
        "posts",
        "post_tags",
        "post_relations",
    }
    assert all(row["platform"] == "X" for row in report)
    assert all("data_quality_score" in row for row in report)
