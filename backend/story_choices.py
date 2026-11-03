"""선택지 마무리: 이번 장면에 맞게, 이전 장면 선택지와 겹치지 않게 3개.

엔진(Colab → /story/choices → Gemini)이 준 선택지 중 쓸 만한 것만 남기고,
모자라면 장면 본문에서 뽑은 등장인물·장소·물건 낱말로 템플릿 선택지를 만들어 채움 (AI 없이도 매번 다름).
"""
import hashlib
import re
from collections import Counter
from typing import Iterable

from story_text import _jong, _particle_fits

CHOICE_COUNT = 3

# Colab 서버가 선택지 JSON을 못 읽었을 때 돌려주는 기본 선택지 (서버 normalize_choices의 fallback)
COLAB_FALLBACK_CHOICES = ["계속 나아간다", "도움을 요청한다", "잠깐 생각해본다"]

_CHOICE_JUNK = re.compile(r"[\"{}\[\]<>:;`/\\=]")


def is_usable_choice(choice) -> bool:
    """아이에게 보여 줄 만한 선택지인지: 한글이 있고, JSON·코드 찌꺼기가 없고, 길이가 알맞음
    (실제 Colab에서 'javascript', 'description": "…' 같은 선택지가 온 적이 있음)"""
    if not isinstance(choice, str):
        return False
    text = choice.strip()
    hangul = len(re.findall(r"[가-힣]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return 4 <= len(text) <= 60 and hangul >= 3 and latin <= 2 and not _CHOICE_JUNK.search(text)


def _key(choice: str) -> str:
    """겹침 비교용: 한글·숫자만"""
    return re.sub(r"[^가-힣0-9]", "", choice or "")


def _overlaps(choice: str, previous_keys: set[str]) -> bool:
    key = _key(choice)
    if not key:
        return True
    for prev in previous_keys:
        if key == prev or (min(len(key), len(prev)) >= 6 and (key in prev or prev in key)):
            return True
    return False


def acceptable_choices(raw, previous: Iterable[str]) -> list[str]:
    """쓸 만하고, Colab 기본값이 아니고, 이전 장면 선택지와 겹치지 않는 것만 (서로도 안 겹치게)"""
    if not isinstance(raw, list):
        return []
    defaults = {_key(c) for c in COLAB_FALLBACK_CHOICES}
    seen = {_key(c) for c in previous if c}
    result: list[str] = []
    for item in raw:
        if not is_usable_choice(item):
            continue
        text = item.strip()
        if _key(text) in defaults or _overlaps(text, seen):
            continue
        result.append(text)
        seen.add(_key(text))
    return result


# ----------------------------------------
# 장면 본문에서 등장인물 / 장소 / 물건 뽑기 (조사가 붙은 말을 보고 보수적으로)
# ----------------------------------------
_PLACE_WORDS = set(
    "숲 숲속 마을 집 바다 바닷가 성 동굴 산 강 강가 하늘 정원 학교 연못 호수 들판 꽃밭 섬 궁전 "
    "방 부엌 시장 공원 놀이터 언덕 골짜기 우주 별나라 구름 나무 숲길 오솔길 탑 도서관 농장 밭 "
    "해변 사막 빙하 계곡 폭포 시냇가 둥지 굴 오두막 항구 배 기차역".split()
)
_STOP_WORDS = set(
    "그 이 저 것 수 때 날 일 말 곳 거 게 데 줄 뿐 등 중 앞 뒤 안 밖 위 아래 옆 속 끝 처음 길 표정 대답 인사 노래 춤 놀이 걸음 쪽 "
    "우리 모두 누구 무엇 아무 여러분 자기 자신 서로 그것 이것 저것 거기 여기 저기 오늘 내일 어제 "
    "마음 생각 기분 이야기 모습 소리 하루 시간 순간 다음 정말 함께 같이 모든 그날 이후 덕분 사이 "
    "얼굴 눈 손 발 몸 힘 용기 행복 기쁨 사랑 우정 친절 꿈 웃음 소식 변화 사실 결과 사람들 "
    "어린이 아이들 친구들 하나 둘 셋 한 번 누군가 무언가 뭔가 어디 언제 가장 더 아주 너무".split()
)
_CHAR_HINTS = set(
    "토끼 곰 여우 사자 호랑이 고양이 강아지 새 고래 거북 거북이 다람쥐 너구리 부엉이 올빼미 펭귄 코끼리 "
    "기린 원숭이 돼지 오리 병아리 닭 나비 벌 개미 물고기 용 공룡 요정 마법사 공주 왕자 왕 여왕 할머니 "
    "할아버지 엄마 아빠 언니 오빠 누나 형 동생 친구 선생님 아이 소녀 소년 로봇 별님 달님 해님 "
    "천사 인형 아기 꼬마 이웃 주민".split()
)
# 무서운 등장인물은 "손잡고 가 본다", "안아 준다" 같은 선택지에 쓰지 않음
_SCARY = set("악마 마녀 거인 도깨비 괴물 늑대 해적 도둑 유령 마왕".split())
_PARTICLE_RE = re.compile(
    r"([가-힣]{1,6})(에게서|에게|한테|에서|으로|은|는|이|가|을|를|와|과|랑|의|에|로)(?=[\s.,!?~…\"'”’]|$)"
)
_CHAR_PARTICLES = {"에게", "에게서", "한테", "와", "과", "랑"}
_PLACE_PARTICLES = {"에서", "으로", "로", "에"}
_OBJECT_PARTICLES = {"을", "를"}
_SUBJECT_PARTICLES = {"은", "는", "이", "가"}
# 관형형·활용형 어미로 끝나는 말 (조사처럼 보여도 명사가 아님): 했는, 있는, 하던 …
_NOT_NOUN_LAST = set("었았였겠는던할될한된운인다요고서며면게지니까데죠네했해")


def _noun_ok(word: str, particle: str) -> bool:
    if len(word) < 1 or word in _STOP_WORDS or word in _SCARY:
        return False
    if particle in _SUBJECT_PARTICLES | {"을", "를", "와", "과", "랑", "으로", "로"} and not _particle_fits(word, particle):
        return False
    if word[-1] in _NOT_NOUN_LAST and word not in _CHAR_HINTS | _PLACE_WORDS:
        return False
    return True


def _base_noun(word: str) -> str:
    """'숲속' → '숲속', '꼬마토끼' 그대로. 알려진 인물·장소 낱말로 끝나면 그 낱말 (예: '하얀토끼' → '토끼')"""
    for known in sorted(_CHAR_HINTS | _PLACE_WORDS, key=len, reverse=True):
        if word.endswith(known) and len(word) > len(known) and len(word) - len(known) <= 2:
            return known
    return word


def extract_story_words(text: str, protagonist: str = "") -> dict[str, list[str]]:
    """{'characters': [...], 'places': [...], 'objects': [...]} 많이 나온 순서. 주인공은 characters에서 뺌"""
    chars, places, objects = Counter(), Counter(), Counter()
    for m in _PARTICLE_RE.finditer(text or ""):
        word, particle = _base_noun(m.group(1)), m.group(2)
        if not _noun_ok(word, particle):
            continue
        if word in _PLACE_WORDS or (particle in {"에서"} and word not in _CHAR_HINTS):
            places[word] += 1
        elif word in _CHAR_HINTS or particle in _CHAR_PARTICLES:
            chars[word] += 1
        elif particle in _OBJECT_PARTICLES:
            objects[word] += 1
        elif particle in _SUBJECT_PARTICLES and word in _CHAR_HINTS:
            chars[word] += 1
    hero_words = set(re.findall(r"[가-힣]+", protagonist or ""))
    hero = [w for w in chars if w in hero_words or any(w.endswith(h) or h.endswith(w) for h in hero_words if len(h) >= 2)]
    for w in hero:
        del chars[w]
    for w in list(objects):
        if w in hero_words or w in chars or w in places:
            del objects[w]
    return {
        "characters": [w for w, _ in chars.most_common(4)],
        "places": [w for w, _ in places.most_common(4)],
        "objects": [w for w, _ in objects.most_common(4)],
    }


def _josa(word: str, with_jong: str, without_jong: str) -> str:
    return word + (with_jong if _jong(word[-1]) else without_jong)


def _ro(word: str) -> str:
    j = _jong(word[-1])
    return word + ("로" if j == 0 or j == 8 else "으로")


_CHAR_TEMPLATES = [
    lambda c: f"{c}에게 무슨 일인지 물어본다",
    lambda c: f"{_josa(c, '과', '와')} 함께 손잡고 가 본다",
    lambda c: f"{c}에게 도와 달라고 말해 본다",
    lambda c: f"{c}의 이야기를 귀 기울여 들어 본다",
    lambda c: f"{c}에게 고맙다고 인사한다",
    lambda c: f"{_josa(c, '을', '를')} 꼭 안아 준다",
]
_PLACE_TEMPLATES = [
    lambda p: f"{_ro(p)} 살금살금 가 본다",
    lambda p: f"{p} 구석구석을 살펴본다",
    lambda p: f"{p}에서 숨은 친구를 찾아본다",
    lambda p: f"{p}에서 잠깐 쉬어 간다",
    lambda p: f"{p} 너머에 뭐가 있는지 가 본다",
]
# 물건은 무엇인지 확실히 모르니 (들고 갈 수 있는 것인지 등) 어떤 낱말에도 어울리는 행동만
_OBJECT_TEMPLATES = [
    lambda o: f"{_josa(o, '을', '를')} 자세히 살펴본다",
    lambda o: f"{_josa(o, '을', '를')} 가만히 바라본다",
    lambda o: f"{o}에 대해 친구에게 물어본다",
]
_GENERIC_TEMPLATES = [
    "반짝이는 쪽으로 조심조심 걸어가 본다",
    "새로운 친구를 찾아 길을 나선다",
    "노래를 부르며 씩씩하게 걸어간다",
    "잠깐 멈춰서 주위를 둘러본다",
    "작은 소리가 나는 쪽을 살펴본다",
    "친구들에게 좋은 생각을 이야기한다",
    "용기를 내어 먼저 인사를 건넨다",
    "하늘을 올려다보며 길을 찾아본다",
    "누군가 도움이 필요한지 둘러본다",
    "가방을 챙겨 더 멀리 가 본다",
    "맛있는 간식을 친구와 나누어 먹는다",
    "그림을 그려 오늘 일을 기억해 둔다",
]
_WRAP_UP_TEMPLATES = [
    "친구들과 오늘 일을 이야기하며 웃는다",
    "도와준 친구들에게 고맙다고 인사한다",
    "모두 함께 집으로 돌아갈 준비를 한다",
    "다 같이 작은 잔치를 열어 축하한다",
]


def template_choices(text: str, protagonist: str, previous: Iterable[str], seed: str = "",
                     need: int = CHOICE_COUNT, wrap_up: bool = False) -> list[str]:
    """장면 본문의 인물·장소·물건으로 선택지 만들기. 인물 → 장소 → 물건 → 기본 문장 순서로 서로 다른 방향 하나씩"""
    words = extract_story_words(text, protagonist)
    # 이전 선택지에 나온 물건 낱말은 빼기 (예비 장면은 고른 선택지를 본문에 그대로 넣어서 되풀이됨)
    previous = list(previous)
    prev_text = " ".join(previous)
    words["objects"] = [w for w in words["objects"] if w not in prev_text]
    h = int(hashlib.sha256(f"{seed}|{text}".encode("utf-8")).hexdigest(), 16)
    groups: list[list[str]] = []
    for key, templates in (("characters", _CHAR_TEMPLATES), ("places", _PLACE_TEMPLATES), ("objects", _OBJECT_TEMPLATES)):
        options = []
        for wi, word in enumerate(words[key]):
            for ti in range(len(templates)):
                options.append(templates[(ti + h + wi) % len(templates)](word))
        if options:
            groups.append(options)
    generic = _WRAP_UP_TEMPLATES + _GENERIC_TEMPLATES if wrap_up else list(_GENERIC_TEMPLATES)
    shift = h % len(generic)
    groups.append(generic[shift:] + generic[:shift])

    seen = {_key(c) for c in previous if c}
    result: list[str] = []
    # 그룹마다 하나씩 돌아가며 (서로 다른 방향)
    index = [0] * len(groups)
    while len(result) < need and any(index[g] < len(groups[g]) for g in range(len(groups))):
        for g, options in enumerate(groups):
            while index[g] < len(options):
                choice = options[index[g]]
                index[g] += 1
                if not _overlaps(choice, seen):
                    result.append(choice)
                    seen.add(_key(choice))
                    break
            if len(result) == need:
                break
    return result


def finalize_choices(candidates, text: str, protagonist: str, previous: Iterable[str],
                     seed: str = "", wrap_up: bool = False) -> tuple[list[str], int]:
    """엔진 후보 중 쓸 만한 것 + 모자라면 템플릿. (선택지 3개, 템플릿으로 채운 개수)"""
    previous = [p for p in previous if p]
    good = acceptable_choices(candidates, previous)[:CHOICE_COUNT]
    if len(good) == CHOICE_COUNT:
        return good, 0
    filler = template_choices(text, protagonist, previous + good, seed, CHOICE_COUNT - len(good), wrap_up)
    return good + filler, len(filler)
