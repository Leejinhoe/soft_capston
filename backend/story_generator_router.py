"""Story generation service router providing /story/start, /story/continue,
/story/psych, /story/characters, /story/character-chat, and /health endpoints.

Ensures the Flutter app can start and continue stories, analyze psychology,
chat with story characters, and send letters end-to-end even in offline/local
mode, producing valid rich Korean fairy tales with choices, vocab, and scene
contracts compatible with KOTE emotion analysis and MongoDB persistence.
"""

from datetime import datetime
import json
import logging
import re
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["story-generation"])

def _vocab_entry(hard: str, easy: str, definition: str) -> Dict[str, str]:
    return {
        "hard": hard,
        "easy": easy,
        "definition": definition,
        "word": hard,
        "meaning": definition,
    }


# Vocabulary dictionary for rich child learning
TEXT_MATCHED_VOCAB: List[Dict[str, str]] = [
    _vocab_entry(
        "나침반",
        "방향을 알려 주는 바늘 도구",
        "바늘이 항상 북쪽을 가리켜 길을 잃지 않게 방향을 알려 주는 도구예요.",
    ),
    _vocab_entry(
        "호기심",
        "새롭고 신기한 것을 알고 싶어 하는 마음",
        "처음 보는 신기한 일이나 물건에 대해 자세히 알고 싶어 하는 마음이에요.",
    ),
    _vocab_entry(
        "다짐",
        "마음을 굳게 정함",
        "어떤 일을 꼭 해내겠다고 스스로 마음을 단단히 먹는 것이에요.",
    ),
    _vocab_entry(
        "정령",
        "숲이나 자연을 지키는 신비한 존재",
        "동화 속에서 나무, 물, 바람 같은 자연에 깃들어 사는 신비로운 존재예요.",
    ),
    _vocab_entry(
        "감탄",
        "마음속 깊이 크게 놀라며 칭찬함",
        "무척 아름답거나 훌륭한 모습을 보고 마음속 깊이 놀라며 느끼는 것이에요.",
    ),
    _vocab_entry(
        "관문",
        "반드시 지나가야 하는 중요한 문",
        "목표한 곳에 도착하기 위해 꼭 통과해야 하는 중요한 문이나 단계예요.",
    ),
    _vocab_entry(
        "해답",
        "어려운 문제를 풀어서 얻은 답",
        "궁금하던 일이나 어려운 문제를 차근차근 생각하여 찾아낸 답이에요.",
    ),
    _vocab_entry(
        "도전",
        "어려운 일에 용기 있게 맞서 봄",
        "조금 어렵거나 새로운 일이라도 포기하지 않고 용기를 내어 해 보는 것이에요.",
    ),
    _vocab_entry(
        "수수께끼",
        "숨겨진 뜻을 알아맞히는 문제",
        "단서나 힌트를 보고 숨겨진 정답을 슬기롭게 찾아내는 문제예요.",
    ),
    _vocab_entry(
        "지혜",
        "바르고 슬기롭게 판단하는 마음의 힘",
        "어려운 상황에서도 이치를 잘 깨닫고 현명하게 해결하는 마음의 힘이에요.",
    ),
]

