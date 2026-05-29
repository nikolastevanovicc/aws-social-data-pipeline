#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


DATASET_FILES = ("tweets.json", "metadata.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload the synthetic X/Twitter dataset to the S3 bronze layer."
    )
    parser.add_argument("--bucket", required=True, help="Name of the target S3 bucket.")
    parser.add_argument(
        "--dataset-name",
        default="x-synthetic-seed",
        help="Dataset name used in the S3 prefix.",
    )
    parser.add_argument(
        "--ingest-date",
        default=dt.datetime.now(dt.timezone.utc).date().isoformat(),
        help="Ingest date in YYYY-MM-DD format. Defaults to today's UTC date.",
    )
    parser.add_argument(
        "--dataset-dir",
        default="datasets/x",
        help="Directory containing tweets.json and metadata.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the upload plan without calling S3.",
    )
    return parser.parse_args()


def resolve_dataset_dir(dataset_dir: str) -> Path:
    path = Path(dataset_dir)
    if path.is_absolute() or path.exists():
        return path

    repo_relative_path = Path(__file__).resolve().parents[1] / path
    if repo_relative_path.exists():
        return repo_relative_path

    return path


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise ValueError(f"Required file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}") from exc


def validate_ingest_date(ingest_date: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ingest_date):
        raise ValueError(f"Invalid --ingest-date '{ingest_date}'. Use YYYY-MM-DD format.")

    try:
        dt.date.fromisoformat(ingest_date)
    except ValueError as exc:
        raise ValueError(
            f"Invalid --ingest-date '{ingest_date}'. Use YYYY-MM-DD format."
        ) from exc


def validate_dataset(dataset_dir: Path) -> tuple[list[Any], dict[str, Any]]:
    tweets_path = dataset_dir / "tweets.json"
    metadata_path = dataset_dir / "metadata.json"

    tweets = load_json(tweets_path)
    metadata = load_json(metadata_path)

    if not isinstance(tweets, list):
        raise ValueError(f"{tweets_path} must contain a JSON array.")

    if not isinstance(metadata, dict):
        raise ValueError(f"{metadata_path} must contain a JSON object.")

    record_count = metadata.get("record_count")
    if record_count is not None and record_count != len(tweets):
        raise ValueError(
            f"{metadata_path} record_count is {record_count}, "
            f"but {tweets_path} contains {len(tweets)} records."
        )

    return tweets, metadata


def build_target_prefix(dataset_name: str, ingest_date: str) -> str:
    return f"bronze/x/ingest_date={ingest_date}/dataset_name={dataset_name}/"


def print_summary(
    bucket: str,
    dataset_name: str,
    ingest_date: str,
    tweet_count: int,
    uploads: list[tuple[Path, str]],
    dry_run: bool,
) -> None:
    action = "Dry run upload plan" if dry_run else "Upload summary"
    print(f"{action}:")
    print(f"  Bucket: {bucket}")
    print(f"  Dataset name: {dataset_name}")
    print(f"  Ingest date: {ingest_date}")
    print(f"  Tweet records: {tweet_count}")
    print("  Local files:")
    for local_path, _ in uploads:
        print(f"    - {local_path}")
    print("  Target S3 URIs:")
    for _, s3_uri in uploads:
        print(f"    - {s3_uri}")


def upload_files(bucket: str, uploads: list[tuple[Path, str]]) -> None:
    import boto3

    s3 = boto3.client("s3")
    for local_path, s3_uri in uploads:
        key = s3_uri.removeprefix(f"s3://{bucket}/")
        s3.upload_file(
            str(local_path),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/json"},
        )
        print(f"Uploaded {local_path} -> {s3_uri}")


def main() -> None:
    args = parse_args()

    try:
        validate_ingest_date(args.ingest_date)
        dataset_dir = resolve_dataset_dir(args.dataset_dir)
        tweets, _ = validate_dataset(dataset_dir)

        dataset_name = args.dataset_name
        prefix = build_target_prefix(dataset_name, args.ingest_date)
        uploads = [
            (dataset_dir / file_name, f"s3://{args.bucket}/{prefix}{file_name}")
            for file_name in DATASET_FILES
        ]

        print_summary(
            bucket=args.bucket,
            dataset_name=dataset_name,
            ingest_date=args.ingest_date,
            tweet_count=len(tweets),
            uploads=uploads,
            dry_run=args.dry_run,
        )

        if args.dry_run:
            return

        upload_files(args.bucket, uploads)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
