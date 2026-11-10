"""Private R2 storage for new story media; legacy GridFS stays readable."""
import asyncio
import hashlib
import os
import re

from bson import ObjectId


def enabled():
    return os.getenv("R2_MEDIA_ENABLED", "").lower() == "true"


def _client():
    import boto3
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    if not re.fullmatch(r"[0-9a-fA-F]{32}", account):
        raise ValueError("Invalid R2 account")
    return boto3.client(
        "s3", endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _bucket():
    bucket = os.environ["R2_BUCKET"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,62}", bucket):
        raise ValueError("Invalid R2 bucket")
    return bucket


def _key(story_id, kind, media_id):
    if not ObjectId.is_valid(story_id) or not ObjectId.is_valid(media_id):
        raise ValueError("Invalid story media ID")
    if kind not in ("image", "video", "journey"):
        raise ValueError("Invalid media kind")
    return f"stories/{story_id}/{kind}/{media_id}"


def _put(story_id, kind, media_id, data):
    key = _key(story_id, kind, media_id)
    digest = hashlib.sha256(data).hexdigest()
    client = _client()
    client.put_object(Bucket=_bucket(), Key=key, Body=data,
                      ContentType="image/png" if kind == "image" else "video/mp4",
                      Metadata={"sha256": digest})
    obj = client.get_object(Bucket=_bucket(), Key=key)
    body = obj["Body"].read()
    if hashlib.sha256(body).hexdigest() != digest:
        raise IOError("R2 upload verification failed")
    return key


async def put(story_id, kind, media_id, data):
    return await asyncio.to_thread(_put, story_id, kind, media_id, data)


def _get(story_id, kind, media_id, limit):
    obj = _client().get_object(Bucket=_bucket(), Key=_key(story_id, kind, media_id))
    if obj["ContentLength"] > limit:
        raise ValueError("R2 media exceeds read limit")
    data = obj["Body"].read(limit + 1)
    if len(data) > limit:
        raise ValueError("R2 media exceeds read limit")
    digest = obj.get("Metadata", {}).get("sha256")
    if digest and hashlib.sha256(data).hexdigest() != digest:
        raise IOError("R2 media checksum mismatch")
    return data


async def get(story_id, kind, media_id, limit):
    return await asyncio.to_thread(_get, story_id, kind, media_id, limit)