VOCAB_DATABASE = {
    "판타지": [
        _vocab_entry("별빛", "밤하늘 별에서 나오는 맑은 빛", "밤하늘의 별에서 나오는 맑고 은은한 빛"),
        _vocab_entry("신비", "생각으로 헤아리기 힘들 만큼 묘함", "사람의 생각으로는 헤아릴 수 없을 만큼 묘하고 이상함"),
        _vocab_entry("수호자", "소중한 곳을 지키고 돌보는 존재", "어떤 대상이나 장소를 지키고 보살피는 사람이나 존재"),
        _vocab_entry("탐험", "모르는 곳을 찾아가 살펴보는 일", "미지의 장소나 위험을 무릅쓰고 찾아가 살피는 일"),
        _vocab_entry("마법", "신기한 일을 일으키는 놀라운 힘", "초자연적인 힘으로 신기한 일을 일으키는 기술"),
    ],
    "모험": [
        _vocab_entry("용기", "두려움을 이겨 내는 씩씩한 마음", "어려움이나 두려움을 이겨 내는 씩씩한 마음"),
        _vocab_entry("지도", "길과 장소의 모습을 줄여 그린 그림", "지구 표면의 상태나 길을 일정한 비율로 줄여 그린 그림"),
        _vocab_entry("나침반", "방향을 알려 주는 바늘 도구", "바늘이 항상 북쪽을 가리켜 방향을 알려 주는 도구"),
        _vocab_entry("발자국", "발로 밟은 자리에 남은 흔적", "발로 밟은 자리에 남은 자국"),
        _vocab_entry("동굴", "바위나 땅속에 자연히 생긴 빈 공간", "자연적으로 생긴 땅속이나 바위 속의 빈 공간"),
    ],
    "자연": [
        _vocab_entry("새싹", "씨앗에서 처음 돋아나는 어린 잎", "씨앗에서 처음으로 돋아나는 어린 잎"),
        _vocab_entry("산들바람", "시원하고 부드럽게 부는 바람", "시원하고 부드럽게 부는 늦봄이나 초가을의 바람"),
        _vocab_entry("물방울", "동그랗게 맺힌 작은 물덩어리", "방울방울 맺히거나 떨어지는 작은 물의 덩어리"),
        _vocab_entry("초원", "풀이 넓게 자란 평평한 들판", "풀이 넓게 우거진 평평한 들판"),
    ],
    "우정": [
        _vocab_entry("약속", "앞으로 지킬 일을 미리 정한 말", "앞으로 어떻게 하기로 미리 정하여 맺는 말이나 글"),
        _vocab_entry("배려", "다른 사람의 마음을 생각해 돌봐 줌", "다른 사람의 처지나 기분을 생각하여 보살펴 줌"),
        _vocab_entry("마음", "생각하고 느끼는 우리 안의 정신", "사람이 생각하고 느끼고 바라는 정신적인 활동"),
        _vocab_entry("온기", "마음이나 몸에 전해지는 따뜻한 기운", "따뜻한 기운이나 느낌"),
    ],
}

DEFAULT_VOCAB = [
    _vocab_entry("반짝임", "작은 빛이 환하게 비치는 모양", "작은 빛이 자꾸 잠깐씩 환하게 비치는 모양"),
    _vocab_entry("희망", "앞일을 기대하며 바라는 마음", "앞일에 대하여 기대를 가지고 바라는 마음"),
]

HERO_NAME_MAP: Dict[str, str] = {
    "male_01": "민호",
    "male_02": "준",
    "male_03": "태산",
    "male_04": "도윤",
    "male_05": "보리",
    "male_06": "레이븐",
    "male_07": "이안",
    "male_08": "하늘",
    "female_01": "미나",
    "female_02": "하나",
    "female_03": "미란",
    "female_04": "루나",
    "female_05": "서연",
    "female_06": "아린",
    "female_07": "나라",
    "female_08": "솔",
}


class StoryStartRequest(BaseModel):
    genre: str = "판타지"
    age: str = "초등_저학년"
    prompt: str = "따뜻한 모험 동화"
    character_key: Optional[str] = None
    character_context: Optional[Dict[str, Any]] = None
    story_cast: Optional[List[Dict[str, Any]]] = None
    character_overrides: Optional[Dict[str, str]] = None
    include_image: bool = False


class StoryContinueRequest(BaseModel):
    story_id: str
    choice: str
    genre: str = "판타지"
    age: str = "초등_저학년"
    character_instruction: Optional[str] = None
    previous_scene_contract: Optional[Dict[str, Any]] = None
    character_key: Optional[str] = None
    character_context: Optional[Dict[str, Any]] = None
    story_cast: Optional[List[Dict[str, Any]]] = None
    character_overrides: Optional[Dict[str, str]] = None
    runtime_state: Optional[str] = None
    story_so_far: Optional[str] = None


