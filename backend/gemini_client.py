"""Gemini 호출 창구: 한도 초과(429)면 .env의 GEMINI_FALLBACK_MODELS 모델로 자동으로 다시 시도합니다.

.env 예시
    GEMINI_MODEL=gemini-3.5-flash
    GEMINI_FALLBACK_MODELS=gemini-3-flash-preview,gemini-2.5-flash

- 무료 한도는 모델마다 따로 계산되므로, 한 모델이 429면 다음 모델로 넘어갑니다.
- 429가 난 모델은 잠시(EXHAUSTED_COOLDOWN_SEC) 건너뛰어서 매번 실패 호출을 낭비하지 않습니다.
- 429가 아닌 오류(잘못된 요청 등)는 바로 올려 보냅니다. (호출하는 쪽의 예비 동작이 처리)
- generate_content / generate_content_async 모양이 GenerativeModel과 같아서 그대로 바꿔 끼울 수 있습니다.
"""
import time
from typing import Callable, Optional

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, TooManyRequests

EXHAUSTED_COOLDOWN_SEC = 10 * 60


def parse_model_list(value: Optional[str]) -> list[str]:
    return [m.strip() for m in (value or "").split(",") if m.strip()]


def is_quota_error(e: Exception) -> bool:
    if isinstance(e, (ResourceExhausted, TooManyRequests)):
        return True
    text = str(e)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower()


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
        self._exhausted_until[name] = self._clock() + EXHAUSTED_COOLDOWN_SEC
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
                if not is_quota_error(e):
                    raise
                self._mark_exhausted(name, e)
                last_error = e
        raise AllModelsExhausted(f"모든 Gemini 모델이 한도 초과: {self.model_names}") from last_error

    async def generate_content_async(self, *args, **kwargs):
        last_error: Optional[Exception] = None
        for name in self._order():
            try:
                result = await self._model(name).generate_content_async(*args, **kwargs)
                self._used(name)
                return result
            except Exception as e:
                if not is_quota_error(e):
                    raise
                self._mark_exhausted(name, e)
                last_error = e
        raise AllModelsExhausted(f"모든 Gemini 모델이 한도 초과: {self.model_names}") from last_error
