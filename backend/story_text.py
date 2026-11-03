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
