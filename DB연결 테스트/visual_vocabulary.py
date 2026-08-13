import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from motion_policy import is_solo_action_semantics


CLASSIFIER_VERSION = 9
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
    "place": {
        "수풀", "마을", "골목", "동굴", "정원", "마당", "들판",
        "과수원", "곳간", "기슭", "부락", "기숙사", "보육원",
        "가로수", "물바다",
    },
    "emotion": {
        "심정", "두려움", "기쁨", "걱정", "외로움", "용기",
        "반가움", "설움", "시름", "조바심", "감격", "감명", "노여움",
    },
    "object": {
        "통나무", "기와", "마개", "저울", "비늘", "회초리", "열쇠",
        "망원경", "잠수함", "꼬챙이", "절구", "호루라기", "광주리",
        "깔개", "꽃신", "나사", "녹음기", "뒤주", "목재", "발명품",
        "벽장", "물레방아", "포대기",
    },
    "environment_effect": {
        "회오리", "불덩이", "바람", "안개", "그림자", "달빛", "햇빛",
        "폭풍", "번개", "천둥", "파도", "불꽃", "발소리", "노을",
        "천둥소리", "북소리",
    },
}

ROLE_KEYWORDS["place"] += (
    "성", "항구", "설원", "광장", "도서관", "시계탑", "축제장", "산길",
    "오두막",
)
EXACT_ROLE_WORDS["place"].update(
    {"항구", "설원", "축제장", "시계탑", "산길", "오두막"}
)

BACKGROUND_HINTS = {
    "fantasy_castle": (
        "마법", "주문", "별", "달빛", "신비", "신통", "성", "요정",
    ),
    "adventure_ruins": (
        "산", "바위산", "유적", "길", "모험", "절벽", "폭포", "말타기",
        "탐험", "기슭",
    ),
    "nature_pond": (
        "숲", "수풀", "나무", "연못", "풀", "꽃", "물고기", "열매",
        "통나무", "나무토막", "이슬", "들판", "물길",
        "과수원", "울창", "무성", "뽀얗",
    ),
    "friendship_square": (
        "친구", "마을", "아랫마을", "윗마을", "건넛마을", "공원", "집",
        "기와집", "빈집", "한집", "웃음", "약속", "다정", "반기",
        "가로수", "부락", "곳간", "기숙사", "보육원",
    ),
    "mystery_library": (
        "단서", "열쇠", "도서관", "발소리", "그림자", "비밀", "수상",
        "책", "벽장", "녹음기",
    ),
    "fantasy_crystal_cave": (
        "crystal", "cave", "portal", "수정", "동굴", "차원문", "마법문",
    ),
    "adventure_harbor": (
        "harbor", "port", "ship", "lighthouse", "항구", "부두", "배", "등대",
        "물바다", "노을",
    ),
    "nature_snowfield": (
        "snow", "snowfield", "winter", "cabin", "눈", "설원", "겨울", "오두막",
    ),
    "friendship_festival": (
        "festival", "parade", "pavilion", "축제", "잔치", "행진", "정자", "무대",
    ),
    "mystery_clocktower": (
        "clocktower", "clock", "gear", "시계탑", "시계", "톱니바퀴", "비밀문",
    ),
}

