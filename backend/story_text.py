"""Gemini가 만든 동화 본문 정리: 마크다운 기호 제거 + 맨 앞 제목 줄 빼기."""
import re

_SENTENCE_END = tuple(".!?…~。,，\"'”’」』)")
_TITLE_PREFIX = re.compile(r"^\s*(제목|title)\s*[:：]", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*")
_BULLET = re.compile(r"^\s*[*\-+•]\s+")
_RULE = re.compile(r"^\s*([*\-_=]\s*){3,}$")
_FULL_BOLD = re.compile(r"^\s*(\*\*|__)(.+?)\1\s*$")


def _strip_inline(line: str) -> str:
    line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line)          # **굵게**, __굵게__
    line = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", line)  # *기울임*
    line = re.sub(r"`([^`]*)`", r"\1", line)                  # `코드`
    return line.replace("**", "").replace("__", "")


def _looks_like_title(raw: str, cleaned: str, has_more: bool, blank_after: bool) -> bool:
    if not cleaned or not has_more:
        return False
    if _HEADING.match(raw) or _FULL_BOLD.match(raw) or _TITLE_PREFIX.match(cleaned):
        return True
    # 기호 없는 제목: 짧고, 문장처럼 끝나지 않고, 바로 뒤가 빈 줄 (예: "용감한 꼬마 마법사의 모험")
    return blank_after and len(cleaned) <= 30 and not cleaned.endswith(_SENTENCE_END)


def clean_story_text(text: str) -> str:
    raw_lines = (text or "").replace("\r\n", "\n").split("\n")
    lines: list[tuple[str, str]] = []  # (원래 줄, 정리한 줄)
    for raw in raw_lines:
        if _RULE.match(raw):
            lines.append((raw, ""))
            continue
        cleaned = _BULLET.sub("", _HEADING.sub("", raw))
        lines.append((raw, _strip_inline(cleaned).strip()))

    # 맨 앞의 빈 줄은 건너뛰고, 첫 줄이 제목처럼 보이면 뺍니다.
    while lines and not lines[0][1]:
        lines.pop(0)
    if lines:
        raw, cleaned = lines[0]
        has_more = any(c for _, c in lines[1:])
        blank_after = len(lines) > 1 and not lines[1][1]
        if _looks_like_title(raw, cleaned, has_more, blank_after):
            lines.pop(0)

    out = "\n".join(c for _, c in lines).strip()
    return re.sub(r"\n{3,}", "\n\n", out)  # 빈 줄은 최대 한 줄


# ----------------------------------------
# 조사 앞 띄어쓰기 고치기 (Colab 모델이 "토끼 는", "뿔 을"처럼 조사를 떼어 쓰는 경우)
# ----------------------------------------
# 보수적으로: 아래 조건을 모두 만족할 때만 앞 낱말에 붙입니다. 애매하면 그대로 둠.
#   1) 조사 바로 뒤가 공백·문장부호·줄 끝 (= 조사가 낱말 하나로 떨어져 있음. "이 책", "가방"은 안 건드림)
#   2) 앞 낱말이 한글로 끝나고, 앞 낱말 끝 글자가 어미·조사로 자주 끝나는 글자가 아님 ("토끼가 이 책" / "집에 가 보자" 보호)
#   3) 앞 낱말이 부사·관형사 목록에 없음 ("정말 도 와 줘" 보호)
#   4) 받침과 조사가 맞음 (은/이/을/과/으로/이랑은 받침 뒤, 는/가/를/와/로/랑은 받침 없는 글자 뒤, 로는 ㄹ받침 뒤도)
PARTICLES = ["에서", "에게", "으로", "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "로", "랑", "만"]
_PARTICLE_SPACE = re.compile(
    r"([가-힣]+)[ \t]+(" + "|".join(PARTICLES) + r")(?=[\s.,!?~…\"'“”‘’)\]」』]|$)"
)
# 이 글자로 끝나는 낱말 뒤에는 붙이지 않음 (어미·조사로 끝난 낱말일 가능성이 큼)
_NO_JOIN_LAST = set("요다고서며면게지니까데죠네는은이가을를에의도로만랑한던된할될갈올운인해했")
_NO_JOIN_WORDS = {
    "정말", "아주", "너무", "매우", "다시", "같이", "함께", "모두", "조금", "많이", "빨리", "천천히", "계속",
    "바로", "먼저", "항상", "그냥", "아직", "이미", "벌써", "자꾸", "꼭", "또", "잘", "못", "안", "더", "좀",
    "그", "저", "이", "새", "헌", "온", "몇", "각", "어느", "무슨", "어떤", "그런", "이런", "저런",
}
_NEEDS_JONG = {"은", "이", "을", "과", "으로"}
_NEEDS_NO_JONG = {"는", "가", "를", "와", "랑"}
_JONG_RIEUL = 8  # ㄹ 받침 번호


def _jong(syllable: str) -> int:
    """받침 번호 (0 = 받침 없음)"""
    return (ord(syllable) - 0xAC00) % 28


def _particle_fits(word: str, particle: str) -> bool:
    jong = _jong(word[-1])
    if particle in _NEEDS_JONG:
        return jong != 0 and not (particle == "으로" and jong == _JONG_RIEUL)
    if particle in _NEEDS_NO_JONG:
        return jong == 0
    if particle == "로":
        return jong == 0 or jong == _JONG_RIEUL
    return True  # 에, 에서, 에게, 의, 도, 만: 받침 상관없음


def fix_particle_spacing(text: str) -> str:
    def join(m: re.Match) -> str:
        word, particle = m.group(1), m.group(2)
        if word in _NO_JOIN_WORDS or word[-1] in _NO_JOIN_LAST or not _particle_fits(word, particle):
            return m.group(0)
        return word + particle

    # 한 번 붙이면 다음 낱말과의 경계가 바뀌므로 바뀌지 않을 때까지 (보통 1~2번)
    for _ in range(3):
        fixed = _PARTICLE_SPACE.sub(join, text)
        if fixed == text:
            break
        text = fixed
    return text
