"""장면 그림: 장면 본문이 먼저 화면에 나온 뒤, 화면이 따로 그림을 요청합니다. (팀원 Colab POST /story/image)

- Colab이 준 PNG(512x512)를 JPEG로 줄여 static/story_images/에 저장하고, URL을 stories.scene_images.{장면 번호}에 저장
  (scenes 배열과 따로 두어서, 그림이 그려지는 동안 다음 장면이 저장돼도 서로 덮어쓰지 않음)
- 이미 그림이 있으면 바로 돌려줌 (Colab을 다시 부르지 않음)
- 실패하면 scene_image_failed.{번호} = true → 그 장면은 그림 없이 진행 (다시 열어도 다시 시도하지 않음)
- 같은 장면을 동시에 두 번 요청하면 하나만 그림 (scene_image_claims), 나머지는 status="busy"
"""
import base64
import io
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel

import colab_client
from branching import _my_story
from database import stories_collection
from security import get_current_user

router = APIRouter(tags=["분기형 동화"])

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "story_images")
IMAGE_URL_PREFIX = "/static/story_images"
JPEG_QUALITY = 85
MAX_SIDE = 768
CLAIM_TIMEOUT = timedelta(minutes=3)


class SceneImageResponse(BaseModel):
    scene_number: int
    status: str                        # ready / failed / busy
    image_url: Optional[str] = None    # "/static/story_images/..." (앞에 서버 주소를 붙여서 씀)


def png_b64_to_jpeg(image_b64: str) -> bytes:
    raw = base64.b64decode(image_b64, validate=False)
    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


@router.post("/api/stories/{story_id}/scenes/{scene_number}/image", response_model=SceneImageResponse)
async def scene_image(story_id: str, scene_number: int, current_user: dict = Depends(get_current_user)):
    doc = await _my_story(story_id, current_user["user_id"])
    scenes = doc.get("scenes") or []
    if not 1 <= scene_number <= len(scenes):
        raise HTTPException(status_code=404, detail="장면을 찾지 못했어요.")
    key = str(scene_number)
    url = (doc.get("scene_images") or {}).get(key)
    if url:
        return SceneImageResponse(scene_number=scene_number, status="ready", image_url=url)
    if (doc.get("scene_image_failed") or {}).get(key):
        return SceneImageResponse(scene_number=scene_number, status="failed")

    now = datetime.utcnow()
    claim_field = f"scene_image_claims.{key}"
    claimed = await stories_collection.update_one(
        {
            "_id": doc["_id"],
            f"scene_images.{key}": {"$exists": False},
            "$or": [{claim_field: {"$exists": False}}, {claim_field: {"$lt": now - CLAIM_TIMEOUT}}],
        },
        {"$set": {claim_field: now}},
    )
    if claimed.modified_count == 0:
        return SceneImageResponse(scene_number=scene_number, status="busy")

    scene = scenes[scene_number - 1]
    try:
        data = await colab_client.post_json(
            "/story/image",
            {"story_text": scene.get("text") or "", "genre": doc.get("genre") or "", "age": doc.get("age") or "5-7세"},
            colab_client.IMAGE_TIMEOUT_SEC,
        )
        if not data.get("image_b64"):
            raise colab_client.ColabError("image_b64가 비어 있음")
        jpeg = png_b64_to_jpeg(data["image_b64"])
    except Exception as e:
        print(f"[장면 그림] {story_id} 장면 {scene_number} 실패 → 그림 없이 진행 ({type(e).__name__}: {e})", flush=True)
        await stories_collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {f"scene_image_failed.{key}": True}, "$unset": {claim_field: ""}},
        )
        return SceneImageResponse(scene_number=scene_number, status="failed")

    os.makedirs(IMAGE_DIR, exist_ok=True)
    file_name = f"{story_id}_{scene_number}_{secrets.token_hex(6)}.jpg"
    with open(os.path.join(IMAGE_DIR, file_name), "wb") as f:
        f.write(jpeg)
    url = f"{IMAGE_URL_PREFIX}/{file_name}"
    await stories_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {f"scene_images.{key}": url}, "$unset": {claim_field: ""}},
    )
    return SceneImageResponse(scene_number=scene_number, status="ready", image_url=url)