ACTION_HINTS = {
    "casting-magic": ("마법", "주문", "요술", "되살리다"),
    "walking": (
        "걷다", "걸어", "걸었", "다가", "이동", "떠나", "길을 나서",
        "따라가", "거치다", "나돌다", "내가다", "닥치다", "등지다",
        "내려가다", "다가서다", "돌아서다", "뒷걸음치다",
    ),
    "running": (
        "달리다", "뛰다", "앞지르다", "뒤쫓다", "누비다",
        "질주하다", "전력질주하다", "서두르다", "뛰어가다", "뛰어다니다",
        "달려가다",
    ),
    "crawling": ("기어가다", "기어가", "엎드려 기어"),
    "climbing": ("기어오르다", "기어오르", "오르다", "올라가다"),
    "stopping": ("멈추다", "멈춰", "정지하다", "멈칫하다"),
    "turning": ("방향을 바꾸다", "돌아서다", "돌아섰다", "몸을 돌리다"),
    "sitting": ("앉다", "앉아", "앉았다"),
    "standing": ("일어서다", "일어나", "일어섰다"),
    "jumping": (
        "\uc810\ud504", "\ub6f0\uc5b4\uc624\ub974", "\ub6f0\uc5b4\ub118", "\ub3c4\uc57d", "\ud6cc\ucc0d", "\ub118\uc5b4\uac00",
        "뛰어내리다", "뛰어넘다", "솟구치다", "도약하다", "펄쩍뛰다",
    ),
    "fighting": (
        "싸우다", "공격하다", "겨루다", "사로잡다", "쥐어뜯다",
        "뒤흔들다", "후려치다", "내리치다", "겨누다", "맞붙다",
        "억누르다", "얽매이다", "패하다",
    ),
    "investigating": (
        "찾", "살피", "관찰", "단서", "발견", "조사", "귀담다",
        "눈치채다", "뒤적이다", "숨죽이다", "기웃거리다",
        "뒤돌아보다", "들추다", "꿰뚫다", "눈뜨다",
        "살펴보다", "둘러보다", "들여다보다", "바라보다", "응시하다",
        "탐색하다", "훑어보다", "찾아보다", "귀기울이다",
    ),
    "helping": (
        "돕", "구하", "구출", "돌보", "보살피", "받들다", "배웅하다",
        "어루만지다", "가누다",
    ),
    "interacting": (
        "떠내다", "채우다", "터놓다", "펴놓다", "돌려놓다", "돌리다",
        "오므리다", "들이밀다", "건네받다", "움켜쥐다", "내보이다",
        "받아먹다", "받아쓰다", "사고팔다", "들리다", "비틀다",
        "일구다", "지피다", "감기다", "거르다", "절이다", "졸이다",
        "다시다", "뒤섞다", "우리다",
    ),
    "talking": (
        "말하다", "이야기하다", "외치다", "비꼬다", "지저귀다",
        "부르짖다", "수군거리다", "웅성거리다", "투덜거리다",
        "칭얼거리다", "권하다", "기리다",
    ),
    "waving": (
        "인사", "반기", "손을 흔들", "손 흔들다", "환영", "손짓하다", "손을 들다",
        "손을 내젓다",
    ),
    "emoting": (
        "붉히다", "뉘우치다", "흐느끼다", "겁먹다", "깔깔거리다",
        "씩씩거리다", "씩씩하다", "헐떡거리다", "헐떡이다",
        "일그러지다", "허덕이다",
    ),
}

ACTION_SEMANTIC_DEFAULTS = {
    "casting-magic": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "magic",
        "interaction_kind": "cast",
        "subject_role": "caster",
        "partner_role": None,
    },
    "walking": {
        "motion_mode": "locomotion",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "journey",
        "interaction_kind": "travel",
        "subject_role": "traveler",
        "partner_role": None,
        "pace": "walk",
    },
    "running": {
        "motion_mode": "locomotion",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "journey",
        "interaction_kind": "travel_fast",
        "subject_role": "runner",
        "partner_role": None,
        "pace": "run",
    },
    "crawling": {
        "motion_mode": "locomotion",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "journey",
        "interaction_kind": "crawl",
        "subject_role": "crawler",
        "partner_role": None,
        "pace": "crawl",
        "body_focus": "full_body",
        "path_pattern": "low_forward",
    },
    "climbing": {
        "motion_mode": "locomotion",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "journey",
        "interaction_kind": "climb",
        "subject_role": "climber",
        "partner_role": None,
        "requires_target": True,
        "target_type": "surface_or_route",
        "pace": "climb",
        "body_focus": "full_body",
        "path_pattern": "upward",
    },
    "stopping": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "stop",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "full_body",
        "temporal_pattern": "state_change",
        "target_type": "self",
    },
    "turning": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "turn_in_place",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "full_body",
        "temporal_pattern": "single",
        "path_pattern": "turn",
        "target_type": "self",
    },
    "sitting": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "sit",
        "interaction_kind": "sit",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "full_body",
        "temporal_pattern": "state",
        "target_type": "self",
    },
    "standing": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "stand",
        "interaction_kind": "stand",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "full_body",
        "temporal_pattern": "state_change",
        "target_type": "self",
    },
    "jumping": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "jump",
        "interaction_kind": "leap",
        "subject_role": "jumper",
        "partner_role": None,
        "body_focus": "whole_body",
        "temporal_pattern": "single",
    },
    "fighting": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "battle",
        "interaction_kind": "targeted_strike",
        "subject_role": "fighter",
        "partner_role": None,
        "requires_target": True,
        "target_type": "person_or_object",
        "body_focus": "arms_and_torso",
        "temporal_pattern": "single",
    },
    "investigating": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "investigate",
        "interaction_kind": "inspect",
        "subject_role": "observer",
        "partner_role": None,
        "body_focus": "gaze_and_hands",
        "target_type": "object_or_scene",
    },
    "helping": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "rescue",
        "interaction_kind": "assist",
        "subject_role": "helper",
        "partner_role": None,
        "body_focus": "hands_and_torso",
        "target_type": "self_or_person",
    },
    "interacting": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "object_interaction",
        "subject_role": "actor",
        "partner_role": None,
        "requires_object": True,
        "object_role": "manipulated_object",
        "body_focus": "hands",
        "target_type": "object",
    },
    "talking": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "conversation",
        "interaction_kind": "speak",
        "subject_role": "speaker",
        "partner_role": None,
        "body_focus": "face_and_upper_body",
        "target_type": "listener_or_scene",
    },
    "waving": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "wave",
        "interaction_kind": "greet",
        "subject_role": "greeter",
        "partner_role": None,
        "body_focus": "arms_and_face",
        "temporal_pattern": "repeated",
        "target_type": "person_or_scene",
    },
    "emoting": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "conversation",
        "interaction_kind": "express_emotion",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "face_and_torso",
        "temporal_pattern": "state",
        "target_type": "self",
    },
}

