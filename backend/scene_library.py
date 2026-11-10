"""Reviewed scene references. Draft contact sheets are never generation inputs."""
import hashlib
import asyncio
import io
import json
import logging
import os
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "assets" / "scene_library"


async def load_scene_references(database, bucket, scene):
    if os.getenv("SCENE_REFERENCE_ASSETS_ENABLED", "true").lower() != "true":
        return []

    async def load():
        from bson import ObjectId
        docs = await database["scene_reference_assets"].find(
            {"status": "approved", "style": "watercolor_v1"}
        ).sort("_id", -1).limit(200).to_list(length=200)
        latest = {}
        for doc in docs:
            latest.setdefault(doc["asset_id"], doc)
        references = []
        for item in select_assets(scene, latest.values()):
            stream = await bucket.open_download_stream(ObjectId(item["file_id"]))
            if stream.length > 10_000_000:
                continue
            data = await stream.read()
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                continue
            references.append({"asset_id": item["asset_id"], "kind": item["kind"],
                               "name": item["name"], "sha256": item["sha256"], "data": data})
        return references

    try:
        return await asyncio.wait_for(load(), timeout=3)
    except Exception as exc:
        logging.getLogger(__name__).warning("Scene reference lookup skipped (%s)", type(exc).__name__)
        return []


def read_catalog(root=ROOT):
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    if catalog.get("schema_version") != 1:
        raise ValueError("Unsupported scene library schema")
    assets = catalog["assets"]
    seen = set()
    for item in assets:
        key = item["asset_id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key) or key in seen:
            raise ValueError("Invalid or duplicate asset ID")
        seen.add(key)
        if item["kind"] not in ("background", "prop") or item["status"] not in ("draft", "approved"):
            raise ValueError("Invalid asset type or review state")
        if not item.get("keywords") or not all(isinstance(k, str) and k.strip() for k in item["keywords"]):
            raise ValueError("Asset requires nonempty keywords")
    return assets


def approved_image(item, root=ROOT):
    if item["status"] != "approved" or not item.get("file"):
        raise ValueError("Only individually reviewed images may be published")
    path = (root / item["file"]).resolve()
    if not path.is_relative_to(root.resolve()) or "previews" in path.relative_to(root.resolve()).parts:
        raise ValueError("Invalid production asset path")
    if path.stat().st_size > 10_000_000:
        raise ValueError("Asset exceeds image size limit")
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or min(image.size) < 128 or image.width * image.height > 4_000_000:
            raise ValueError("Reference must be a bounded PNG image")
        image.verify()
    return data


def select_assets(scene, assets, style="watercolor_v1"):
    """Conservative keyword candidates, not a semantic scene-understanding model."""
    text = scene.casefold()
    selected = []
    for kind in ("background", "prop"):
        ranked = []
        for item in assets:
            if item["status"] != "approved" or item["kind"] != kind or item["style"] != style:
                continue
            matches = [k for k in item["keywords"] if (
                re.search(r"(?<![a-z])" + re.escape(k.casefold()) + r"(?![a-z])", text)
                if k.isascii() else k in text)]
            if matches:
                ranked.append((max(map(len, matches)), item))
        if ranked:
            ranked.sort(key=lambda pair: (-pair[0], pair[1]["asset_id"]))
            selected.append(ranked[0][1])
    return selected


async def publish_assets(database, bucket, assets, root=ROOT):
    # Validate every file before any remote write. Content hashes make re-runs reusable.
    prepared = [(item, approved_image(item, root)) for item in assets if item["status"] == "approved"]
    collection = database["scene_reference_assets"]
    await collection.create_index([("asset_id", 1), ("sha256", 1)], unique=True)
    published = []
    for item, data in prepared:
        digest = hashlib.sha256(data).hexdigest()
        identity = {"asset_id": item["asset_id"], "sha256": digest}
        existing = await collection.find_one(identity)
        if existing:
            published.append(str(existing["file_id"]))
            continue
        file_id = await bucket.upload_from_stream(
            f"scene-reference-{item['asset_id']}-{digest[:12]}.png", data,
            metadata={"type": "scene_reference", **identity},
        )
        # On ambiguous DB errors retain the file: deleting could break a committed record.
        from pymongo.errors import DuplicateKeyError
        try:
            await collection.insert_one({**item, **identity, "file_id": str(file_id)})
        except DuplicateKeyError:
            await bucket.delete(file_id)
            winner = await collection.find_one(identity)
            file_id = winner["file_id"]
        published.append(str(file_id))
    return published
