"""단어 뜻풀이: 기본형 후보 → 표준국어대사전 전체 뜻 조회 → 문맥에 맞는 뜻 고르기 → 사전식 한 문장.

흐름
1. lemma_candidates: 클릭한 말의 기본형 후보를 파이썬으로 만듭니다. (노란 → 노란, 노라다, 노랗다)
2. fetch_senses: 후보마다 search.do로 동음이의어를 찾고, view.do로 각 표제어의 모든 뜻을 가져옵니다.
3. pick_definitions: Gemini 한 번으로 문맥에 맞는 기본형과 뜻을 고르고, 국어사전 형식의 한 문장으로 다듬습니다.
   사전에 맞는 뜻이 없으면 Gemini가 문맥에 맞게 직접 씁니다.
   (무료 할당량이 작아서 원형 정제와 뜻 고르기를 한 번의 호출로 묶었습니다)

뜻풀이 형식(팝업·단어장·추천 단어 공통): 국어사전처럼 간결한 한 문장, 마침표로 끝.
  예) 따뜻하다 → "춥지 않고 알맞게 따뜻하다."  반짝이다 → "빛이 작게 잠깐씩 나타났다 사라지다."
"""
import asyncio
import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

SEARCH_URL = "https://stdict.korean.go.kr/api/search.do"
VIEW_URL = "https://stdict.korean.go.kr/api/view.do"

MAX_HOMONYMS = 6          # 기본형 하나당 동음이의어 최대 개수
MAX_SENSES_PER_WORD = 12  # 표제어 하나당 뜻 최대 개수
MAX_SENSES_TOTAL = 30     # 기본형 하나당 Gemini에 넘기는 뜻 최대 개수

SOURCE_DICT = "dictionary"   # 사전 뜻을 골라 다듬음
SOURCE_AI = "ai"             # 사전에 맞는 뜻이 없어 Gemini가 직접 씀
SOURCE_FALLBACK = "fallback" # Gemini 실패 → 사전 첫 뜻 그대로

STYLE_RULES = """[뜻풀이 형식 규칙]
- 국어사전처럼 간결하게 '한 문장'으로 쓴다. 마침표(.)로 끝낸다.
- 동사·형용사는 '~다.'로 끝낸다. (예: 따뜻하다 → "춥지 않고 알맞게 따뜻하다.", 반짝이다 → "빛이 작게 잠깐씩 나타났다 사라지다.")
- 명사는 '~것.', '~일.', '~사람.'처럼 명사로 끝낸다. (예: 달 → "밤하늘에 떠서 빛나는 둥근 천체.")
- 말을 거는 말투(~해요, ~랍니다, ~예요, ~거야), 감탄, 이모지, 따옴표를 쓰지 않는다.
- 뜻풀이 안에 그 단어 자체를 되풀이하지 않는다.
- 사전 뜻이 어려우면 같은 뜻을 쉬운 낱말로 바꿔 쓰되, 형식은 위 규칙을 지킨다.
- '또는 ~' 처럼 문맥과 상관없는 덧붙임 뜻은 뺀다."""


def _dict_key() -> Optional[str]:
    return os.getenv("KOREAN_DICT_API_KEY")


def _log(where: str, e: Exception) -> None:
    print(f"[뜻풀이 오류] {where}: {type(e).__name__}: {str(e).splitlines()[0][:200]}", flush=True)


def _clean_headword(word: str) -> str:
    """사전 표제어 표기(반짝-이다, 노랗^다, 숫자) 정리"""
    return re.sub(r"[-^ˇ\d]", "", word or "").strip()


def to_dictionary_style(text: str) -> str:
    """혹시 남은 군더더기를 정리해 '한 문장 + 마침표' 형식으로 맞춥니다."""
    text = re.sub(r"[\"'“”‘’`*#]", "", (text or "").strip())
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)  # 이모지
    text = " ".join(text.split())
    if not text:
        return ""
    m = re.search(r"[.!?。](\s|$)", text)
    if m:
        text = text[: m.start()]
    text = text.rstrip(" .!?~。")
    return f"{text}." if text else ""


def _gemini_json(text: str):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    return json.loads(text)