VERB_SEMANTIC_OVERRIDES = {
    "가다듬다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "self_adjust",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "upper_body",
        "temporal_pattern": "single",
        "target_type": "self",
    },
    "가리다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "conceal",
        "subject_role": "actor",
        "partner_role": None,
        "requires_object": True,
        "object_role": "cover",
        "body_focus": "hands",
        "target_type": "object_or_view",
    },
    "가물다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "drought",
        "subject_role": "environment",
        "partner_role": None,
        "temporal_pattern": "state_change",
    },
    "감돌다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "ambient_orbit",
        "subject_role": "environment",
        "partner_role": None,
        "path_pattern": "circular",
        "temporal_pattern": "continuous",
    },
    "걷히다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "weather_clearing",
        "subject_role": "environment",
        "partner_role": None,
        "temporal_pattern": "state_change",
    },
    "꺼리다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "conversation",
        "interaction_kind": "avoidance",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "face_and_torso",
        "target_type": "self",
    },
    "널리다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "scattered_state",
        "subject_role": "environment",
        "partner_role": None,
        "temporal_pattern": "state",
    },
    "다그다": {
        "motion_mode": "locomotion",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "journey",
        "interaction_kind": "approach",
        "subject_role": "approacher",
        "partner_role": None,
        "path_pattern": "toward_target",
        "target_type": "person_or_object",
        "pace": "walk",
    },
    "다잡다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "self_control",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "hands_and_torso",
        "target_type": "self",
    },
    "달구다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "heat_object",
        "subject_role": "actor",
        "partner_role": None,
        "requires_object": True,
        "object_role": "heated_object",
        "body_focus": "hands",
        "target_type": "object",
    },
    "되살아나다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "magic",
        "interaction_kind": "revival",
        "subject_role": "revived_subject",
        "partner_role": None,
        "body_focus": "full_body",
        "temporal_pattern": "state_change",
        "target_type": "self",
    },
    "들끓다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "crowd_activity",
        "subject_role": "environment",
        "partner_role": None,
        "temporal_pattern": "continuous",
    },
    "머금다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "conversation",
        "interaction_kind": "hold_expression",
        "subject_role": "actor",
        "partner_role": None,
        "body_focus": "face",
        "target_type": "self",
    },
    "사로잡히다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "battle",
        "interaction_kind": "capture_passive",
        "subject_role": "target",
        "partner_role": "captor",
        "body_focus": "full_body",
        "target_type": "person",
    },
    "설치다": {
        "motion_mode": "locomotion",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "journey",
        "interaction_kind": "move_erratically",
        "subject_role": "mover",
        "partner_role": None,
        "path_pattern": "erratic",
        "temporal_pattern": "repeated",
        "pace": "run",
    },
    "어르다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "conversation",
        "interaction_kind": "soothe",
        "subject_role": "comforter",
        "partner_role": "recipient",
        "body_focus": "hands_and_face",
        "target_type": "person",
    },
    "잡아먹히다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "battle",
        "interaction_kind": "predator_attack_passive",
        "subject_role": "prey",
        "partner_role": "predator",
        "body_focus": "full_body",
        "target_type": "creature",
    },
    "킁킁거리다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "investigate",
        "interaction_kind": "sniff",
        "subject_role": "observer",
        "partner_role": None,
        "body_focus": "face",
        "temporal_pattern": "repeated",
        "target_type": "object_or_scene",
    },
    "휩싸다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "envelop",
        "subject_role": "environment",
        "partner_role": None,
        "path_pattern": "surround",
        "temporal_pattern": "state_change",
    },
    "헐벗다": {
        "motion_mode": "environmental",
        "participant_count": 0,
        "requires_partner": False,
        "animation_action": "idle",
        "interaction_kind": "barren_state",
        "subject_role": "environment",
        "partner_role": None,
        "temporal_pattern": "state",
    },
    "건네받다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "interaction",
        "interaction_kind": "handoff_receive",
        "subject_role": "receiver",
        "partner_role": "giver",
        "requires_object": True,
        "object_role": "transferred_item",
        "body_focus": "hands",
        "temporal_pattern": "single",
        "directionality": "partner_to_subject",
        "target_type": "person",
    },
    "사고팔다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "interaction",
        "interaction_kind": "trade",
        "subject_role": "buyer",
        "partner_role": "seller",
        "requires_object": True,
        "object_role": "goods",
        "body_focus": "hands",
        "temporal_pattern": "repeated",
        "directionality": "bidirectional",
        "target_type": "person",
    },
    "사로잡다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "battle",
        "interaction_kind": "capture",
        "subject_role": "captor",
        "partner_role": "target",
        "body_focus": "full_body",
        "temporal_pattern": "single",
        "directionality": "toward_partner",
        "target_type": "person_or_creature",
    },
    "맞붙다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "battle",
        "interaction_kind": "duel",
        "subject_role": "fighter",
        "partner_role": "opponent",
        "body_focus": "full_body",
        "temporal_pattern": "repeated",
        "directionality": "bidirectional",
        "target_type": "person_or_creature",
    },
    "어루만지다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "rescue",
        "interaction_kind": "comfort",
        "subject_role": "comforter",
        "partner_role": "recipient",
        "body_focus": "hands",
        "temporal_pattern": "repeated_gentle",
        "directionality": "toward_partner",
        "target_type": "person_or_creature",
    },
    "배웅하다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "conversation",
        "interaction_kind": "farewell",
        "subject_role": "greeter",
        "partner_role": "departing_person",
        "body_focus": "upper_body",
        "temporal_pattern": "repeated",
        "directionality": "toward_partner",
        "target_type": "person",
    },
    "비꼬다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "conversation",
        "interaction_kind": "taunt",
        "subject_role": "speaker",
        "partner_role": "listener",
        "body_focus": "face_and_upper_body",
        "temporal_pattern": "continuous",
        "directionality": "toward_partner",
        "target_type": "person",
    },
    "수군거리다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "conversation",
        "interaction_kind": "whisper",
        "subject_role": "speaker",
        "partner_role": "listener",
        "body_focus": "face_and_upper_body",
        "temporal_pattern": "continuous",
        "directionality": "toward_partner",
        "target_type": "person",
    },
    "권하다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "conversation",
        "interaction_kind": "offer",
        "subject_role": "speaker",
        "partner_role": "listener",
        "body_focus": "face_and_hands",
        "temporal_pattern": "single",
        "directionality": "toward_partner",
        "target_type": "person",
    },
    "뒤쫓다": {
        "motion_mode": "locomotion",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "journey",
        "interaction_kind": "chase",
        "subject_role": "pursuer",
        "partner_role": "target",
        "body_focus": "full_body",
        "path_pattern": "pursuit",
        "temporal_pattern": "continuous",
        "directionality": "toward_target",
        "target_type": "person_or_creature",
        "requires_target": True,
        "pace": "run",
    },
    "싸우다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "battle",
        "interaction_kind": "fight",
        "subject_role": "fighter",
        "partner_role": "opponent",
        "requires_target": True,
        "target_type": "person_or_creature",
        "body_focus": "full_body",
        "temporal_pattern": "repeated",
        "directionality": "bidirectional",
    },
    "겨누다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "battle",
        "interaction_kind": "aim",
        "subject_role": "attacker",
        "partner_role": None,
        "requires_object": True,
        "object_role": "weapon",
        "requires_target": True,
        "target_type": "person_or_object",
        "body_focus": "arms_and_gaze",
        "temporal_pattern": "held_pose",
        "directionality": "toward_target",
    },
    "내리치다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "battle",
        "interaction_kind": "downward_strike",
        "subject_role": "attacker",
        "partner_role": None,
        "requires_target": True,
        "target_type": "person_or_object",
        "body_focus": "arms_and_torso",
        "temporal_pattern": "single",
        "directionality": "downward",
    },
    "뒤흔들다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "shake_target",
        "subject_role": "actor",
        "partner_role": None,
        "requires_target": True,
        "target_type": "person_or_object",
        "body_focus": "arms",
        "temporal_pattern": "repeated",
        "directionality": "alternating",
    },
    "억누르다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "conversation",
        "interaction_kind": "suppress",
        "subject_role": "actor",
        "partner_role": None,
        "target_type": "self_or_person",
        "body_focus": "face_and_torso",
        "temporal_pattern": "held_pose",
    },
    "얽매이다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "battle",
        "interaction_kind": "bound_passive",
        "subject_role": "restrained_subject",
        "partner_role": None,
        "requires_object": True,
        "object_role": "restraint",
        "target_type": "self",
        "body_focus": "full_body",
        "temporal_pattern": "held_pose",
    },
    "패하다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "conversation",
        "interaction_kind": "defeated_state",
        "subject_role": "defeated_subject",
        "partner_role": None,
        "target_type": "self",
        "body_focus": "full_body",
        "temporal_pattern": "state",
    },
    "쥐어뜯다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "tear_or_clutch",
        "subject_role": "actor",
        "partner_role": None,
        "requires_target": True,
        "target_type": "self_or_object",
        "body_focus": "hands",
        "temporal_pattern": "repeated",
    },
    "후려치다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "battle",
        "interaction_kind": "swing_strike",
        "subject_role": "attacker",
        "partner_role": None,
        "requires_target": True,
        "target_type": "person_or_object",
        "body_focus": "arms_and_torso",
        "temporal_pattern": "single",
        "directionality": "across_target",
    },
    "받들다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "support_or_revere",
        "subject_role": "supporter",
        "partner_role": None,
        "target_type": "person_or_object",
        "body_focus": "hands_and_torso",
        "temporal_pattern": "held_pose",
    },
    "받아먹다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "interaction",
        "interaction_kind": "receive_food",
        "subject_role": "recipient",
        "partner_role": "giver",
        "requires_object": True,
        "object_role": "food",
        "target_type": "person",
        "body_focus": "hands_and_face",
        "temporal_pattern": "single",
        "directionality": "partner_to_subject",
    },
    "받아쓰다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "dictation_write",
        "subject_role": "writer",
        "partner_role": None,
        "requires_object": True,
        "object_role": "notebook_and_pencil",
        "target_type": "speech_source",
        "body_focus": "hands_and_gaze",
        "temporal_pattern": "repeated",
    },
    "채우다": {
        "motion_mode": "stationary",
        "participant_count": 1,
        "requires_partner": False,
        "animation_action": "interaction",
        "interaction_kind": "attach_item",
        "subject_role": "actor",
        "partner_role": None,
        "requires_object": True,
        "object_role": "wearable_or_restraint",
        "target_type": "self_or_person",
        "body_focus": "hands",
        "temporal_pattern": "single",
    },
    "웅성거리다": {
        "motion_mode": "stationary",
        "participant_count": 2,
        "requires_partner": True,
        "animation_action": "conversation",
        "interaction_kind": "group_murmur",
        "subject_role": "group_member",
        "partner_role": "group_members",
        "participant_scope": "group",
        "target_type": "group",
        "body_focus": "face_and_upper_body",
        "temporal_pattern": "continuous",
        "directionality": "group_inward",
    },
}