class StoryPsychRequest(BaseModel):
    story_id: str = ""
    story_title: str = "동화"
    choices_made: List[str] = Field(default_factory=list)
    runtime_state: Optional[str] = None
    emotion_scoring_enabled: bool = False
    completed: bool = True


class StoryCharactersRequest(BaseModel):
    story_id: str = ""
    story_title: str = "동화"
    story_text: str = ""
    age: str = "초등_저학년"


class StoryCharacterChatRequest(BaseModel):
    story_id: str = ""
    story_title: str = "동화"
    story_text: str = ""
    age: str = "초등_저학년"
    user_name: str = "동화 탐험가"
    character: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    user_message: str = ""


def _get_hero_name(character_key: Optional[str], character_context: Optional[Dict[str, Any]]) -> str:
    if character_context and character_context.get("name"):
        return str(character_context["name"]).strip()
    return HERO_NAME_MAP.get(character_key or "male_01", "민호")


def _get_vocab_for(genre: str, count: int = 2, story_text: str = "") -> List[Dict[str, str]]:
    text = (story_text or "").strip()
    matched: List[Dict[str, str]] = []
    seen = set()
    if text:
        for entry in TEXT_MATCHED_VOCAB + VOCAB_DATABASE.get(genre, []):
            hard = entry.get("hard") or entry.get("word") or ""
            if hard and hard not in seen and hard in text:
                matched.append(dict(entry))
                seen.add(hard)
                if len(matched) >= count:
                    return matched[:count]
    for entry in VOCAB_DATABASE.get(genre, DEFAULT_VOCAB):
        hard = entry.get("hard") or entry.get("word") or ""
        if hard and hard not in seen:
            matched.append(dict(entry))
            seen.add(hard)
            if len(matched) >= count:
                break
    return matched[:count]


@router.get("/health")
async def handle_story_health():
    """Health check endpoint used by Flutter ApiService.checkHealth()."""
    return {"status": "ok"}


@router.post("/story/start")
async def handle_story_start(payload: StoryStartRequest):
    """Handle story opening generation matching the Flutter ApiService contract."""
    character_key = payload.character_key or "male_01"
    hero_name = _get_hero_name(character_key, payload.character_context)
    prompt_clean = payload.prompt.split("[CHARACTER LOCK]")[0].strip()
    if not prompt_clean:
        prompt_clean = "신비로운 숲에서 시작되는 마법 같은 모험"

    genre = payload.genre or "판타지"
    story_id = f"story_{int(time.time())}_{secrets.token_hex(4)}"

    story_text = (
        f"달빛이 창문을 조용히 두드리던 밤, {hero_name}(은)는 책상 위에서 이상한 소리를 들었습니다. "
        f"낡은 보물 상자 안에서 은은하고 푸른 빛이 새어 나오고 있었어요. "
        f"상자 뚜껑을 조심스레 열자, {prompt_clean}에 얽힌 비밀의 지도가 빛을 내뿜으며 천천히 펼쳐졌습니다. "
        f"지도 위에는 별 모양의 작은 나침반이 빙글빙글 돌고 있었습니다. "
        f"{hero_name}(은)는 가슴이 두근거리기 시작했습니다. "
        f"‘이 지도를 따라가면 어떤 놀라운 세상이 기다리고 있을까?’ "
        f"{hero_name}(은)는 두려움보다는 호기심과 용기를 가슴에 품고 첫 발걸음을 떼기로 다짐했습니다."
    )

    choices = [
        "두근거리는 기대를 품고 빛나는 지도를 따라 숲길로 간다.",
        "주변을 둘러보며 숨겨진 위험이나 함정이 없는지 살핀다.",
        "신나는 마음으로 마을 광장의 친구에게 기쁜 소식을 전한다.",
    ]

    vocab = _get_vocab_for(genre, 2, story_text=story_text)

    scene_contract = {
        "version": 1,
        "source": "generator",
        "character_key": character_key,
        "participants": [{"character_key": character_key, "role": "hero"}],
        "character_keys": [character_key],
        "participant_roles": {character_key: "hero"},
        "scene_goal": "explore map mystery",
        "action": "interaction",
        "target": "map",
        "required_props": ["map"],
        "participant_count": 1,
        "visual_anchor": "glowing map discovery",
        "background_direction": "toward_target",
        "dialogue": None,
        "validation_errors": [],
        "valid": True,
        "story_text_excerpt": story_text[:120],
    }

    return {
        "story_id": story_id,
        "chapter": 1,
        "story_text": story_text,
        "choices": choices,
        "choice_emotions": [],
        "story_emotion": None,
        "vocab": vocab,
        "characters": {"hero": f"{hero_name} - 용감하고 호기심 많은 주인공"},
        "scene_contract": scene_contract,
        "completed": False,
        "runtime_state": f"ch1_{character_key}_{genre}",
    }


