import time
import boto3
import requests
import os
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "oyenstikker")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "oyenstikker123")
BUCKET = os.getenv("MINIO_BUCKET", "oyenstikker-data")
API_URL = os.getenv("API_URL", "http://localhost:8000")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

seen = set()

def get_objects():
    try:
        response = s3.list_objects_v2(Bucket=BUCKET)
        return [obj["Key"] for obj in response.get("Contents", [])]
    except Exception as e:
        print(f"error listing objects: {e}")
        return []

def ingest_object(key):
    try:
        response = s3.get_object(Bucket=BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8", errors="ignore")
        r = requests.post(
            f"{API_URL}/ingest",
            json={"content": content, "metadata": {"source": f"minio:{BUCKET}/{key}"}},
            headers={"X-API-Key": os.getenv("API_KEY", "")},
            timeout=30
        )
        if r.status_code == 200:
            print(f"ingested: {key}")
        else:
            print(f"ingest failed {key}: {r.status_code}")
    except Exception as e:
        print(f"error ingesting {key}: {e}")

def watch():
    print(f"watching bucket: {BUCKET} every {POLL_INTERVAL}s")
    while True:
        objects = get_objects()
        for key in objects:
            if key not in seen:
                print(f"new object detected: {key}")
                ingest_object(key)
                seen.add(key)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    watch()