ACTION_SEMANTIC_PRIORITY = (
    "jumping",
    "crawling",
    "climbing",
    "running",
    "walking",
    "stopping",
    "turning",
    "sitting",
    "standing",
    "fighting",
    "helping",
    "interacting",
    "investigating",
    "talking",
    "waving",
    "emoting",
    "casting-magic",
)

EMOTION_HINTS = {
    "joyful": (
        "기쁘", "즐겁", "행복", "웃", "신나", "깔깔거리다", "반가움",
        "감격", "감명", "까르르",
    ),
    "happy": (
        "웃다", "기뻐하다", "깔깔거리다", "방긋", "빙그레", "거뜬하다",
    ),
    "sad": (
        "울다", "흐느끼다", "칭얼거리다", "뉘우치다", "여의다", "설움",
        "시름", "슬피", "흑흑", "가엽다", "애처롭다", "딱하다",
    ),
    "angry": (
        "화내다", "씩씩거리다", "씩씩하다", "붉히다", "부르짖다",
        "투덜거리다", "노여움", "호통", "고래고래", "못마땅하다",
        "언짢다", "심술궂다",
    ),
    "afraid": (
        "두렵", "무섭", "겁", "걱정", "겁먹다", "숨죽이다", "허덕이다",
        "헐떡이다", "헐떡거리다", "조바심", "철렁", "화들짝",
    ),
    "curious": (
        "궁금", "호기심", "신기", "살피", "기웃거리다", "눈치채다",
    ),
    "caring": (
        "다정", "돕", "돌보", "보살피", "어루만지다", "받들다",
        "배웅하다", "어질다", "온화하다", "훈훈하다",
    ),
    "determined": ("굳세다", "기운차다", "거침없다", "모질다"),
}

