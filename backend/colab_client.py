"""팀원 Colab 서버(STORY_SERVER_URL) 호출 공통 창구.

서버 하나에 동화(/story/start, /story/continue), 그림(/story/image), 심리분석(/story/psych), TTS(/api/tts)가 다 있어요.
(구조: team_code/colab/fairytale_emotion_server_colab.ipynb)

- 주소는 .env의 STORY_SERVER_URL. Colab을 다시 켜서 주소가 바뀌면 .env만 고치고 백엔드를 재시작하면 됩니다.
- 연결이 안 되거나(꺼짐) 시간이 넘으면(느림) ColabError → 부르는 쪽이 Gemini / 예비 동작으로 넘어갑니다.
- 연결 자체가 안 되면 잠깐(OFFLINE_COOLDOWN_SEC) Colab을 건너뛰어서, 꺼진 동안 요청마다 오래 기다리지 않게 합니다.
"""
import asyncio
import json
import os
import time
from typing import Optional

import httpx

STORY_TIMEOUT_SEC = 120     # 장면 하나 (실측 55~60초)
STREAM_IDLE_TIMEOUT_SEC = 120   # 스트리밍: 다음 줄이 올 때까지 (선택지·감정 준비 동안은 한동안 조용함)
STREAM_TOTAL_TIMEOUT_SEC = 240  # 스트리밍: 장면 하나 전체
CHOICES_TIMEOUT_SEC = 90    # 선택지만 다시 만들기 (/story/choices)
IMAGE_TIMEOUT_SEC = 120     # 그림 하나 (실측 약 20초)
PSYCH_TIMEOUT_SEC = 150     # 심리분석 (실측 75~100초)
TTS_TIMEOUT_SEC = 180       # 장면 하나 낭독 (XTTS, 문장 수에 비례)
CONNECT_TIMEOUT_SEC = 10
# 스트리밍 첫 줄: Colab은 연결되자마자 meta 줄을 먼저 보냄. 이 안에 아무것도 안 오면
# 커널이 멈췄거나 GPU가 다른 요청에 붙잡힌 것 → 꺼진 것처럼 60초 건너뛰고 바로 Gemini로 (시연 중 Colab이 꺼져도 빨리 넘어가게)
FIRST_EVENT_TIMEOUT_SEC = 15
# 단, 우리가 보낸 다른 Colab 요청(그림·TTS·심리분석·선택지)이 처리 중이면 Colab이 그걸 하느라 늦는 것이라
# (Colab의 async def 엔드포인트가 GPU 작업 동안 서버 전체를 붙잡음) 그 요청이 끝날 때까지 이만큼은 더 기다림
FIRST_EVENT_BUSY_TIMEOUT_SEC = 150

_inflight = 0  # 지금 Colab에 보내 놓고 답을 기다리는 일반 요청(_post) 수 (스트리밍 첫 응답 기다리기에서 씀)
OFFLINE_COOLDOWN_SEC = 60

_offline_until = 0.0


class ColabError(RuntimeError):
    """Colab 서버가 꺼져 있거나, 느리거나, 실패함"""


def colab_url() -> str:
    return (os.getenv("STORY_SERVER_URL") or "").strip().rstrip("/")


def colab_enabled() -> bool:
    return bool(colab_url())


def _check_ready() -> str:
    base = colab_url()
    if not base:
        raise ColabError("STORY_SERVER_URL이 비어 있어요.")
    if time.monotonic() < _offline_until:
        raise ColabError("Colab 서버에 방금 연결하지 못해서 잠깐 건너뛰어요.")
    return base


def _mark_offline(e: Exception) -> None:
    global _offline_until
    _offline_until = time.monotonic() + OFFLINE_COOLDOWN_SEC
    print(f"[Colab] 연결 안 됨 → {OFFLINE_COOLDOWN_SEC}초 동안 건너뜀 ({type(e).__name__}: {e})", flush=True)


async def _post(path: str, timeout: float, **kwargs) -> httpx.Response:
    base = _check_ready()
    limits = httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_SEC)
    global _inflight
    _inflight += 1
    try:
        async with httpx.AsyncClient(timeout=limits) as client:
            response = await client.post(f"{base}{path}", **kwargs)
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        _mark_offline(e)
        raise ColabError(f"Colab 연결 실패: {e}") from e
    except httpx.TimeoutException as e:
        raise ColabError(f"Colab {path} 시간 초과({timeout:.0f}초)") from e
    except httpx.HTTPError as e:
        raise ColabError(f"Colab {path} 요청 오류: {type(e).__name__}: {e}") from e
    finally:
        _inflight -= 1
    # cloudflared 터널은 Colab이 꺼지면 502/530 같은 응답을 바로 돌려줌
    if response.status_code in (502, 503, 504, 530):
        if response.status_code in (502, 530):
            _mark_offline(RuntimeError(f"HTTP {response.status_code}"))
        raise ColabError(f"Colab {path} 응답 {response.status_code}")
    if response.status_code != 200:
        raise ColabError(f"Colab {path} 응답 {response.status_code}: {response.text[:200]}")
    return response