def _is_quiet_reflection_choice(choice: str) -> bool:
    quiet_keywords = ("해독", "살핀다", "둘러보며", "생각", "기다린다", "관찰", "읽어")
    return any(keyword in choice for keyword in quiet_keywords)


@router.post("/story/continue")
async def handle_story_continue(payload: StoryContinueRequest):
    """Handle story continuation matching the Flutter ApiService contract."""
    character_key = payload.character_key or "male_01"
    hero_name = _get_hero_name(character_key, payload.character_context)
    choice = payload.choice.strip()
    genre = payload.genre or "판타지"

    current_chapter = 2
    state_match = re.match(r"^ch([1-9]\d*)_", payload.runtime_state or "")
    if state_match:
        current_chapter = max(2, min(5, int(state_match.group(1)) + 1))
    elif payload.story_so_far:
        scenes = [p for p in payload.story_so_far.split("\n\n") if len(p.strip()) > 30]
        current_chapter = max(2, min(5, len(scenes) + 1))

    is_final = current_chapter >= 4
    quiet_choice = _is_quiet_reflection_choice(choice)

    if is_final:
        new_text = (
            f"{hero_name}(은)는 마침내 모든 수수께끼를 풀고 별빛의 정원에 도착해 큰 기쁨과 감동을 느꼈습니다. "
            f"선택했던 길 끝에서 환하게 빛나는 보물을 발견한 {hero_name}(은)는 따뜻하고 행복한 미소를 지었습니다. "
            f"함께했던 모든 모험의 순간들이 마음속에 뿌듯한 지혜와 용기로 차곡차곡 남았습니다. "
            f"‘우리의 모험은 끝났지만, 마음속의 빛은 언제나 함께할 거야!’ "
            f"{hero_name}(은)는 감사하고 행복한 마음으로 집으로 돌아왔고, 모험은 아름답게 끝을 맺었습니다."
        )
        choices = []
        scene_goal = "celebrate peaceful ending in starlight garden"
        action = "idle"
        target = "starlight_garden"
        required_props = ["crystal_key"]
        visual_anchor = "starlight garden finale"
        background_direction = "stationary"
    elif current_chapter == 2:
        new_text = (
            f"숲길을 걸어가던 {hero_name}(은)는 신비로운 거대한 고목 나무와 맑은 수정 연못을 보고 깊이 감탄했습니다! "
            f"푸른 이끼가 별처럼 반짝이며 길을 비추어 주어 마음이 참 따뜻하고 기뻤어요. "
            f"연못 한가운데에는 아름다운 수정 열쇠가 떠오르고 있었고, 물가에는 숲의 정령들이 남긴 고대 문자가 빛나고 있었습니다. "
            f"‘정말 아름답고 신기한 연못이야!’ "
            f"{hero_name}(은)는 설레는 기대감과 기쁨을 가득 품고 다음 걸음을 준비했습니다."
        )
        choices = [
            "신기한 마음으로 바위의 고대 문자를 천천히 해독해 본다.",
            "두근거리는 기대를 품고 수정 열쇠를 향해 징검다리를 건넌다.",
            "신기해하며 작은 손거울로 빛나는 문자를 비춰 본다.",
        ]
        scene_goal = "ponder ancient runes beside crystal pond"
        action = "idle"
        target = "crystal"
        required_props = ["crystal_key"]
        visual_anchor = "crystal pond reflection"
        background_direction = "stationary"
    else:
        if quiet_choice:
            new_text = (
                f"차분히 마음을 가다듬은 {hero_name}(은)는 수정 연못가에 서서 흥미로운 마음으로 문자를 읽어 내려갔습니다. "
                f"조용히 숨을 고르자 물결에 비친 글자들이 마법처럼 또렷한 문장으로 이어져 정말 기뻤어요! "
                f"‘마음이 고요할 때 비로소 진실의 길이 열린다.’ "
                f"{hero_name}(은)는 연못가 제자리에서 기쁜 미소를 지으며 마지막 관문의 해답을 깨닫고 뿌듯해했습니다."
            )
            scene_goal = "quietly decipher runes at crystal pond"
            action = "idle"
            target = "crystal"
            required_props = ["crystal_key"]
            visual_anchor = "crystal pond reflection"
            background_direction = "stationary"
        else:
            new_text = (
                f"용기를 내어 나아간 {hero_name}(은)는 빛나는 수정 열쇠를 손에 쥐고 정말 기뻐했습니다! "
                f"열쇠에 손끝이 닿는 순간, 연못 위로 아름다운 무지갯빛 다리가 솟아오르며 별빛 정원의 문이 활짝 열렸어요! "
                f"맑은 종소리가 {hero_name}의 용기 있는 도전을 축하해 주어 마음이 뿌듯하고 행복했습니다. "
                f"‘드디어 마지막 관문이 열렸어, 정말 기대돼!’ "
                f"{hero_name}(은)는 설레는 마음으로 다리 너머를 바라보았습니다."
            )
            scene_goal = "cross rainbow bridge with crystal key"
            action = "journey"
            target = "rainbow_bridge"
            required_props = ["crystal_key"]
            visual_anchor = "rainbow bridge portal"
            background_direction = "forward"
        choices = [
            "감동과 기쁨으로 수정 열쇠를 들고 별빛 정원의 문을 연다.",
            "행복하고 설레는 마음으로 무지갯빛 다리를 건너 나아간다.",
            "두근거리는 기대를 안고 조심스럽게 정원 안으로 들어선다.",
        ]

    vocab = _get_vocab_for(genre, 2, story_text=new_text)

    scene_contract = {
        "version": 1,
        "source": "generator",
        "character_key": character_key,
        "participants": [{"character_key": character_key, "role": "hero"}],
        "character_keys": [character_key],
        "participant_roles": {character_key: "hero"},
        "scene_goal": scene_goal,
        "action": action,
        "target": target,
        "required_props": required_props,
        "participant_count": 1,
        "visual_anchor": visual_anchor,
        "background_direction": background_direction,
        "dialogue": None,
        "validation_errors": [],
        "valid": True,
        "story_text_excerpt": new_text[:120],
    }

    return {
        "story_id": payload.story_id,
        "chapter": current_chapter,
        "new_text": new_text,
        "choices": choices,
        "choice_emotions": [],
        "story_emotion": None,
        "vocab": vocab,
        "scene_contract": scene_contract,
        "completed": is_final,
        "runtime_state": f"ch{current_chapter}_{character_key}_{genre}",
    }


