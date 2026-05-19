#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload X dataset files to bronze S3 prefix.")
    parser.add_argument("--bucket", required=True, help="Target Data Lake bucket name.")
    parser.add_argument(
        "--dataset-name", default="x-synthetic-seed", help="Dataset name in S3 path."
    )
    parser.add_argument(
        "--ingest-date",
        default=dt.datetime.now(dt.timezone.utc).date().isoformat(),
        help="Ingest date in YYYY-MM-DD format. Default is current UTC date.",
    )
    parser.add_argument(
        "--base-dir",
        default=str(Path(__file__).resolve().parents[1] / "datasets/x"),
        help="Directory that contains tweets.json and metadata.json.",
    )
    args = parser.parse_args()

    s3 = boto3.client("s3")
    base_dir = Path(args.base_dir)
    target_prefix = (
        f"bronze/x/ingest_date={args.ingest_date}/dataset_name={args.dataset_name}"
    )

    for name in ["tweets.json", "metadata.json"]:
        local_path = base_dir / name
        key = f"{target_prefix}/{name}"
        s3.upload_file(str(local_path), args.bucket, key)
        print(f"Uploaded {local_path} -> s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
