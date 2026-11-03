"""우리 가족 목소리 + 동화 듣기(TTS)

목소리 등록 (마이페이지 "우리 가족 목소리")
    - 사용자당 최대 MAX_VOICES개, 이름(엄마, 아빠, 나 …)을 붙여 등록·삭제
    - 앱에서 녹음한 소리든 올린 음성 파일이든, 형식과 상관없이 ffmpeg로 XTTS가 받는 WAV(PCM 16bit, 모노, 22.05kHz)로 바꿔
      voice_data/{사용자별 폴더}/{voice_id}.wav 에 저장 (static 밖이라 주소로 열 수 없음)
    - 앞뒤 무음을 뺀 길이가 MIN_SECONDS초보다 짧으면 다시 녹음 안내, MAX_SECONDS초까지만 씀
    - ffmpeg는 PATH에 있으면 그것을, 없으면 imageio-ffmpeg에 들어 있는 것을 씀
    - family_voices 컬렉션: {voice_id, user_id, name, duration_sec, file, created_at}

동화 듣기 (POST /api/tts, 장면 하나씩)
    - 기본 목소리(기계음, voice_id="default"): gTTS (예전 앱은 GET /api/tts를 불렀지만 서버에 만든 적이 없어서 새로 만듦)
    - 가족 목소리: 팀원 Colab POST /api/tts (text + speaker_wav) → XTTS가 그 목소리로 읽음
      Colab이 꺼져 있거나 실패하면 기본 목소리로 읽고 fallback=true + 안내 문구
    - 만든 오디오는 static/tts/{voice_id}/{해시}.wav|mp3 로 저장 → 다시 들을 때는 Colab/gTTS를 부르지 않음
      (해시 = 비밀값 + 목소리 + 동화 + 장면 + 본문 → 주소를 짐작할 수 없음, 본문이 바뀌면 새로 만듦)
    - 목소리를 지우면 static/tts/{voice_id}/ 폴더(그 목소리로 만든 오디오)도 같이 삭제
"""
import asyncio
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

import colab_client
from branching import _my_story
from database import family_voices_collection, safe_create_index
from security import get_current_user

router = APIRouter(tags=["가족 목소리 / 동화 듣기"])

BASE_DIR = Path(__file__).resolve().parent
VOICE_DIR = BASE_DIR / "voice_data"
TTS_DIR = BASE_DIR / "static" / "tts"
TTS_URL_PREFIX = "/static/tts"

DEFAULT_VOICE_ID = "default"
DEFAULT_VOICE_NAME = "기본 목소리(기계음)"
MAX_VOICES = 3
NAME_MAX_LEN = 10
MIN_SECONDS = 3.0
MAX_SECONDS = 20.0
SAMPLE_RATE = 22050
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
TTS_TEXT_MAX_LEN = 2400  # Colab XTTS는 한 번에 2,500자까지

SAMPLE_SENTENCE = (
    "옛날 옛날 깊은 숲속에 마음씨 착한 아기 토끼가 살았어요. "
    "아기 토끼는 친구들과 함께 노래를 부르며 매일매일 즐겁게 놀았답니다."
)
PRIVACY_NOTICE = "녹음한 목소리는 동화 읽어주기에만 쓰이고, 언제든 지울 수 있어요."
NO_FAMILY_VOICE_HINT = "가족 목소리를 등록하면 그 목소리로 들을 수 있어요."
FALLBACK_MESSAGE = "지금은 가족 목소리 요정이 쉬고 있어서 기본 목소리로 읽어 줄게요."
TOO_SHORT_MESSAGE = f"목소리가 {MIN_SECONDS:.0f}초보다 짧아요. 예시 문장을 끝까지 천천히 읽으며 다시 녹음해 주세요."


async def ensure_indexes() -> None:
    await safe_create_index(family_voices_collection, [("user_id", 1), ("created_at", 1)])
    await safe_create_index(family_voices_collection, "voice_id", unique=True)


# ----------------------------------------
# 스키마
# ----------------------------------------
class VoiceOut(BaseModel):
    id: str
    name: str
    is_default: bool = False
    duration_sec: Optional[float] = None
    created_at: Optional[datetime] = None


class VoiceListResponse(BaseModel):
    voices: list[VoiceOut]          # 맨 앞은 항상 기본 목소리
    max_count: int = MAX_VOICES
    family_count: int
    sample_sentence: str = SAMPLE_SENTENCE
    min_seconds: float = MIN_SECONDS
    notice: str = PRIVACY_NOTICE
    hint: str = ""                  # 가족 목소리가 없으면 등록 안내


class DeleteVoiceResponse(BaseModel):
    ok: bool
    deleted_audio_files: int


class TtsRequest(BaseModel):
    story_id: str
    scene_number: int = Field(..., ge=1)
    voice_id: str = DEFAULT_VOICE_ID


class TtsResponse(BaseModel):
    audio_url: str                  # "/static/tts/..." (앞에 서버 주소를 붙여서 씀)
    voice_id: str                   # 실제로 읽은 목소리 (fallback이면 default)
    voice_name: str
    fallback: bool = False          # 가족 목소리를 골랐지만 기본 목소리로 읽음
    cached: bool = False            # 저장해 둔 파일을 그대로 씀
    message: str = ""