@router.post("/story/psych")
async def handle_story_psych(payload: StoryPsychRequest):
    """Analyze story choices and return a child-friendly conversation summary."""
    choices = [c.strip() for c in payload.choices_made if c and c.strip()]
    quiet_count = sum(1 for c in choices if _is_quiet_reflection_choice(c))
    social_count = sum(
        1 for c in choices if any(k in c for k in ("친구", "마을", "함께", "나누", "인사", "도움"))
    )

    if quiet_count > 0 and quiet_count >= len(choices) // 2:
        psych_type = "깊이 생각하는 지혜 탐험가"
        dominant_emotions = ["신중함", "호기심", "집중력"]
        description = (
            f"'{payload.story_title}' 이야기에서 서두르지 않고 주변의 단서와 문자를 차분히 살피는 선택을 했어요. "
            f"낯선 상황에서도 먼저 관찰하고 이해하려는 깊은 사고력과 침착한 마음이 돋보입니다."
        )
    elif social_count > 0:
        psych_type = "마음을 나누는 다정한 동행자"
        dominant_emotions = ["따뜻함", "배려", "용기"]
        description = (
            f"'{payload.story_title}' 모험 속에서 친구와 기쁨을 나누고 함께 길을 찾으려는 선택이 빛났어요. "
            f"주변과의 관계를 소중히 여기며 협력 속에서 용기를 얻는 따뜻한 시선이 느껴집니다."
        )
    else:
        psych_type = "씩씩한 별빛 개척자"
        dominant_emotions = ["용기", "설렘", "도전정신"]
        description = (
            f"'{payload.story_title}' 이야기에서 미지의 길을 두려워하지 않고 한 걸음씩 앞으로 나아가는 선택을 했어요. "
            f"새로운 세계를 향한 호기심과 목표를 끝까지 이루려는 주도적인 에너지가 잘 드러납니다."
        )

    choice_insights: List[str] = []
    for idx, choice in enumerate(choices, start=1):
        if _is_quiet_reflection_choice(choice):
            choice_insights.append(
                f"{idx}번째 선택(\"{choice}\"): 바로 움직이기보다 단서의 의미를 먼저 파악하려는 차분한 관찰력이 나타났어요."
            )
        elif any(k in choice for k in ("친구", "마을", "함께", "도움")):
            choice_insights.append(
                f"{idx}번째 선택(\"{choice}\"): 소중한 사람과 경험을 공유하고 힘을 모으려는 공감 태도가 돋보였어요."
            )
        else:
            choice_insights.append(
                f"{idx}번째 선택(\"{choice}\"): 두려움을 이겨내고 스스로 길을 열어가려는 씩씩한 실천력이 담겨 있어요."
            )

    if not choice_insights:
        choice_insights.append("이야기 시작부터 끝까지 주인공의 여정을 집중해서 함께 따라갔어요.")

    caregiver_prompts = [
        "이야기에서 가장 마음이 끌렸던 선택은 무엇이었는지, 왜 그 길을 골랐는지 물어봐 주세요.",
        "주인공이 낯선 장소에 도착했을 때 어떤 기분이었을지 함께 상상해 보세요.",
        "만약 다른 선택지를 골랐다면 이야기가 어떻게 달라졌을지 즐겁게 이야기 나누어 보세요.",
    ]

    return {
        "type": psych_type,
        "description": description,
        "dominant_emotions": dominant_emotions,
        "choice_insights": choice_insights,
        "caregiver_prompts": caregiver_prompts,
        "analysis_caution": "동화 속 선택을 바탕으로 한 대화용 해설이며 심리검사가 아닙니다.",
    }


