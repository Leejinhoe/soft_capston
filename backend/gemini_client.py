"""Gemini 호출 창구: 한도 초과(429)면 .env의 GEMINI_FALLBACK_MODELS 모델로 자동으로 다시 시도합니다.

.env 예시
    GEMINI_MODEL=gemini-3.5-flash
    GEMINI_FALLBACK_MODELS=gemini-3-flash-preview,gemini-2.5-flash

- 무료 한도는 모델마다 따로 계산되므로, 한 모델이 429면 다음 모델로 넘어갑니다.
- 429가 난 모델은 잠시(EXHAUSTED_COOLDOWN_SEC) 건너뛰어서 매번 실패 호출을 낭비하지 않습니다.
- 404(없어진 모델, 예: gemini-2.5-flash "no longer available")도 한도 초과처럼 건너뛰고 다음 모델로 넘어갑니다.
- 504/503/500(잠깐 느리거나 아픈 모델)도 다음 모델로 넘어가고, 그 모델은 1분만 건너뜁니다.
- 그 밖의 오류(잘못된 요청 등)는 바로 올려 보냅니다. (호출하는 쪽의 예비 동작이 처리)
- generate_content_async는 "먼저 보낸 모델이 HEDGE_AFTER_SEC 안에 답이 없으면 다음 모델에도 같이 보내고
  먼저 온 답을 씀" (Gemini 응답 시간이 2초~60초로 들쭉날쭉해서, 한 모델을 끝까지 기다리면 화면이 멈춤)
- generate_content / generate_content_async 모양이 GenerativeModel과 같아서 그대로 바꿔 끼울 수 있습니다.
"""
import asyncio
import time
from typing import Callable, Optional

import google.generativeai as genai
from google.api_core.exceptions import (DeadlineExceeded, InternalServerError, NotFound, ResourceExhausted,
                                        ServiceUnavailable, TooManyRequests)

EXHAUSTED_COOLDOWN_SEC = 10 * 60
SLOW_COOLDOWN_SEC = 60          # 504/503/500(잠깐 느리거나 아픈 모델)은 1분만 건너뜀
MODEL_REQUEST_TIMEOUT_SEC = 40  # 모델 하나를 기다리는 최대 시간 (기본값은 훨씬 김)
HEDGE_AFTER_SEC = 8             # 이 안에 답이 없으면 다음 모델에도 같이 보냄
MAX_PARALLEL = 2                # 동시에 기다리는 모델은 2개까지 (무료 한도를 아끼려고)


def parse_model_list(value: Optional[str]) -> list[str]:
    return [m.strip() for m in (value or "").split(",") if m.strip()]


def is_model_gone(e: Exception) -> bool:
    """모델이 없어졌거나 이 키로 쓸 수 없음 (404) → 다음 모델로"""
    return isinstance(e, NotFound) or ("404" in str(e) and "model" in str(e).lower())


def is_quota_error(e: Exception) -> bool:
    if isinstance(e, (ResourceExhausted, TooManyRequests)):
        return True
    text = str(e)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


def is_temporary_error(e: Exception) -> bool:
    """잠깐 느리거나 아픈 모델 (504 시간 초과, 503 과부하, 500) → 다음 모델로"""
    if isinstance(e, (DeadlineExceeded, ServiceUnavailable, InternalServerError)):
        return True
    text = str(e)
    return any(code in text for code in ("504", "503", "Deadline")) and "400" not in text


class AllModelsExhausted(RuntimeError):
    """모든 모델이 한도 초과"""


class FallbackModel:
    def __init__(
        self,
        primary: str,
        fallbacks: Optional[list[str]] = None,
        factory: Callable[[str], object] = genai.GenerativeModel,
        clock: Callable[[], float] = time.monotonic,
    ):
        names = [primary] + [m for m in (fallbacks or []) if m != primary]
        self.model_names = list(dict.fromkeys(names))
        self._factory = factory
        self._clock = clock
        self._models: dict[str, object] = {}
        self._exhausted_until: dict[str, float] = {}
        self.last_used: Optional[str] = None

    def _model(self, name: str):
        if name not in self._models:
            self._models[name] = self._factory(name)
        return self._models[name]

    def _order(self) -> list[str]:
        """쉬는 중이 아닌 모델 먼저. 전부 쉬는 중이면 그래도 순서대로 한 번씩 시도."""
        now = self._clock()
        ready = [n for n in self.model_names if self._exhausted_until.get(n, 0) <= now]
        return ready or list(self.model_names)

    def _mark_exhausted(self, name: str, e: Exception) -> None:
        cooldown = SLOW_COOLDOWN_SEC if is_temporary_error(e) else EXHAUSTED_COOLDOWN_SEC
        self._exhausted_until[name] = self._clock() + cooldown
        print(f"[Gemini 한도 초과] {name} → 다음 모델로 다시 시도 ({str(e).splitlines()[0][:120]})", flush=True)

    def _used(self, name: str) -> None:
        if name != self.model_names[0]:
            print(f"[Gemini] 대체 모델 {name} 사용", flush=True)
        self.last_used = name

    def generate_content(self, *args, **kwargs):
        last_error: Optional[Exception] = None
        for name in self._order():
            try:
                result = self._model(name).generate_content(*args, **kwargs)
                self._used(name)
                return result
            except Exception as e:
                if not (is_quota_error(e) or is_model_gone(e)):
                    raise
                self._mark_exhausted(name, e)
                last_error = e
        raise AllModelsExhausted(f"모든 Gemini 모델이 한도 초과: {self.model_names}") from last_error

    async def generate_content_async(self, *args, **kwargs):
        kwargs.setdefault("request_options", {"timeout": MODEL_REQUEST_TIMEOUT_SEC})
        waiting = list(self._order())
        running: dict[asyncio.Task, str] = {}
        last_error: Optional[Exception] = None

        def launch() -> None:
            name = waiting.pop(0)
            running[asyncio.ensure_future(self._model(name).generate_content_async(*args, **kwargs))] = name

        launch()
        try:
            while running:
                done, _ = await asyncio.wait(
                    set(running), timeout=HEDGE_AFTER_SEC if waiting and len(running) < MAX_PARALLEL else None,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:  # 느림 → 다음 모델에도 같이 보냄 (먼저 보낸 것도 계속 기다림)
                    print(f"[Gemini] {', '.join(running.values())} 답이 늦어서 {waiting[0]}에도 같이 보냄", flush=True)
                    launch()
                    continue
                for task in done:
                    name = running.pop(task)
                    e = task.exception()
                    if e is None:
                        self._used(name)
                        return task.result()
                    if not (is_quota_error(e) or is_model_gone(e) or is_temporary_error(e)):
                        if not running and not waiting:
                            raise e
                        print(f"[Gemini] {name} 오류 → 다른 모델로 ({type(e).__name__}: {str(e)[:100]})", flush=True)
                    else:
                        self._mark_exhausted(name, e)
                    last_error = e
                if not running and waiting:
                    launch()
        finally:
            for task in running:
                task.cancel()
        raise AllModelsExhausted(f"모든 Gemini 모델이 실패: {self.model_names}") from last_error
