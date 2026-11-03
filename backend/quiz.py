"""단어장 퀴즈 문제 만들기 (DB와 무관한 순수 함수 모음)."""
import random
import re
from typing import Optional

QUESTION_COUNT = 5
CHOICE_COUNT = 4
MASK = "○○"

# 사전 조회가 실패했을 때 저장되는 문구는 뜻풀이로 쓰지 않습니다.
INVALID_MEANINGS = {"", "표준 사전 정의를 찾을 수 없습니다.", "사전 정보 불러오기 실패"}

# 저장 단어가 부족할 때 오답 보기로 쓰는 5~7세 수준의 쉬운 단어
BASIC_WORDS = [
    "사과", "토끼", "나무", "구름", "바다", "기차", "우산", "모자", "강아지", "고양이",
    "별", "달", "꽃", "친구", "엄마", "학교", "의자", "신발", "풍선", "비행기",
    "웃다", "달리다", "먹다", "자다", "놀다", "크다", "작다", "예쁘다", "기쁘다", "따뜻하다",
]


def _first_valid(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        text = (item.get(key) or "").strip()
        if text not in INVALID_MEANINGS:
            return text
    return ""


def friendly_meaning(item: dict) -> str:
    """저장된 단어의 뜻풀이 (퀴즈용). meaning = 문맥에 맞춘 사전식 한 문장."""
    return _first_valid(item, ("meaning", "easy_meaning", "official_definition"))


def card_definition(item: dict) -> str:
    """단어장 카드용: 문맥에 맞춘 사전식 뜻(meaning)을 먼저.

    official_definition은 예전에 사전 '첫 뜻'을 그대로 저장한 값이라
    동음이의어(노란 → 호인들이 일으킨 난리)가 섞여 있을 수 있어 마지막에만 씁니다.
    """
    return _first_valid(item, ("meaning", "easy_meaning", "official_definition"))


def mask_word(definition: str, word: str) -> str:
    """뜻풀이 안에 정답 단어가 그대로 보이면 ○○로 가립니다. ('달리다'는 '달리'도 가림)"""
    forms = {word}
    if word.endswith("다") and len(word) >= 3:
        forms.add(word[:-1])
    for form in sorted(forms, key=len, reverse=True):
        definition = definition.replace(form, MASK)
    return definition


def build_questions(vocabs: list[dict], rng: Optional[random.Random] = None) -> list[dict]:
    """저장 단어 목록으로 4지선다 문제를 최대 5개 만듭니다.

    - 아직 못 외운 단어(is_mastered=False)를 먼저, 외운 단어는 남는 자리에만 씁니다.
    - 오답 보기는 다른 저장 단어에서 고르고, 모자라면 BASIC_WORDS로 채웁니다.
    """
    rng = rng or random.Random()

    # 같은 단어가 여러 번 저장되어 있어도 보기는 한 번만 나오게 합니다.
    unique: dict[str, dict] = {}
    for item in vocabs:
        word = (item.get("word") or "").strip()
        if word and word not in unique:
            unique[word] = item

    # 뜻을 아직 못 고른 단어("뜻이 여러 가지예요")는 문제로 내지 않습니다.
    candidates = [
        item for item in unique.values()
        if friendly_meaning(item) and not item.get("meaning_pending")
    ]
    learning = [item for item in candidates if not item.get("is_mastered")]
    mastered = [item for item in candidates if item.get("is_mastered")]
    rng.shuffle(learning)
    rng.shuffle(mastered)
    picked = (learning + mastered)[:QUESTION_COUNT]

    all_words = list(unique.keys())
    questions = []
    for item in picked:
        answer = item["word"].strip()
        wrong_pool = [w for w in all_words if w != answer]
        rng.shuffle(wrong_pool)
        wrongs = wrong_pool[: CHOICE_COUNT - 1]

        if len(wrongs) < CHOICE_COUNT - 1:
            basic_pool = [w for w in BASIC_WORDS if w != answer and w not in wrongs]
            rng.shuffle(basic_pool)
            wrongs += basic_pool[: CHOICE_COUNT - 1 - len(wrongs)]

        choices = wrongs + [answer]
        rng.shuffle(choices)
        questions.append({
            "vocab_id": str(item["_id"]),
            "definition": mask_word(friendly_meaning(item), answer),
            "choices": choices,
            "answer": answer,
            "is_mastered": bool(item.get("is_mastered")),
        })
    return questions
