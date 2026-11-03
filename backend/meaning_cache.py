"""뜻풀이 결과 캐시 (MongoDB `word_meaning_cache`)

같은 단어 + 같은 문장(+ 연령대)이면 저장해 둔 결과를 쓰고 Gemini를 부르지 않습니다.

- 키: mode("click": 클릭한 말 그대로 / "lemma": 추천 단어처럼 기본형을 아는 경우), word, sentence, age
- Gemini가 실제로 고른 결과(source가 dictionary/ai)만 저장합니다.
  Gemini 실패 시의 예비 결과(fallback, "뜻이 여러 가지예요")는 저장하지 않아서
  Gemini가 돌아오면 다시 제대로 고릅니다.
"""
import re
from datetime import datetime

from database import safe_create_index, word_meaning_cache_collection as cache
from word_meaning import SOURCE_FALLBACK, clean_word, explain_word, explain_words

MODE_CLICK = "click"
MODE_LEMMA = "lemma"
_FIELDS = ("hard", "definition", "dict_definition", "source", "ambiguous")


def _key(mode: str, word: str, sentence: str, age: str) -> dict:
    return {
        "mode": mode,
        "word": clean_word(word),
        "sentence": " ".join((sentence or "").split()),
        "age": (age or "5-7세").strip(),
    }


def _cacheable(result: dict) -> bool:
    return (
        result.get("source") != SOURCE_FALLBACK
        and not result.get("ambiguous")
        and bool(result.get("definition"))
    )


async def ensure_indexes() -> None:
    await safe_create_index(cache, [("mode", 1), ("word", 1), ("sentence", 1), ("age", 1)], unique=True)


async def _get(key: dict):
    doc = await cache.find_one(key)
    if doc:
        await cache.update_one({"_id": doc["_id"]}, {"$inc": {"hits": 1}})
        return {f: doc.get(f) for f in _FIELDS}
    return None


async def _put(key: dict, result: dict) -> None:
    if not _cacheable(result):
        return
    await cache.update_one(
        key,
        {"$set": {**{f: result.get(f) for f in _FIELDS}, "updated_at": datetime.utcnow()},
         "$setOnInsert": {"created_at": datetime.utcnow(), "hits": 0}},
        upsert=True,
    )


async def cached_explain_word(model, word: str, sentence: str, age: str = "5-7세") -> dict:
    key = _key(MODE_CLICK, word, sentence, age)
    if key["word"]:
        hit = await _get(key)
        if hit:
            return hit
    result = await explain_word(model, word, sentence, age)
    if key["word"]:
        await _put(key, result)
    return result


async def cached_explain_words(model, items: list[dict], age: str = "5-7세") -> list[dict]:
    """추천 단어: 캐시에 없는 단어만 모아서 Gemini 1번"""
    keys = [_key(MODE_LEMMA, it["word"], it["sentence"], age) for it in items]
    results: list = [await _get(k) for k in keys]
    missing = [i for i, r in enumerate(results) if r is None]
    if missing:
        fresh = await explain_words(model, [items[i] for i in missing], age)
        for i, r in zip(missing, fresh):
            results[i] = r
            await _put(keys[i], r)
    return results