async def post_json(path: str, body: dict, timeout: float) -> dict:
    response = await _post(path, timeout, json=body)
    try:
        data = response.json()
    except ValueError as e:
        raise ColabError(f"Colab {path} 응답이 JSON이 아님") from e
    if not isinstance(data, dict):
        raise ColabError(f"Colab {path} 응답이 객체가 아님")
    return data


async def post_ndjson(path: str, body: dict, on_event, timeout: float = STREAM_IDLE_TIMEOUT_SEC) -> dict:
    """Colab 스트리밍(NDJSON: meta / delta / status / complete / error) → complete 이벤트 내용.

    on_event(event)는 complete 전 이벤트마다 불립니다. timeout은 "다음 줄이 올 때까지" 기다리는 시간,
    전체 시간은 STREAM_TOTAL_TIMEOUT_SEC까지. error 이벤트나 complete 없이 끝나면 ColabError.
    """
    base = _check_ready()
    limits = httpx.Timeout(timeout, connect=CONNECT_TIMEOUT_SEC)

    async def run() -> dict:
        async with httpx.AsyncClient(timeout=limits) as client:
            async with client.stream("POST", f"{base}{path}", json=body) as response:
                if response.status_code in (502, 503, 530):
                    _mark_offline(RuntimeError(f"HTTP {response.status_code}"))
                if response.status_code != 200:
                    raise ColabError(f"Colab {path} 응답 {response.status_code}")
                first_line.set()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    kind = event.get("type") if isinstance(event, dict) else None
                    if kind == "complete":
                        return event
                    if kind == "error":
                        raise ColabError(f"Colab {path} 스트림 오류: {str(event.get('message'))[:200]}")
                    on_event(event)
        raise ColabError(f"Colab {path} 스트림이 complete 없이 끝남")

    first_line = asyncio.Event()  # 응답 헤더가 왔다 (Colab이 살아서 쓰기 시작함)

    async def run_with_first_deadline() -> dict:
        """응답 헤더가 FIRST_EVENT_TIMEOUT_SEC 안에 안 오면 Colab이 멈춘 것으로 보고 바로 실패
        (다른 Colab 요청이 처리 중일 때만 FIRST_EVENT_BUSY_TIMEOUT_SEC까지 기다려 줌)"""
        task = asyncio.ensure_future(run())
        waiter = asyncio.ensure_future(first_line.wait())
        started = time.monotonic()
        try:
            while True:
                done, _ = await asyncio.wait({task, waiter}, timeout=FIRST_EVENT_TIMEOUT_SEC,
                                             return_when=asyncio.FIRST_COMPLETED)
                if done:
                    break
                waited = time.monotonic() - started
                if _inflight == 0 or waited >= FIRST_EVENT_BUSY_TIMEOUT_SEC:
                    e = TimeoutError(f"{waited:.0f}초 동안 응답 없음")
                    _mark_offline(e)
                    raise ColabError(f"Colab {path} 응답 없음 ({e})")
                print(f"[Colab] {path}: 다른 Colab 요청({_inflight}개)이 끝나길 기다리는 중 ({waited:.0f}초)", flush=True)
            return await task
        finally:
            waiter.cancel()
            if not task.done():
                task.cancel()

    try:
        return await asyncio.wait_for(run_with_first_deadline(), STREAM_TOTAL_TIMEOUT_SEC)
    except ColabError:
        raise
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        _mark_offline(e)
        raise ColabError(f"Colab 연결 실패: {e}") from e
    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        raise ColabError(f"Colab {path} 스트림 시간 초과") from e
    except httpx.HTTPError as e:
        raise ColabError(f"Colab {path} 스트림 오류: {type(e).__name__}: {e}") from e


async def post_tts(text: str, speaker_wav: bytes, timeout: float = TTS_TIMEOUT_SEC) -> bytes:
    """Colab POST /api/tts (multipart: text + speaker_wav) → WAV 바이트"""
    response = await _post(
        "/api/tts",
        timeout,
        data={"text": text},
        files={"speaker_wav": ("speaker.wav", speaker_wav, "audio/wav")},
    )
    audio = response.content
    if audio[:4] != b"RIFF":
        raise ColabError("Colab TTS 응답이 WAV가 아님")
    return audio


def compact_emotion(raw, step: Optional[int] = None) -> Optional[dict]:
    """Colab KOTE 감정 분석 결과(44개 점수)에서 심리분석에 필요한 것만 남깁니다."""
    if not isinstance(raw, dict) or not raw.get("primary_emotion"):
        return None
    top = []
    for item in (raw.get("top_emotions") or [])[:5]:
        if isinstance(item, dict) and item.get("label"):
            top.append({"label": str(item["label"]), "score": round(float(item.get("score") or 0), 4)})
    result = {
        "primary_emotion": str(raw["primary_emotion"]),
        "primary_score": round(float(raw.get("primary_score") or 0), 4),
        "top_emotions": top,
    }
    if step is not None:
        result["step"] = step
    return result