# ----------------------------------------
# 1. 기본형 후보 (Gemini 호출 없이)
#    관형형/활용형 → 기본형: 노란→노랗다, 반짝이는→반짝이다, 푹신한→푹신하다, 예쁜→예쁘다, 귀여운→귀엽다
#    후보를 모두 사전에서 찾아 두고, Gemini가 문맥에 맞는 기본형과 뜻을 함께 고릅니다.
#    후보에 없는 활용형(떠났답니다 등)은 Gemini가 알려 준 기본형으로 다시 찾습니다.
# ----------------------------------------
_PARTICLES = r"(이랑|으로|에서|에게|께서|처럼|보다|까지|부터|은|는|이|가|을|를|과|와|로|도|만|의|에|랑)$"
_JONG_N, _JONG_B, _JONG_H = 4, 17, 27


def _jong(ch: str) -> int:
    code = ord(ch) - 0xAC00
    return code % 28 if 0 <= code < 11172 else -1


def _with_jong(ch: str, jong: int) -> str:
    code = ord(ch) - 0xAC00
    return chr(0xAC00 + code - code % 28 + jong)


def clean_word(word: str) -> str:
    return re.sub(r"[^\w가-힣]", "", word or "")


def lemma_candidates(word: str) -> list[str]:
    w = clean_word(word)
    if not w:
        return []
    cands = [w, re.sub(_PARTICLES, "", w)]
    last, stem = w[-1], w[:-1]
    if stem:
        if last == "는":                           # 반짝이는 → 반짝이다, 먹는 → 먹다
            cands.append(stem + "다")
        if last == "한":                           # 푹신한 → 푹신하다
            cands.append(stem + "하다")
        if last == "은":                           # 작은 → 작다
            cands.append(stem + "다")
        if last == "운" and _jong(stem[-1]) == 0:  # 귀여운 → 귀엽다
            cands.append(stem[:-1] + _with_jong(stem[-1], _JONG_B) + "다")
    if _jong(last) == _JONG_N:
        cands.append(stem + _with_jong(last, 0) + "다")        # 예쁜 → 예쁘다, 큰 → 크다
        cands.append(stem + _with_jong(last, _JONG_H) + "다")  # 노란 → 노랗다, 하얀 → 하얗다
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


# ----------------------------------------
# 2. 사전 뜻 전부 가져오기
# ----------------------------------------
async def _search_homonyms(client: httpx.AsyncClient, word: str) -> list[dict]:
    res = await client.get(SEARCH_URL, params={
        "key": _dict_key(), "q": word, "req_type": "xml", "part": "word", "num": 20,
    })
    root = ET.fromstring(res.text)
    items = []
    for item in root.findall(".//item"):
        if _clean_headword(item.findtext("word") or "") != word:
            continue
        sense = item.find("sense")
        items.append({
            "target_code": (item.findtext("target_code") or "").strip(),
            "pos": (item.findtext("pos") or "").strip(),
            "first_definition": ((sense.findtext("definition") if sense is not None else "") or "").strip(),
        })
    return items[:MAX_HOMONYMS]


async def _view_senses(client: httpx.AsyncClient, homonym: dict) -> list[dict]:
    """표제어 하나의 모든 뜻. 실패하면 검색 결과의 첫 뜻만."""
    fallback = [{"pos": homonym["pos"], "definition": homonym["first_definition"], "example": ""}]
    fallback = fallback if homonym["first_definition"] else []
    try:
        res = await client.get(VIEW_URL, params={
            "key": _dict_key(), "q": homonym["target_code"], "req_type": "xml", "method": "target_code",
        })
        root = ET.fromstring(res.text)
        senses = []
        for pos_info in root.iter("pos_info"):
            pos = (pos_info.findtext("pos") or homonym["pos"]).strip()
            for sense in pos_info.iter("sense_info"):
                definition = (sense.findtext("definition") or "").strip()
                if definition:
                    example = (sense.findtext("example_info/example") or "").strip()
                    senses.append({"pos": pos, "definition": definition, "example": example})
        return senses[:MAX_SENSES_PER_WORD] or fallback
    except Exception as e:
        _log(f"사전 상세 조회({homonym['target_code']})", e)
        return fallback


async def fetch_senses(word: str, client: Optional[httpx.AsyncClient] = None) -> list[dict]:
    """기본형의 모든 동음이의어·다의어 뜻 [{pos, definition, example}]"""
    if not word or not _dict_key():
        return []
    own = client is None
    client = client or httpx.AsyncClient(timeout=6.0)
    try:
        homonyms = await _search_homonyms(client, word)
        groups = await asyncio.gather(*[_view_senses(client, h) for h in homonyms])
        # homonym: 몇 번째 동음이의어인지 (Gemini 실패 시 동음이의어별 대표 뜻을 고르는 데 씀)
        return [{**s, "homonym": n} for n, g in enumerate(groups) for s in g][:MAX_SENSES_TOTAL]
    except Exception as e:
        _log(f"사전 검색({word})", e)
        return []
    finally:
        if own:
            await client.aclose()