def _detect_protagonist_name(story_text: str) -> str:
    for name in HERO_NAME_MAP.values():
        if re.search(rf"\b{re.escape(name)}(?:은|는|이|가|을|를|의|\(은\)는)?", story_text):
            return name
    return "민호"


@router.post("/story/characters")
async def handle_story_characters(payload: StoryCharactersRequest):
    """Discover story characters for CharacterChatPage."""
    hero_name = _detect_protagonist_name(payload.story_text or "")
    characters = [
        {
            "name": hero_name,
            "role": "동화 속 주인공",
            "personality": "호기심이 많고 용감하며 친구의 이야기에 귀를 기울여요.",
            "greeting": f"안녕! 나는 {hero_name}(이)야. 나와 함께 모험해 줘서 정말 고마워! 궁금한 게 있으면 편하게 물어봐.",
            "avatar_emoji": "🌟",
        },
        {
            "name": "별빛 정령 루미",
            "role": "수정 연못의 안내자",
            "personality": "신비롭고 다정하며 숲속의 오래된 비밀을 잘 알고 있어요.",
            "greeting": "반가워요, 작은 탐험가님! 수정 연못과 별빛 정원에서 느꼈던 이야기를 들려줄래요?",
            "avatar_emoji": "🧚",
        },
    ]
    return {"characters": characters}


