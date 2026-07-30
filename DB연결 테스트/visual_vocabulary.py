import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional


CLASSIFIER_VERSION = 1
VISUAL_ROLES = (
    "place",
    "action",
    "emotion",
    "object",
    "environment_effect",
)

ROLE_KEYWORDS = {
    "place": (
        "장소", "곳", "지역", "공간", "숲", "수풀", "산", "바다", "강",
        "호수", "연못", "마을", "집", "방", "길", "골목", "동굴",
        "섬", "계곡", "정원", "마당",
    ),
    "action": (
        "행동", "움직", "이동", "걷", "달리", "뛰", "오르", "내리",
        "열다", "닫다", "잡다", "던지", "흔들", "돌다", "숨다",
        "찾다", "살피", "외치", "옮기", "밀다", "당기", "돕다",
        "구하다", "건너", "타다",
    ),
    "emotion": (
        "감정", "마음", "기분", "기쁘", "슬프", "두렵", "무섭",
        "놀라", "화가", "용기", "다정", "외롭", "부끄", "신기",
        "걱정", "즐겁", "행복", "그립",
    ),
    "object": (
        "물건", "도구", "기구", "재료", "열매", "병", "그릇", "끈",
        "막대기", "장난감", "통나무", "기와", "마개", "저울", "비늘",
        "책", "열쇠", "망원경", "등불",
    ),
    "environment_effect": (
        "날씨", "바람", "빛", "불꽃", "그림자", "안개", "비", "눈",
        "구름", "파도", "회오리", "번개", "천둥", "달빛", "햇빛",
        "어둡", "밝",
    ),
}

ABSTRACT_KEYWORDS = (
    "생각", "관계", "정도", "방법", "이유", "상태", "기준", "의견",
    "요구", "과정", "결과", "형편", "일반", "시간",
)

EXACT_ROLE_WORDS = {
    "place": {"수풀", "마을", "골목", "동굴", "정원", "마당", "들판"},
    "emotion": {"심정", "두려움", "기쁨", "걱정", "외로움", "용기"},
    "object": {
        "통나무", "기와", "마개", "저울", "비늘", "회초리", "열쇠",
        "망원경", "잠수함",
    },
    "environment_effect": {
        "회오리", "불덩이", "바람", "안개", "그림자", "달빛", "햇빛",
        "폭풍", "번개", "천둥", "파도", "불꽃", "발소리",
    },
}

BACKGROUND_HINTS = {
    "fantasy_castle": (
        "마법", "주문", "별", "달빛", "신비", "신통", "성", "요정",
    ),
    "adventure_ruins": (
        "산", "바위산", "유적", "길", "모험", "절벽", "폭포", "말타기",
        "탐험",
    ),
    "nature_pond": (
        "숲", "수풀", "나무", "연못", "풀", "꽃", "물고기", "열매",
        "통나무", "나무토막", "이슬", "들판", "물길",
    ),
    "friendship_square": (
        "친구", "마을", "아랫마을", "윗마을", "건넛마을", "공원", "집",
        "기와집", "빈집", "한집", "웃음", "약속", "다정", "반기",
    ),
    "mystery_library": (
        "단서", "열쇠", "도서관", "발소리", "그림자", "비밀", "수상",
        "책",
    ),
}

ACTION_HINTS = {
    "casting-magic": ("마법", "주문", "요술"),
    "walking": ("걷다", "걸어", "걸었", "다가", "이동", "떠나", "길을 나서", "따라가"),
    "investigating": ("찾", "살피", "관찰", "단서", "발견", "조사"),
    "helping": ("돕", "구하", "구출", "돌보", "보살피"),
    "waving": ("인사", "반기", "손을 흔들", "환영"),
}

EMOTION_HINTS = {
    "joyful": ("기쁘", "즐겁", "행복", "웃", "신나"),
    "afraid": ("두렵", "무섭", "겁", "걱정"),
    "curious": ("궁금", "호기심", "신기", "살피"),
    "caring": ("다정", "돕", "돌보", "보살피"),
}

EFFECT_HINTS = {
    "whirlwind": ("회오리", "소용돌이"),
    "strong_wind": ("거센 바람", "강풍", "휩쓸"),
    "glowing_light": (
        "빛", "빛깔", "얼굴빛", "보랏빛", "푸른빛", "반짝", "환히",
        "달빛", "햇빛",
    ),
    "mist": ("안개", "서리"),
    "fire": ("불꽃", "불덩이", "모닥불"),
}

MATCH_TERM_OVERRIDES = {
    "걷다": ["걸어", "걸었", "걸으", "걸음"],
    "돕다": ["돕", "도와", "도우"],
    "듣다": ["들어", "들었"],
    "묻다": ["물어", "물었"],
    "붓다": ["부어", "부었"],
}


def normalize_text(value: Optional[str]) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return " ".join(normalized.split())


def _contains_any(text: str, keywords: Iterable[str]) -> List[str]:
    return [keyword for keyword in keywords if normalize_text(keyword) in text]


def _normalize_pos(document: Dict[str, Any]) -> str:
    pos = normalize_text(
        document.get("pos_group") or document.get("part_of_speech")
    )
    if "동사" in pos:
        return "verb"
    if "형용사" in pos:
        return "adjective"
    if "부사" in pos:
        return "adverb"
    if "명사" in pos:
        return "noun"
    return "unknown"


