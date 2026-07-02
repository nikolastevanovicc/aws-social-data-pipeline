import importlib.util
import os
from pathlib import Path


os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

HANDLER_PATH = (
    Path(__file__).resolve().parents[2]
    / "lambdas"
    / "hn_silver_normalization"
    / "handler.py"
)
SPEC = importlib.util.spec_from_file_location("hn_silver_normalization_handler", HANDLER_PATH)
handler = importlib.util.module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(handler)


def test_resolve_hn_processing_options_preserves_explicit_dates_and_overrides():
    options = handler.resolve_hn_processing_options(
        {
            "bucket": "event-bucket",
            "bronze_prefix": "custom/bronze/hn",
            "silver_prefix": "custom/silver",
            "data_date": "2026-05-20",
            "ingest_date": "2026-05-21",
        }
    )

    assert options == {
        "bucket": "event-bucket",
        "bronze_prefix": "custom/bronze/hn",
        "silver_prefix": "custom/silver",
        "data_date": "2026-05-20",
        "ingest_date": "2026-05-21",
    }


def test_resolve_hn_processing_options_defaults_to_yesterday_data_date_and_today_ingest_date(
    monkeypatch,
):
    monkeypatch.setenv("DATA_LAKE_BUCKET", "env-bucket")
    monkeypatch.setattr(handler, "utc_yesterday", lambda: "2026-07-01")
    monkeypatch.setattr(handler, "utc_today", lambda: "2026-07-02")

    options = handler.resolve_hn_processing_options({})

    assert options["bucket"] == "env-bucket"
    assert options["bronze_prefix"] == "bronze/hacker-news"
    assert options["silver_prefix"] == "silver"
    assert options["data_date"] == "2026-07-01"
    assert options["ingest_date"] == "2026-07-02"