# ----------------------------------------
# 오디오 변환
# ----------------------------------------
def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


# 앞뒤 무음 빼기 (뒤쪽은 뒤집어서 앞쪽처럼 처리)
_TRIM_SILENCE = (
    "silenceremove=start_periods=1:start_silence=0.2:start_threshold=-45dB,areverse,"
    "silenceremove=start_periods=1:start_silence=0.2:start_threshold=-45dB,areverse"
)


def _convert_sync(data: bytes, suffix: str) -> tuple[bytes, float]:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, f"input{suffix}")
        dst = os.path.join(tmp, "voice.wav")
        with open(src, "wb") as f:
            f.write(data)
        cmd = [
            ffmpeg_exe(), "-y", "-v", "error", "-i", src, "-vn", "-af", _TRIM_SILENCE,
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", "-t", str(MAX_SECONDS), dst,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0 or not os.path.exists(dst):
            raise ValueError(result.stderr.decode("utf-8", "replace")[-300:])
        with open(dst, "rb") as f:
            wav = f.read()
    with wave.open(io.BytesIO(wav)) as w:
        duration = w.getnframes() / float(w.getframerate() or 1)
    return wav, duration


async def convert_to_voice_wav(data: bytes, filename: str) -> tuple[bytes, float]:
    """아무 음성 파일 → (WAV PCM 모노 바이트, 초). 읽을 수 없으면 ValueError"""
    suffix = Path(filename or "").suffix.lower()
    if not suffix or len(suffix) > 6 or not suffix[1:].isalnum():
        suffix = ".bin"
    return await asyncio.to_thread(_convert_sync, data, suffix)


# ----------------------------------------
# 도우미
# ----------------------------------------
def _user_dir(user_id: str) -> Path:
    return VOICE_DIR / hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def _voice_out(doc: dict) -> VoiceOut:
    return VoiceOut(
        id=doc["voice_id"],
        name=doc.get("name") or "가족 목소리",
        duration_sec=doc.get("duration_sec"),
        created_at=doc.get("created_at"),
    )


def _default_voice() -> VoiceOut:
    return VoiceOut(id=DEFAULT_VOICE_ID, name=DEFAULT_VOICE_NAME, is_default=True)


async def _my_voices(user_id: str) -> list[dict]:
    return [d async for d in family_voices_collection.find({"user_id": user_id}).sort("created_at", 1)]


def _secret() -> str:
    return os.getenv("JWT_SECRET") or "fairytale-tts"


def _audio_path(voice_id: str, story_id: str, scene_number: int, text: str, ext: str) -> Path:
    key = f"{_secret()}|{voice_id}|{story_id}|{scene_number}|{text}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return TTS_DIR / voice_id / f"{digest}.{ext}"


def _audio_url(path: Path) -> str:
    return f"{TTS_URL_PREFIX}/{path.parent.name}/{path.name}"


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _gtts_sync(text: str) -> bytes:
    from gtts import gTTS

    buf = io.BytesIO()
    gTTS(text=text, lang="ko").write_to_fp(buf)
    return buf.getvalue()


def _speech_text(scene: dict) -> str:
    text = " ".join((scene.get("text") or "").split())
    return text[:TTS_TEXT_MAX_LEN]


# ----------------------------------------
# 목소리 API
# ----------------------------------------
@router.get("/api/voices", response_model=VoiceListResponse)
async def list_voices(current_user: dict = Depends(get_current_user)):
    family = [_voice_out(d) for d in await _my_voices(current_user["user_id"])]
    return VoiceListResponse(
        voices=[_default_voice(), *family],
        family_count=len(family),
        hint="" if family else NO_FAMILY_VOICE_HINT,
    )


@router.post("/api/voices", response_model=VoiceOut)
async def add_voice(
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """목소리 등록: 녹음 파일 또는 올린 음성 파일 (형식 상관없음) → WAV로 바꿔 저장"""
    user_id = current_user["user_id"]
    name = " ".join(name.split())
    if not name:
        raise HTTPException(status_code=400, detail="목소리 이름을 적어 주세요. (예: 엄마, 아빠, 나)")
    if len(name) > NAME_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"이름은 {NAME_MAX_LEN}자까지 쓸 수 있어요.")
    voices = await _my_voices(user_id)
    if len(voices) >= MAX_VOICES:
        raise HTTPException(status_code=400, detail=f"목소리는 {MAX_VOICES}개까지 등록할 수 있어요. 하나를 지우고 다시 해 주세요.")
    if any(v.get("name") == name for v in voices):
        raise HTTPException(status_code=400, detail=f"'{name}' 목소리가 벌써 있어요. 다른 이름을 붙여 주세요.")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="파일이 너무 커요. 20MB보다 작은 음성 파일을 올려 주세요.")
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일이에요. 다시 녹음해 주세요.")
    try:
        wav, duration = await convert_to_voice_wav(data, file.filename or "")
    except Exception as e:
        print(f"[가족 목소리] 변환 실패: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(status_code=400, detail="이 파일은 소리로 읽을 수 없어요. 녹음 파일(mp3, m4a, wav 등)을 올려 주세요.")
    if duration < MIN_SECONDS:
        raise HTTPException(status_code=400, detail=TOO_SHORT_MESSAGE)

    voice_id = uuid.uuid4().hex
    folder = _user_dir(user_id)
    path = folder / f"{voice_id}.wav"
    _write_atomic(path, wav)
    doc = {
        "voice_id": voice_id,
        "user_id": user_id,
        "name": name,
        "duration_sec": round(duration, 1),
        "file": str(path.relative_to(BASE_DIR)),
        "created_at": datetime.utcnow(),
    }
    await family_voices_collection.insert_one(doc)
    return _voice_out(doc)


@router.delete("/api/voices/{voice_id}", response_model=DeleteVoiceResponse)
async def delete_voice(voice_id: str, current_user: dict = Depends(get_current_user)):
    """목소리 삭제 + 그 목소리로 만든 동화 오디오 파일도 같이 삭제"""
    doc = await family_voices_collection.find_one({"voice_id": voice_id, "user_id": current_user["user_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="목소리를 찾지 못했어요.")
    sample = BASE_DIR / doc.get("file", "")
    if sample.is_file():
        sample.unlink()
    audio_dir = TTS_DIR / voice_id
    deleted = 0
    if audio_dir.is_dir():
        deleted = sum(1 for p in audio_dir.iterdir() if p.is_file())
        shutil.rmtree(audio_dir, ignore_errors=True)
    await family_voices_collection.delete_one({"_id": doc["_id"]})
    return DeleteVoiceResponse(ok=True, deleted_audio_files=deleted)


# ----------------------------------------
# 동화 듣기
# ----------------------------------------
async def _default_tts(story_id: str, scene_number: int, text: str) -> tuple[Path, bool]:
    path = _audio_path(DEFAULT_VOICE_ID, story_id, scene_number, text, "mp3")
    if path.is_file():
        return path, True
    try:
        audio = await asyncio.to_thread(_gtts_sync, text)
    except Exception as e:
        print(f"[동화 듣기] 기본 목소리(gTTS) 실패: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(status_code=503, detail="목소리 요정이 잠깐 쉬고 있어요. 조금 뒤에 다시 눌러 주세요.")
    _write_atomic(path, audio)
    return path, False


@router.post("/api/tts", response_model=TtsResponse)
async def story_tts(body: TtsRequest, current_user: dict = Depends(get_current_user)):
    """장면 하나 읽어 주기. 본문은 서버에 저장된 장면에서 가져옴 (클라이언트가 보낸 글을 읽지 않음)"""
    user_id = current_user["user_id"]
    doc = await _my_story(body.story_id, user_id)
    scenes = doc.get("scenes") or [{"text": doc.get("content") or ""}]
    if body.scene_number > len(scenes):
        raise HTTPException(status_code=404, detail="장면을 찾지 못했어요.")
    text = _speech_text(scenes[body.scene_number - 1])
    if not text:
        raise HTTPException(status_code=400, detail="읽을 이야기가 없어요.")
    story_id = str(doc["_id"])

    if body.voice_id != DEFAULT_VOICE_ID:
        voice = await family_voices_collection.find_one({"voice_id": body.voice_id, "user_id": user_id})
        if not voice:
            raise HTTPException(status_code=404, detail="목소리를 찾지 못했어요. 목소리 목록을 다시 불러올게요.")
        path = _audio_path(body.voice_id, story_id, body.scene_number, text, "wav")
        if path.is_file():
            return TtsResponse(audio_url=_audio_url(path), voice_id=body.voice_id, voice_name=voice["name"], cached=True)
        sample = BASE_DIR / voice.get("file", "")
        try:
            if not sample.is_file():
                raise colab_client.ColabError("목소리 샘플 파일이 없음")
            audio = await colab_client.post_tts(text, sample.read_bytes())
            _write_atomic(path, audio)
            return TtsResponse(audio_url=_audio_url(path), voice_id=body.voice_id, voice_name=voice["name"])
        except colab_client.ColabError as e:
            print(f"[동화 듣기] 가족 목소리(Colab XTTS) 실패 → 기본 목소리 ({e})", flush=True)
            path, cached = await _default_tts(story_id, body.scene_number, text)
            return TtsResponse(
                audio_url=_audio_url(path), voice_id=DEFAULT_VOICE_ID, voice_name=DEFAULT_VOICE_NAME,
                fallback=True, cached=cached, message=FALLBACK_MESSAGE,
            )

    path, cached = await _default_tts(story_id, body.scene_number, text)
    count = await family_voices_collection.count_documents({"user_id": user_id})
    return TtsResponse(
        audio_url=_audio_url(path), voice_id=DEFAULT_VOICE_ID, voice_name=DEFAULT_VOICE_NAME,
        cached=cached, message="" if count else NO_FAMILY_VOICE_HINT,
    )
