import boto3
import os
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "oyenstikker")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "oyenstikker123")
DEFAULT_BUCKET = os.getenv("MINIO_BUCKET", "oyenstikker-data")

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1"
)

def ensure_bucket(bucket=DEFAULT_BUCKET):
    existing = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    if bucket not in existing:
        s3.create_bucket(Bucket=bucket)
        print(f"created bucket: {bucket}")
    return bucket

def store_object(key: str, data: str, bucket=DEFAULT_BUCKET):
    ensure_bucket(bucket)
    s3.put_object(Bucket=bucket, Key=key, Body=data.encode("utf-8"))
    print(f"stored: {bucket}/{key}")

def retrieve_object(key: str, bucket=DEFAULT_BUCKET) -> str:
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")

def list_objects(bucket=DEFAULT_BUCKET):
    ensure_bucket(bucket)
    response = s3.list_objects_v2(Bucket=bucket)
    return [obj["Key"] for obj in response.get("Contents", [])]

if __name__ == "__main__":
    ensure_bucket()
    store_object("test/hello.txt", "Øyenstikker MinIO integration working.")
    print("objects:", list_objects())
    print("retrieved:", retrieve_object("test/hello.txt"))