@router.post("/story/character-chat")
async def handle_story_character_chat(payload: StoryCharacterChatRequest):
    """Generate an in-character reply for CharacterChatPage and LetterPage."""
    char_name = str((payload.character or {}).get("name") or "주인공").strip()
    user_name = (payload.user_name or "동화 탐험가").strip()
    user_message = (payload.user_message or "").strip()

    is_letter = "편지를 썼어" in user_message or any(
        str(m.get("content") or "").startswith("편지:") for m in (payload.messages or [])
    )

    if is_letter:
        cleaned_letter = re.sub(
            r"^나는 너에게 이런 편지를 썼어\. 따뜻하게 답장해 줘\.\s*",
            "",
            user_message,
        ).strip()
        excerpt = cleaned_letter[:60] + ("..." if len(cleaned_letter) > 60 else "")
        reply = (
            f"{user_name}에게,\n\n"
            f"정성껏 보내 준 편지를 읽으며 마음이 참 따뜻해졌어! "
            f"특히 \"{excerpt}\"라고 적어 준 부분에서 네 다정한 마음이 그대로 전해졌단다. "
            f"네가 용기 있게 선택해 준 덕분에 우리가 별빛 정원까지 무사히 도착할 수 있었어. "
            f"앞으로도 새로운 모험이 시작될 때마다 너와 함께했던 순간을 꼭 기억할게!\n\n"
            f"- 너의 동화 친구 {char_name} 보냄"
        )
    elif any(k in user_message for k in ("기억", "순간", "장면", "모험")):
        reply = (
            f"{user_name}, 나는 우리가 수정 연못가에서 빛나는 열쇠와 비밀 문자를 마주했던 순간이 가장 기억에 남아! "
            f"네가 신중하게 길을 골라 준 덕분에 두려움이 설렘으로 바뀌었거든. 너는 어떤 장면이 제일 좋았어?"
        )
    elif any(k in user_message for k in ("기분", "마음", "감정", "어땠")):
        reply = (
            f"처음 보물 상자에서 푸른 빛이 새어 나왔을 때는 가슴이 두근거리고 조금 긴장됐어. "
            f"하지만 {user_name}(이)가 곁에서 함께 걸어 준다고 생각하니까 든든하고 행복했단다!"
        )
    else:
        reply = (
            f"{user_name}, 그렇게 말해 줘서 정말 기뻐! "
            f"우리가 함께 지나온 숲속 오솔길과 별빛 정원의 반짝임은 언제까지나 우리 마음속에 남아 있을 거야. "
            f"다음에 또 어떤 신비한 곳을 함께 탐험하고 싶니?"
        )

    suggested_replies = [
        "모험에서 가장 기억나는 순간은 뭐야?",
        "수정 연못을 봤을 때 어떤 기분이었어?",
        "다음에 또 함께 모험을 떠나자!",
    ]
    return {
        "reply": reply,
        "suggested_replies": suggested_replies,
    }