def _hint_values(text: str, mapping: Dict[str, Iterable[str]]) -> List[str]:
    def matches(keyword: str) -> bool:
        normalized_keyword = normalize_text(keyword)
        if len(normalized_keyword) == 1:
            return text == normalized_keyword
        return normalized_keyword in text

    return sorted(
        key for key, keywords in mapping.items() if any(matches(item) for item in keywords)
    )


def classify_fit_vocabulary(document: Dict[str, Any]) -> Dict[str, Any]:
    word = normalize_text(document.get("word") or document.get("original_word"))
    meaning = normalize_text(
        document.get("child_friendly_meaning") or document.get("meaning")
    )
    combined = f"{word} {meaning}".strip()
    pos = _normalize_pos(document)

    scores = {role: 0 for role in VISUAL_ROLES}
    evidence = {role: [] for role in VISUAL_ROLES}
    for role in VISUAL_ROLES:
        if word in EXACT_ROLE_WORDS.get(role, set()):
            scores[role] += 8
            evidence[role].append(f"exact_word:{word}")
        matches = _contains_any(combined, ROLE_KEYWORDS[role])
        if matches:
            scores[role] += min(10, 5 + len(matches))
            evidence[role].extend(f"meaning_keyword:{item}" for item in matches[:5])

    if pos == "verb":
        scores["action"] += 3
        evidence["action"].append("pos:verb")
    elif pos in {"adjective", "adverb"}:
        scores["emotion"] += 2
        evidence["emotion"].append(f"pos:{pos}")
    elif pos == "noun":
        for role in ("place", "object", "environment_effect"):
            if scores[role]:
                scores[role] += 2
                evidence[role].append("pos:noun")

    abstract_matches = _contains_any(combined, ABSTRACT_KEYWORDS)
    non_visual_score = min(12, len(abstract_matches) * 3)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    selected_roles = [role for role, score in ranked if score >= 5]
    highest_score = ranked[0][1]
    second_score = ranked[1][1]
    ambiguous = (
        len(selected_roles) > 1
        and highest_score > 0
        and highest_score - second_score <= 2
    )
    if not selected_roles or non_visual_score >= highest_score:
        primary_role = "non_visual"
        selected_roles = []
    else:
        primary_role = ranked[0][0]

    match_terms = [word] if len(word) >= 2 else []
    if pos in {"verb", "adjective"} and word.endswith("다") and len(word) >= 3:
        match_terms.append(word[:-1])
    match_terms.extend(MATCH_TERM_OVERRIDES.get(word, []))

    background_keys = _hint_values(word, BACKGROUND_HINTS)
    action_tags = _hint_values(word, ACTION_HINTS)
    emotion_tags = _hint_values(word, EMOTION_HINTS)
    effect_tags = _hint_values(word, EFFECT_HINTS)
    exact_visual_word = any(
        word in role_words for role_words in EXACT_ROLE_WORDS.values()
    )
    usable_for_image = primary_role != "non_visual" and bool(
        exact_visual_word
        or background_keys
        or action_tags
        or emotion_tags
        or effect_tags
    )

    return {
        "word": word,
        "meaning": meaning,
        "pos_group": pos,
        "primary_role": primary_role,
        "visual_roles": selected_roles,
        "role_scores": scores,
        "confidence": round(min(1.0, highest_score / 12.0), 3),
        "ambiguous": ambiguous,
        "evidence": sorted(
            {
                item
                for role in selected_roles
                for item in evidence.get(role, [])
            }
        ),
        "match_terms": sorted(set(match_terms), key=lambda item: (-len(item), item)),
        "background_keys": background_keys,
        "action_tags": action_tags,
        "emotion_tags": emotion_tags,
        "effect_tags": effect_tags,
        "usable_for_image": usable_for_image,
        "classifier_version": CLASSIFIER_VERSION,
    }


def match_visual_vocabulary(
    story_text: str,
    vocabulary_documents: Iterable[Dict[str, Any]],
    *,
    limit: int = 20,
) -> Dict[str, Any]:
    normalized_story = normalize_text(story_text)
    matches = []
    for document in vocabulary_documents:
        if not document.get("enabled", True) or not document.get(
            "usable_for_image",
            True,
        ):
            continue
        terms = [
            normalize_text(term)
            for term in document.get("match_terms", [])
            if len(normalize_text(term)) >= 2
        ]
        matched_terms = [term for term in terms if term in normalized_story]
        if not matched_terms:
            continue
        fit_score = document.get("fit_score") or 0
        try:
            fit_score = float(fit_score)
        except (TypeError, ValueError):
            fit_score = 0.0
        matches.append(
            {
                "word": document.get("word"),
                "primary_role": document.get("primary_role"),
                "matched_term": max(matched_terms, key=len),
                "fit_score": fit_score,
                "background_keys": document.get("background_keys", []),
                "action_tags": document.get("action_tags", []),
                "emotion_tags": document.get("emotion_tags", []),
                "effect_tags": document.get("effect_tags", []),
            }
        )

    matches.sort(
        key=lambda item: (
            -len(item["matched_term"]),
            -item["fit_score"],
            str(item["word"]),
        )
    )
    matches = matches[:limit]

    def collect(key: str) -> List[str]:
        return sorted(
            {
                value
                for match in matches
                for value in match.get(key, [])
                if value
            }
        )

    return {
        "matched_words": [match["word"] for match in matches],
        "matches": matches,
        "background_keys": collect("background_keys"),
        "action_tags": collect("action_tags"),
        "emotion_tags": collect("emotion_tags"),
        "effect_tags": collect("effect_tags"),
        "match_score": round(
            sum(1.0 + min(match["fit_score"], 100.0) / 100.0 for match in matches),
            3,
        ),
    }