# ----------------------------------------
# 3. 문맥에 맞는 기본형 + 뜻 고르기 (여러 단어를 Gemini 한 번으로)
# ----------------------------------------
def _entry_block(n: int, entry: dict, numbered: list) -> str:
    lines = [f"[단어 {n}] {entry['word']}", f"문장: \"{entry['sentence']}\"", "사전 뜻 후보:"]
    for lemma, senses in entry["candidates"].items():
        if not senses:
            continue
        lines.append(f"  <기본형: {lemma}>")
        for sense in senses:
            numbered.append((lemma, sense))
            ex = f" (예: {sense['example']})" if sense.get("example") else ""
            lines.append(f"    {len(numbered)}. [{sense['pos']}] {sense['definition']}{ex}")
    if not numbered:
        lines.append("  (사전에서 찾은 뜻이 없음)")
    return "\n".join(lines)


async def pick_definitions(model, entries: list[dict], age: str = "5-7세") -> list[dict]:
    """entries: [{word, sentence, candidates: {기본형: [뜻...]}, default_lemma}]
    → 같은 순서의 [{hard, definition, dict_definition, source}]
    """
    if not entries:
        return []
    numbered_per_entry: list[list] = []
    blocks = []
    for n, e in enumerate(entries, 1):
        numbered: list = []
        blocks.append(_entry_block(n, e, numbered))
        numbered_per_entry.append(numbered)

    prompt = f"""너는 국어사전 편찬자야. 아래 각 단어가 주어진 문장에서 어떤 기본형, 어떤 뜻으로 쓰였는지 판단해.
- 'lemma': 그 단어의 국어사전 기본형. 동사·형용사의 관형형·활용형은 '~다' 기본형으로 (노란→노랗다, 반짝이는→반짝이다, 푹신한→푹신하다).
- 'choice': 사전 뜻 후보 중 문장 문맥과 품사에 맞는 뜻의 번호. 소리만 같은 엉뚱한 뜻(예: '노란 달님'의 '노란'을 명사 '노란(虜亂)'으로 보는 것)을 고르지 마.
  맞는 후보가 없거나 후보가 비어 있으면 0.
- 'definition': 고른 뜻을 {age} 아이도 이해할 쉬운 낱말로 다듬은 뜻풀이. choice가 0이면 문맥에 맞는 뜻을 네가 직접 써.

{STYLE_RULES}

{chr(10).join(blocks)}

JSON 배열로만 답해. 단어 순서대로 하나씩:
[{{"index": 1, "lemma": "기본형", "choice": 2, "definition": "사전식 한 문장."}}]"""

    results: list[Optional[dict]] = [None] * len(entries)
    try:
        res = await model.generate_content_async(
            prompt, generation_config={"response_mime_type": "application/json"}
        )
        data = _gemini_json(res.text)
        if isinstance(data, dict):
            data = [data]
        for k, row in enumerate(data if isinstance(data, list) else []):
            if not isinstance(row, dict):
                continue
            try:
                idx = int(row.get("index") or k + 1) - 1
                choice = int(row.get("choice") or 0)
            except (TypeError, ValueError):
                continue
            if not 0 <= idx < len(entries):
                continue
            numbered = numbered_per_entry[idx]
            lemma = clean_word(str(row.get("lemma") or ""))
            chosen = ""
            if 1 <= choice <= len(numbered):
                lemma, sense = numbered[choice - 1]  # 고른 뜻의 기본형을 따릅니다.
                chosen = sense["definition"]
            definition = to_dictionary_style(row.get("definition") or "") or to_dictionary_style(chosen)
            if definition:
                results[idx] = {
                    "hard": lemma or entries[idx]["default_lemma"],
                    "definition": definition,
                    "dict_definition": chosen,
                    "source": SOURCE_DICT if chosen else SOURCE_AI,
                    "ambiguous": False,
                }
    except Exception as e:
        _log("문맥 뜻 고르기", e)

    # Gemini가 실패했거나 빠뜨린 단어: 사전에 있는 마지막 후보(용언 기본형일 가능성이 큼)
    for i, e in enumerate(entries):
        if results[i] is None:
            found = [(lemma, senses) for lemma, senses in e["candidates"].items() if senses]
            lemma, senses = found[-1] if found else (e["default_lemma"], [])
            results[i] = fallback_result(lemma, senses)
    return results