EFFECT_HINTS = {
    "whirlwind": ("회오리", "소용돌이"),
    "strong_wind": (
        "거센 바람", "강풍", "휩쓸", "휘몰다", "휘몰아치다", "펄럭이다",
    ),
    "glowing_light": (
        "빛", "빛깔", "얼굴빛", "보랏빛", "푸른빛", "반짝", "환히",
        "달빛", "햇빛", "어리다", "깃들다", "차오르다",
    ),
    "mist": ("안개", "서리", "서리다", "스미다", "스며들다"),
    "fire": ("불꽃", "불덩이", "모닥불", "지피다", "달구다", "이글거리다", "달아오르다"),
    "revival": ("되살아나다",),
    "motion_blur": ("앞지르다", "뒤쫓다", "누비다"),
    "sound": (
        "울리다", "지저귀다", "웅성거리다", "북소리", "천둥소리", "둥둥",
    ),
    "sunset_glow": ("노을",),
    "flooded_ground": ("물바다",),
    "pale_mist": ("뽀얗다",),
    "murky_atmosphere": ("탁하다",),
    "soft_warmth": ("온화하다", "훈훈하다"),
    "thunder_flash": ("천둥소리",),
    "splash": ("풍덩",),
}

PROP_HINTS = {
    "wooden_skewer": ("꼬챙이",),
    "stacked_pile": ("더미",),
    "stone_mortar": ("절구",),
    "whistle": ("호루라기",),
    "woven_basket": ("광주리",),
    "floor_mat": ("깔개",),
    "flower_shoes": ("꽃신",),
    "metal_screw": ("나사",),
    "sound_recorder": ("녹음기",),
    "wooden_grain_chest": ("뒤주",),
    "timber": ("목재",),
    "invented_device": ("발명품",),
    "wall_cabinet": ("벽장",),
    "waterwheel": ("물레방아",),
    "baby_wrap": ("포대기",),
    "chestnut": ("알밤",),
    "walnut": ("호두",),
}

