import datetime as dt
import html
import os
import re
import uuid


X_PLATFORM = "X"
X_USER_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "social-data-pipeline:x:user")
X_POST_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "social-data-pipeline:x:post")


def utc_now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def extract_date_parts(created_at_utc):
    normalized = parse_iso_timestamp(created_at_utc)
    if normalized is None:
        return {"year": None, "month": None, "day": None}

    parsed = dt.datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    return {
        "year": f"{parsed.year:04d}",
        "month": f"{parsed.month:02d}",
        "day": f"{parsed.day:02d}",
    }


def stable_uuid(namespace, value):
    if value is None or value == "":
        return None

    if not isinstance(namespace, uuid.UUID):
        try:
            namespace = uuid.UUID(str(namespace))
        except (ValueError, TypeError, AttributeError):
            namespace = uuid.uuid5(uuid.NAMESPACE_DNS, str(namespace))

    return str(uuid.uuid5(namespace, str(value)))


def infer_x_post_type(tweet):
    referenced_tweets = tweet.get("referenced_tweets") if isinstance(tweet, dict) else None
    reference_types = {
        reference.get("type")
        for reference in referenced_tweets or []
        if isinstance(reference, dict)
    }

    for reference_type, post_type in (
        ("retweeted", "retweet"),
        ("replied_to", "reply"),
        ("quoted", "quote"),
    ):
        if reference_type in reference_types:
            return post_type

    return "tweet"


def clean_text(value):
    if not isinstance(value, str):
        return None

    cleaned = re.sub(r"\s+", " ", html.unescape(value)).strip()
    return cleaned or None


def safe_int(value):
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def safe_bool(value):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False

    return None


def deduplicate_rows(rows, key_fields):
    seen_keys = set()
    deduplicated = []

    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if key in seen_keys:
            continue

        seen_keys.add(key)
        deduplicated.append(row)

    return deduplicated


def normalize_x_users(tweets, data_date, ingest_date, processed_at_utc):
    normalized_users = []
    seen_users = set()

    for tweet in tweets or []:
        if not isinstance(tweet, dict):
            continue

        user = tweet.get("user")
        if not isinstance(user, dict):
            continue

        raw_source_user_id = user.get("id")
        source_user_id = (
            str(raw_source_user_id)
            if raw_source_user_id is not None and raw_source_user_id != ""
            else None
        )
        username = clean_text(user.get("username"))
        if source_user_id is None and username is None:
            continue

        deduplication_key = (
            (X_PLATFORM, "source_user_id", source_user_id)
            if source_user_id is not None
            else (X_PLATFORM, "username", username)
        )
        if deduplication_key in seen_users:
            continue
        seen_users.add(deduplication_key)

        display_name = clean_text(user.get("display_name"))
        if display_name is None:
            display_name = clean_text(user.get("name"))

        is_verified = safe_bool(user.get("verified"))
        if is_verified is None:
            is_verified = safe_bool(user.get("is_verified"))

        user_id_value = (
            f"{X_PLATFORM}:{source_user_id}"
            if source_user_id is not None
            else f"{X_PLATFORM}:username:{username}"
        )
        normalized_users.append(
            {
                "user_id": stable_uuid(X_USER_NAMESPACE, user_id_value),
                "platform": X_PLATFORM,
                "source_user_id": source_user_id,
                "username": username,
                "display_name": display_name,
                "karma_score": None,
                "followers_count": safe_int(user.get("followers_count")),
                "following_count": safe_int(user.get("following_count")),
                "is_verified": is_verified,
                "user_created_at_utc": parse_iso_timestamp(user.get("created_at")),
                "data_date": data_date,
                "ingest_date": ingest_date,
                "silver_processed_at_utc": processed_at_utc,
            }
        )

    return normalized_users


def normalize_x_posts(tweets, data_date, ingest_date, processed_at_utc):
    normalized_posts = []
    seen_posts = set()

    for tweet in tweets or []:
        if not isinstance(tweet, dict):
            continue

        raw_source_post_id = tweet.get("id")
        if raw_source_post_id is None or raw_source_post_id == "":
            continue
        source_post_id = str(raw_source_post_id)

        deduplication_key = (X_PLATFORM, source_post_id)
        if deduplication_key in seen_posts:
            continue
        seen_posts.add(deduplication_key)

        user = tweet.get("user")
        if not isinstance(user, dict):
            user = {}

        raw_source_user_id = user.get("id")
        source_user_id = (
            str(raw_source_user_id)
            if raw_source_user_id is not None and raw_source_user_id != ""
            else None
        )
        author_username = clean_text(user.get("username"))
        if source_user_id is not None:
            author_user_id = stable_uuid(
                X_USER_NAMESPACE, f"{X_PLATFORM}:{source_user_id}"
            )
        elif author_username is not None:
            author_user_id = stable_uuid(
                X_USER_NAMESPACE, f"{X_PLATFORM}:username:{author_username}"
            )
        else:
            author_user_id = None

        metrics = tweet.get("metrics")
        if not isinstance(metrics, dict):
            metrics = {}

        created_at_utc = parse_iso_timestamp(tweet.get("created_at"))
        date_parts = extract_date_parts(created_at_utc)
        normalized_posts.append(
            {
                "post_id": stable_uuid(
                    X_POST_NAMESPACE, f"{X_PLATFORM}:{source_post_id}"
                ),
                "platform": X_PLATFORM,
                "source_post_id": source_post_id,
                "author_user_id": author_user_id,
                "author_username": author_username,
                "post_type": infer_x_post_type(tweet),
                "title": None,
                "content_text": clean_text(tweet.get("text")),
                "url": None,
                "score": None,
                "like_count": safe_int(metrics.get("like_count")),
                "retweet_count": safe_int(metrics.get("retweet_count")),
                "reply_count": safe_int(metrics.get("reply_count")),
                "quote_count": safe_int(metrics.get("quote_count")),
                "lang": clean_text(tweet.get("lang")),
                "source": clean_text(tweet.get("source")),
                "created_at_utc": created_at_utc,
                "year": date_parts["year"],
                "month": date_parts["month"],
                "day": date_parts["day"],
                "data_date": data_date,
                "ingest_date": ingest_date,
                "silver_processed_at_utc": processed_at_utc,
            }
        )

    return normalized_posts


def lambda_handler(event, context):
    ingest_date = event.get("ingest_date") if isinstance(event, dict) else None
    dataset_name = (
        event.get("x_dataset_name")
        if isinstance(event, dict) and event.get("x_dataset_name")
        else os.getenv("DEFAULT_X_DATASET_NAME", "x-synthetic-seed")
    )

    return {
        "source": "x",
        "layer": "silver",
        "status": "placeholder",
        "ingest_date": ingest_date,
        "dataset_name": dataset_name,
        "bucket": os.getenv("DATA_LAKE_BUCKET"),
        "bronze_prefix": os.getenv("BRONZE_X_PREFIX", "bronze/x"),
        "silver_prefix": os.getenv("SILVER_PREFIX", "silver"),
        "processed_at_utc": utc_now_iso(),
        "message": "X silver normalization implementation is assigned to Student 3.",
        "request_id": getattr(context, "aws_request_id", None),
    }
