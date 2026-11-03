"""동화 본문 기반 추천 단어 3~5개 (Gemini + 파이썬 2차 검증 + 문맥 뜻풀이)

기존 /api/generate-story에 있던 로직을 그대로 옮겨서, 분기형 동화 완료 때도 같이 씁니다.
"""
import json

from meaning_cache import cached_explain_words
from word_meaning import sentence_with, to_dictionary_style


def word_in_story(item: dict, story_text: str) -> bool:
    """추천 단어가 동화 본문에 실제로 들어 있는지 확인합니다.

    - surface: Gemini가 알려준 '본문에 쓰인 그대로'의 표현
    - hard: 기본형 (용언이면 끝의 '다'를 뗀 어간도 확인. 예: '떠나다' → '떠나')
    """
    surface = (item.get("surface") or "").strip()
    hard = (item.get("hard") or "").strip()
    if surface and surface in story_text:
        return True
    if not hard:
        return False
    if hard in story_text:
        return True
    if hard.endswith("다") and len(hard) >= 3 and hard[:-1] in story_text:
        return True
    return False


def _vocab_prompt(story_text: str, age: str) -> str:
    return f"""
    너는 다정한 어린이 언어 선생님이야.
    아래 [동화 텍스트]를 자세히 읽고, **반드시 텍스트 안에 실제로 등장하는 어휘/표현 중에서만** {age} 어린이가 학습하기 좋은 주요 단어 3~5개를 선택해줘.

    [동화 텍스트]
    {story_text}

    [필수 규칙]
    1. 'surface' 항목은 동화 텍스트에 쓰인 모습 그대로 복사할 것. (예: '날아갔어요')
    2. 'hard' 항목은 그 단어의 조사/어미를 뗀 기본형/원형으로 작성할 것. (예: '날아가다')
    3. 절대 동화 텍스트 본문에 없는 단어를 지어내지 마!
    4. 'definition': 국어사전처럼 간결한 한 문장 (동사·형용사는 '~다.', 명사는 명사로 끝냄. '~해요/~랍니다' 말투 금지).

    반드시 아래 JSON 배열 형식으로만 응답해줘:
    [
      {{
        "surface": "본문에 쓰인 그대로의 표현",
        "hard": "본문에 있는 단어 원형",
        "definition": "사전식 한 문장."
      }}
    ]
    """


_FALLBACK_VOCAB = [
    {"hard": "여행", "definition": "일이나 구경을 위하여 다른 고장이나 나라에 가는 일."},
    {"hard": "친구", "definition": "가깝게 오래 사귄 사람."},
]


async def recommend_vocab(model, story_text: str, age: str, on_error=None) -> list[dict]:
    """본문에 실제로 있는 단어만 최대 5개. on_error(where, e): Gemini 실패 로그용."""
    try:
        response = await model.generate_content_async(
            _vocab_prompt(story_text, age),
            generation_config={"response_mime_type": "application/json"},
        )
        raw_vocab = json.loads(response.text)
        if not isinstance(raw_vocab, list):
            raise ValueError(f"추천 단어 응답이 배열이 아님: {type(raw_vocab).__name__}")
    except Exception as e:
        if on_error:
            on_error("추천 단어 추출", e)
        raw_vocab = _FALLBACK_VOCAB

    # 최종 목록: 동화 본문에 실제로 들어 있는 단어만 (예비용 기본 단어도 동일하게 검증)
    vocab_list = []
    seen = set()
    for item in raw_vocab:
        if not isinstance(item, dict):
            continue
        hard = (item.get("hard") or "").strip()
        if not hard or hard in seen:
            continue
        if word_in_story(item, story_text):
            vocab_list.append(item)
            seen.add(hard)
        else:
            print(f"[추천 단어 제외] 본문에 없음: {hard!r}", flush=True)
        if len(vocab_list) >= 5:
            break

    # 추천 단어 뜻: 본문 문장 문맥에 맞는 사전 뜻으로 맞춥니다. (단어 클릭 팝업과 같은 형식, Gemini 1번)
    if vocab_list:
        items = []
        for item in vocab_list:
            hard = item["hard"].strip()
            needles = [(item.get("surface") or "").strip(), hard, hard[:-1] if hard.endswith("다") else ""]
            item["sentence"] = sentence_with(story_text, needles)  # 단어장 저장 때 다시 고를 문맥
            items.append({"word": hard, "sentence": item["sentence"]})
        for item, found in zip(vocab_list, await cached_explain_words(model, items, age)):
            item["definition"] = found["definition"] or to_dictionary_style(item.get("definition") or "")
            item["dict_definition"] = found["dict_definition"]
            item["ambiguous"] = found["ambiguous"]
    return vocab_list
