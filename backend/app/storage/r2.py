from .base import ObjectStorage


class R2Storage(ObjectStorage):
    """Cloudflare R2 via its S3-compatible API.

    Not exercised by docker-compose (no credentials in the box), but it is the
    real implementation: R2 speaks S3, so boto3 with a custom endpoint_url is all
    that changes. See README "Storage abstraction" for the migration checklist.
    """

    def __init__(self, endpoint_url: str, bucket: str, access_key: str, secret_key: str,
                 public_base_url: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return key

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def set_pointer(self, name: str, key: str) -> None:
        # A single PUT of a tiny object. R2 gives read-after-write consistency,
        # so the flip is atomic from a reader's point of view.
        self.client.put_object(
            Bucket=self.bucket, Key=f"{name}.pointer", Body=key.encode(),
            ContentType="text/plain", CacheControl="no-cache, max-age=5",
        )

    def get_pointer(self, name: str) -> str | None:
        from botocore.exceptions import ClientError

        try:
            return self.get(f"{name}.pointer").decode().strip()
        except ClientError:
            return None