MOTION_MODIFIER_HINTS = {
    "slow_subtle": ("슬며시",),
    "sudden": ("뜻밖에", "와락", "언뜻", "별안간", "갑작스럽다"),
    "fast_agile": ("날쌔다", "거침없다", "기운차다"),
    "continuous": ("끊임없다",),
    "trembling": ("부르르",),
    "rolling": ("둘둘", "똘똘", "데굴데굴"),
    "splashing": ("풍덩",),
    "smiling": ("방긋", "빙그레", "까르르"),
    "crying": ("슬피", "흑흑"),
    "thinking": ("골똘히", "곰곰", "명상", "궁리"),
    "exhausted": ("헉헉", "가쁘다", "녹초"),
    "startled": ("화들짝", "철렁", "뜨끔하다"),
}

MATCH_TERM_OVERRIDES = {
    "걷다": ["걸어", "걸었", "걸으", "걸음"],
    "돕다": ["돕", "도와", "도우"],
    "듣다": ["들어", "들었"],
    "묻다": ["물어", "물었"],
    "붓다": ["부어", "부었"],
    "앞지르다": ["앞지르", "앞질러", "앞질렀", "앞질"],
    "기어오르다": ["기어오르", "기어올라", "기어올랐", "기어올"],
    "기어가다": ["기어가", "기어갔", "기어가며"],
    "오르다": ["오르", "올라", "올랐", "오르는"],
    "내려가다": ["내려가", "내려갔", "내려가며"],
    "질주하다": ["질주하", "질주했", "질주하며"],
    "서두르다": ["서두르", "서둘러", "서둘렀"],
    "뛰어내리다": ["뛰어내리", "뛰어내려", "뛰어내렸"],
    "뛰어넘다": ["뛰어넘", "뛰어넘어", "뛰어넘었"],
    "솟구치다": ["솟구치", "솟구쳐", "솟구쳤"],
    "살펴보다": ["살펴보", "살펴봐", "살펴봤"],
    "둘러보다": ["둘러보", "둘러봐", "둘러봤"],
    "들여다보다": ["들여다보", "들여다봐", "들여다봤"],
    "응시하다": ["응시하", "응시했", "응시하며"],
    "탐색하다": ["탐색하", "탐색했", "탐색하며"],
    "손짓하다": ["손짓하", "손짓했", "손짓하며"],
    "뒤돌아보다": ["뒤돌아보", "뒤돌아봐", "뒤돌아봤", "뒤돌아"],
    "눈치채다": ["눈치채", "눈치챘", "눈치"],
    "숨죽이다": ["숨죽이", "숨죽여", "숨죽였", "숨죽"],
    "들추다": ["들추", "들춰", "들췄"],
    "내보이다": ["내보이", "내보여", "내보였", "내보"],
    "일구다": ["일구", "일궈", "일궜"],
    "지피다": ["지피", "지펴", "지폈"],
    "가리다": ["가리", "가려", "가렸"],
    "걷히다": ["걷히", "걷혀", "걷혔", "걷힌"],
    "꺼리다": ["꺼리", "꺼려", "꺼렸"],
    "널리다": ["널리", "널려", "널렸"],
    "달구다": ["달구", "달궈", "달궜"],
    "사로잡히다": ["사로잡히", "사로잡혀", "사로잡혔"],
    "설치다": ["설치", "설쳐", "설쳤"],
    "어르다": ["어르", "얼러", "얼렀"],
    "잡아먹히다": ["잡아먹히", "잡아먹혀", "잡아먹혔"],
    "겨누다": ["겨누", "겨눠", "겨눴"],
    "내리치다": ["내리치", "내리쳐", "내리쳤"],
    "억누르다": ["억누르", "억눌러", "억눌렀"],
    "얽매이다": ["얽매이", "얽매여", "얽매였"],
    "후려치다": ["후려치", "후려쳐", "후려쳤"],
    "받아쓰다": ["받아쓰", "받아써", "받아썼"],
    "채우다": ["채우", "채워", "채웠"],
    "멈추다": ["멈추", "멈춰", "멈췄", "멈칫"],
    "방향을 바꾸다": ["방향을 바꾸", "방향을 바꿔", "방향을 바꿨"],
    "앉다": ["앉아", "앉았", "앉으"],
    "일어서다": ["일어서", "일어섰", "일어나"],
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


def _complete_action_semantics(values: Dict[str, Any]) -> Dict[str, Any]:
    semantics = dict(values)
    motion_mode = str(semantics.get("motion_mode") or "stationary")
    mode_defaults = {
        "locomotion": {
            "body_focus": "full_body",
            "path_pattern": "forward",
            "temporal_pattern": "continuous",
            "directionality": "toward_route",
            "target_type": "route",
        },
        "stationary": {
            "body_focus": "upper_body",
            "path_pattern": "none",
            "temporal_pattern": "single",
            "directionality": "self_or_target",
            "target_type": "self_or_scene",
        },
        "environmental": {
            "body_focus": "scene",
            "path_pattern": "none",
            "temporal_pattern": "state_change",
            "directionality": "scene_wide",
            "target_type": "environment",
        },
    }
    completed = {
        "requires_object": False,
        "object_role": None,
        "requires_target": False,
        **mode_defaults.get(motion_mode, mode_defaults["stationary"]),
        **semantics,
    }
    if completed.get("requires_partner"):
        completed["participant_count"] = max(
            2,
            int(completed.get("participant_count") or 2),
        )
    completed.setdefault(
        "participant_scope",
        (
            "environment"
            if completed.get("participant_count") == 0
            else "pair"
            if completed.get("requires_partner")
            else "solo"
        ),
    )
    return completed


def _resolve_action_semantics(
    word: str,
    action_tags: Iterable[str],
    effect_tags: Iterable[str],
    pos: str,
) -> Dict[str, Any]:
    override = VERB_SEMANTIC_OVERRIDES.get(word)
    if override:
        return _complete_action_semantics(override)

    normalized_tags = set(action_tags)
    for tag in ACTION_SEMANTIC_PRIORITY:
        if tag in normalized_tags:
            return _complete_action_semantics(ACTION_SEMANTIC_DEFAULTS[tag])

    if pos == "verb" and list(effect_tags):
        return _complete_action_semantics({
            "motion_mode": "environmental",
            "participant_count": 0,
            "requires_partner": False,
            "animation_action": "idle",
            "interaction_kind": "environment_change",
            "subject_role": "environment",
            "partner_role": None,
        })
    return {}


def classify_fit_vocabulary(document: Dict[str, Any]) -> Dict[str, Any]:
    word = normalize_text(document.get("word") or document.get("original_word"))
    meaning = normalize_text(
        document.get("child_friendly_meaning") or document.get("meaning")
    )
    combined = f"{word} {meaning}".strip()
    pos = _normalize_pos(document)
    background_keys = _hint_values(word, BACKGROUND_HINTS)
    action_tags = _hint_values(word, ACTION_HINTS)
    emotion_tags = _hint_values(word, EMOTION_HINTS)
    effect_tags = _hint_values(word, EFFECT_HINTS)
    prop_tags = _hint_values(word, PROP_HINTS)
    motion_modifier_tags = _hint_values(word, MOTION_MODIFIER_HINTS)
    action_semantics = _resolve_action_semantics(
        word,
        action_tags,
        effect_tags,
        pos,
    )

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

    if action_tags and pos == "verb":
        scores["action"] += 7
        evidence["action"].extend(
            f"action_tag:{tag}" for tag in action_tags
        )
    if action_semantics:
        semantic_role = (
            "environment_effect"
            if action_semantics.get("motion_mode") == "environmental"
            else "action"
        )
        scores[semantic_role] += 8
        evidence[semantic_role].append(
            f"semantic_kind:{action_semantics.get('interaction_kind')}"
        )
    if background_keys:
        scores["place"] += 6
        evidence["place"].extend(
            f"background_key:{key}" for key in background_keys
        )
    if emotion_tags:
        scores["emotion"] += 6
        evidence["emotion"].extend(
            f"emotion_tag:{tag}" for tag in emotion_tags
        )
    if effect_tags:
        scores["environment_effect"] += 6
        evidence["environment_effect"].extend(
            f"effect_tag:{tag}" for tag in effect_tags
        )
    if prop_tags:
        scores["object"] += 7
        evidence["object"].extend(f"prop_tag:{tag}" for tag in prop_tags)
    if motion_modifier_tags:
        scores["action"] += 5
        evidence["action"].extend(
            f"motion_modifier:{tag}" for tag in motion_modifier_tags
        )

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
    if not selected_roles or (
        not action_semantics and non_visual_score >= highest_score
    ):
        primary_role = "non_visual"
        selected_roles = []
    else:
        primary_role = ranked[0][0]

    match_terms = [word] if len(word) >= 2 else []
    if pos in {"verb", "adjective"} and word.endswith("다") and len(word) >= 3:
        match_terms.append(word[:-1])
    if pos == "verb" and word.endswith("하다") and len(word) >= 4:
        match_terms.append(word[:-2])
    if pos == "verb" and word.endswith("거리다") and len(word) >= 5:
        match_terms.append(word[:-2])
    match_terms.extend(MATCH_TERM_OVERRIDES.get(word, []))
    exact_visual_word = any(
        word in role_words for role_words in EXACT_ROLE_WORDS.values()
    )
    usable_for_image = primary_role != "non_visual" and bool(
        exact_visual_word
        or background_keys
        or action_tags
        or action_semantics
        or emotion_tags
        or effect_tags
        or prop_tags
        or motion_modifier_tags
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
        "action_semantics": action_semantics,
        "solo_action": is_solo_action_semantics(action_semantics),
        "emotion_tags": emotion_tags,
        "effect_tags": effect_tags,
        "prop_tags": prop_tags,
        "motion_modifier_tags": motion_modifier_tags,
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
                "action_semantics": document.get("action_semantics", {}),
                "solo_action": bool(document.get("solo_action", False)),
                "emotion_tags": document.get("emotion_tags", []),
                "effect_tags": document.get("effect_tags", []),
                "prop_tags": document.get("prop_tags", []),
                "motion_modifier_tags": document.get(
                    "motion_modifier_tags", []
                ),
                "ensemble_profile": document.get("ensemble_profile"),
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

    semantic_match = next(
        (
            match
            for match in matches
            if match.get("primary_role") == "action"
            and match.get("action_semantics")
        ),
        None,
    ) or next(
        (match for match in matches if match.get("action_semantics")),
        None,
    )
    action_semantics = dict((semantic_match or {}).get("action_semantics") or {})
    if action_semantics and semantic_match:
        action_semantics["source_word"] = semantic_match.get("word")

    solo_action_matches = [
        match for match in matches if bool(match.get("solo_action"))
    ]
    ensemble_match = semantic_match or next(
        (match for match in matches if match.get("ensemble_profile")),
        None,
    )
    ensemble_profile = dict(
        (ensemble_match or {}).get("ensemble_profile") or {}
    )

    return {
        "matched_words": [match["word"] for match in matches],
        "matches": matches,
        "background_keys": collect("background_keys"),
        "action_tags": collect("action_tags"),
        "action_semantics": action_semantics,
        "solo_action": bool((semantic_match or {}).get("solo_action")),
        "solo_action_words": [match["word"] for match in solo_action_matches],
        "emotion_tags": collect("emotion_tags"),
        "effect_tags": collect("effect_tags"),
        "prop_tags": collect("prop_tags"),
        "motion_modifier_tags": collect("motion_modifier_tags"),
        "ensemble_profile": ensemble_profile,
        "match_score": round(
            sum(1.0 + min(match["fit_score"], 100.0) / 100.0 for match in matches),
            3,
        ),
    }