AMBIGUOUS_TITLE = "뜻이 여러 가지예요."
MAX_AMBIGUOUS_SHOWN = 3
SHORT_DEFINITION_LEN = 40


def _short(definition: str) -> str:
    text = to_dictionary_style(definition)
    if len(text) <= SHORT_DEFINITION_LEN:
        return text
    cut = text[:SHORT_DEFINITION_LEN]
    cut = cut[: cut.rfind(" ")] if " " in cut else cut
    return cut.rstrip(" ,.") + "…"


def _representative_senses(senses: list[dict]) -> list[dict]:
    """동음이의어마다 대표 뜻(첫 뜻)을 먼저, 모자라면 나머지 뜻으로 채워 최대 3개"""
    firsts, rest, seen = [], [], set()
    for s in senses:
        (rest if s.get("homonym") in seen else firsts).append(s)
        seen.add(s.get("homonym"))
    return (firsts + rest)[:MAX_AMBIGUOUS_SHOWN]


def fallback_result(lemma: str, senses: list[dict]) -> dict:
    """Gemini 없이 보여줄 뜻.

    - 사전 뜻이 1개뿐이면 그대로 보여줍니다.
    - 여러 개면 엉뚱한 동음이의어를 고르지 않도록 "뜻이 여러 가지예요" + 짧은 뜻 2~3개를 번호로 보여주고,
      ambiguous=True로 표시합니다. (단어장에 확정 뜻으로 저장하지 않고, 나중에 다시 고릅니다)
    """
    base = {"hard": lemma, "source": SOURCE_FALLBACK}
    if len(senses) <= 1:
        first = senses[0]["definition"] if senses else ""
        return {**base, "definition": to_dictionary_style(first), "dict_definition": first, "ambiguous": False}
    picked = _representative_senses(senses)
    lines = [AMBIGUOUS_TITLE] + [f"{n}. {_short(s['definition'])}" for n, s in enumerate(picked, 1)]
    return {**base, "definition": "\n".join(lines), "dict_definition": "", "ambiguous": True}


def is_ambiguous_text(text: str) -> bool:
    return (text or "").strip().startswith(AMBIGUOUS_TITLE)


async def explain_word(model, word: str, sentence: str, age: str = "5-7세") -> dict:
    """단어 클릭 팝업 / 단어 저장용: {hard, definition, dict_definition, source, ambiguous}"""
    lemmas = lemma_candidates(word)
    if not lemmas:
        return fallback_result("", [])
    async with httpx.AsyncClient(timeout=6.0) as client:
        sense_lists = await asyncio.gather(*[fetch_senses(l, client) for l in lemmas])
    candidates = dict(zip(lemmas, sense_lists))
    entry = {"word": clean_word(word), "sentence": sentence, "candidates": candidates,
             "default_lemma": lemmas[1] if len(lemmas) > 1 else lemmas[0]}
    result = (await pick_definitions(model, [entry], age))[0]

    # 후보에 없던 기본형을 Gemini가 알려 줬다면(예: 떠났답니다 → 떠나다) 그 기본형의 사전 뜻으로 다시 고릅니다.
    if result["source"] == SOURCE_AI and result["hard"] not in candidates:
        senses = await fetch_senses(result["hard"])
        if senses:
            retry = {"word": result["hard"], "sentence": sentence,
                     "candidates": {result["hard"]: senses}, "default_lemma": result["hard"]}
            again = (await pick_definitions(model, [retry], age))[0]
            if again["source"] != SOURCE_FALLBACK:
                result = again
    return result


async def explain_words(model, items: list[dict], age: str = "5-7세") -> list[dict]:
    """기본형을 이미 아는 여러 단어(추천 단어): items [{word, sentence}] → 같은 순서의 결과 (Gemini 1번)"""
    async with httpx.AsyncClient(timeout=6.0) as client:
        sense_lists = await asyncio.gather(*[fetch_senses(it["word"], client) for it in items])
    entries = [
        {"word": it["word"], "sentence": it["sentence"], "candidates": {it["word"]: senses},
         "default_lemma": it["word"]}
        for it, senses in zip(items, sense_lists)
    ]
    return await pick_definitions(model, entries, age)


def sentence_with(text: str, needles: list[str]) -> str:
    """본문에서 단어가 들어 있는 문장 하나를 찾습니다. (추천 단어의 문맥용)"""
    sentences = re.split(r"(?<=[.!?。])\s+|\n+", text or "")
    for needle in needles:
        if not needle:
            continue
        for s in sentences:
            if needle in s:
                return s.strip()
    return ""
