"""
동화 줄거리 생성 데이터 전처리 스크립트
----------------------------------------------
3가지 데이터 타입을 모두 처리하여 학습용 Instruction-Following 포맷으로 변환합니다.

출력: data/train.jsonl, data/val.jsonl, data/stats.json
"""

import json
import os
import re
import random
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────
# 경로 설정
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent / "015.동화 줄거리 생성 데이터/3.개방데이터/1.데이터"
OUT_DIR  = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)

SUBLABEL_DIR  = BASE_DIR / "Sublabel/SbL"
TRAIN_SRC_DIR = BASE_DIR / "Training/01.원천데이터"
TRAIN_LBL_DIR = BASE_DIR / "Training/02.라벨링데이터"
VAL_SRC_DIR   = BASE_DIR / "Validation/01.원천데이터"
VAL_LBL_DIR   = BASE_DIR / "Validation/02.라벨링데이터"

# ─────────────────────────────────────────────
# 분류 코드 → 한글 매핑
# ─────────────────────────────────────────────
THEME_MAP = {
    "01T": "의사소통",
    "02T": "자연탐구",
    "03T": "사회관계",
    "04T": "예술경험",
    "05T": "신체운동_건강",
}
AGE_MAP = {
    "01S": "유아",
    "02S": "초등_저학년",
    "03S": "초등_고학년",
}

# ─────────────────────────────────────────────
# 선택지 템플릿 (데이터 augmentation용)
# ─────────────────────────────────────────────
CHOICE_TEMPLATES = [
    ["주인공이 용기를 내어 앞으로 나아간다", "친구에게 도움을 요청한다", "잠깐 멈추고 생각한다"],
    ["마법을 사용해 문제를 해결한다", "다른 방법을 찾아본다", "어른에게 이야기한다"],
    ["함께 협력해서 해결한다", "혼자서 해결하려 한다", "포기하고 돌아간다"],
]

def load_json(path: Path) -> Optional[dict]:
    """UTF-8 BOM 처리 포함 JSON 로더"""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [경고] 로드 실패: {path.name} — {e}")
        return None

def extract_theme_age_from_path(path: Path) -> tuple[str, str]:
    """파일명 또는 경로에서 주제/연령 추출"""
    parts = str(path).replace("\\", "/").split("/")
    theme, age = "일반", "전체"
    for part in parts:
        for k, v in THEME_MAP.items():
            if k in part:
                theme = v
        for k, v in AGE_MAP.items():
            if k in part:
                age = v
    return theme, age

def clean_text(text: str) -> str:
    """불필요한 공백, 줄바꿈 정리"""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    text = re.sub(r" {2,}", " ", text)
    return text

# ═══════════════════════════════════════════════
# 타입 1: Sublabel 텍스트 → 스토리 생성 샘플
# ═══════════════════════════════════════════════
def process_sublabel(path: Path) -> list[dict]:
    """
    raw text → 스토리 생성 + 선택지 생성 2가지 샘플 생성
    """
    samples = []
    data = load_json(path)
    if not data or "text" not in data:
        return samples

    theme, age = extract_theme_age_from_path(path)
    full_text  = clean_text(data["text"])
    if len(full_text) < 100:
        return samples

    # 문단으로 분리
    paragraphs = [p.strip() for p in full_text.split("\n\n") if len(p.strip()) > 30]
    if len(paragraphs) < 2:
        paragraphs = [p.strip() for p in full_text.split("\n") if len(p.strip()) > 30]
    if len(paragraphs) < 2:
        return samples

    intro      = "\n".join(paragraphs[:2])   # 도입부 2단락
    body       = "\n".join(paragraphs[2:4])  # 전개 2단락
    total_len  = len(paragraphs)

    # ── 샘플 A: 스토리 도입부 생성 ──
    samples.append({
        "type": "story_generation",
        "instruction": (
            f"장르: {theme}, 대상 연령: {age}\n"
            f"다음 힌트를 바탕으로 어린이 동화의 도입부를 써주세요."
        ),
        "input": f"[힌트] 주제: {theme}, 연령: {age}",
        "output": intro,
        "metadata": {
            "theme": theme, "age": age,
            "source": "sublabel", "total_paragraphs": total_len,
        }
    })

    # ── 샘플 B: 선택지 생성 (도입부 이후) ──
    if len(paragraphs) >= 3:
        choice_set = random.choice(CHOICE_TEMPLATES)
        samples.append({
            "type": "choice_generation",
            "instruction": (
                "다음 동화 내용을 읽고, 주인공이 선택할 수 있는 자연스러운 다음 행동 3가지를 제시하세요.\n"
                "각 선택지는 아이가 이해하기 쉬운 짧은 문장으로 작성해주세요."
            ),
            "input": intro,
            "output": "\n".join([f"{i+1}. {c}" for i, c in enumerate(choice_set)]),
            "metadata": {
                "theme": theme, "age": age, "source": "sublabel_choice",
            }
        })

    # ── 샘플 C: 이야기 이어쓰기 ──
    if body:
        samples.append({
            "type": "story_continuation",
            "instruction": (
                "다음은 어린이 동화의 앞부분입니다. 이야기를 자연스럽게 이어서 써주세요."
            ),
            "input": intro,
            "output": body,
            "metadata": {
                "theme": theme, "age": age, "source": "sublabel_cont",
            }
        })

    return samples


# ═══════════════════════════════════════════════
# 타입 2: 원천데이터(TS/VS) → 메타+줄거리 샘플
# ═══════════════════════════════════════════════
def process_source(path: Path) -> list[dict]:
    """
    원천 데이터: 제목/작가/분류 + 문단 텍스트 → 줄거리 재구성
    """
    samples = []
    data = load_json(path)
    if not data or "paragraphInfo" not in data:
        return samples

    title     = data.get("title", "")
    author    = data.get("author", "")
    theme     = data.get("classification", "")
    age       = data.get("readAge", "")
    para_list = data.get("paragraphInfo", [])

    if not para_list:
        return samples

    # 전체 본문 합치기
    full_story = "\n\n".join(
        p.get("srcText", "") for p in para_list if p.get("srcText")
    )
    full_story = clean_text(full_story)

    if len(full_story) < 100:
        return samples

    # 도입 (앞 30%), 전개 (30~70%), 결말 (70%~)
    split = len(para_list)
    intro_end = max(1, split // 3)
    body_end  = max(2, split * 2 // 3)

    intro = clean_text("\n\n".join(
        p.get("srcText", "") for p in para_list[:intro_end] if p.get("srcText")
    ))
    body  = clean_text("\n\n".join(
        p.get("srcText", "") for p in para_list[intro_end:body_end] if p.get("srcText")
    ))

    # ── 샘플 A: 제목+메타 → 스토리 생성 ──
    samples.append({
        "type": "story_from_title",
        "instruction": (
            f"제목: 『{title}』 (작가: {author})\n"
            f"장르: {theme}, 대상 연령: {age}\n"
            f"위 동화의 첫 부분을 어린이가 이해하기 쉽게 써주세요."
        ),
        "input": "",
        "output": intro,
        "metadata": {
            "title": title, "author": author,
            "theme": theme, "age": age, "source": "source_data",
        }
    })

    # ── 샘플 B: 도입 → 이어쓰기 ──
    if body:
        samples.append({
            "type": "story_continuation",
            "instruction": "다음 동화의 앞부분을 읽고 이야기를 이어서 써주세요.",
            "input": intro,
            "output": body,
            "metadata": {
                "title": title, "theme": theme, "age": age, "source": "source_cont",
            }
        })

    return samples


# ═══════════════════════════════════════════════
# 타입 3: 라벨링데이터(TL/VL) → 구조화 샘플 (핵심!)
# ═══════════════════════════════════════════════
def process_labeled(path: Path) -> list[dict]:
    """
    라벨링 데이터: character/setting/feeling + plotSummaryText 활용
    → 가장 풍부한 학습 샘플 생성
    """
    samples = []
    data = load_json(path)
    if not data or "paragraphInfo" not in data:
        return samples

    title     = data.get("title", "")
    author    = data.get("author", "")
    para_list = data.get("paragraphInfo", [])

    labeled_paras = [
        p for p in para_list
        if isinstance(p.get("plotSummaryInfo"), dict)
           and p["plotSummaryInfo"].get("plotSummaryText")
    ]
    if not labeled_paras:
        return samples

    for para in labeled_paras:
        src_text     = clean_text(para.get("srcText", ""))
        psi          = para.get("plotSummaryInfo", {})
        summary_text = clean_text(psi.get("plotSummaryText", ""))
        theme        = psi.get("classification", "")
        age          = psi.get("readAge", "")
        form         = psi.get("form", "")  # long-form / short-form

        # 라벨 수집
        character = para.get("character", "") or ""
        setting   = para.get("setting", "") or ""
        action    = para.get("action", "") or ""
        feeling   = para.get("feeling", "") or ""
        cause     = para.get("causalRelationship", "") or ""
        outcome   = para.get("outcomeResolution", "") or ""

        if not src_text or not summary_text:
            continue

        # ── 샘플 A: 줄거리 요약 생성 ──
        samples.append({
            "type": "plot_summary",
            "instruction": (
                f"다음 동화 내용을 읽고 핵심 줄거리를 {form} 형식으로 요약하세요.\n"
                f"장르: {theme}, 대상 연령: {age}"
            ),
            "input": src_text,
            "output": summary_text,
            "metadata": {
                "title": title, "theme": theme, "age": age,
                "form": form, "source": "labeled_summary",
            }
        })

        # ── 샘플 B: 등장인물+배경+감정 → 스토리 생성 ──
        hints = []
        if character: hints.append(f"등장인물: {character}")
        if setting:   hints.append(f"배경: {setting}")
        if feeling:   hints.append(f"감정: {feeling}")
        if action:    hints.append(f"행동: {action}")

        if hints:
            samples.append({
                "type": "story_from_elements",
                "instruction": (
                    f"아래 요소를 모두 포함하여 어린이 동화의 한 장면을 써주세요.\n"
                    f"장르: {theme}, 대상 연령: {age}"
                ),
                "input": "\n".join(hints),
                "output": src_text,
                "metadata": {
                    "title": title, "theme": theme, "age": age,
                    "source": "labeled_elements",
                }
            })

        # ── 샘플 C: 인과관계 → 스토리 전개 ──
        if cause and outcome:
            samples.append({
                "type": "causal_story",
                "instruction": (
                    "다음 원인과 결과를 자연스러운 동화 문장으로 연결하여 써주세요."
                ),
                "input": f"[원인] {cause}\n[결과] {outcome}",
                "output": src_text,
                "metadata": {
                    "title": title, "theme": theme, "age": age,
                    "source": "labeled_causal",
                }
            })

        # ── 샘플 D: 다음 내용 예측 (prediction 필드 사용) ──
        prediction = para.get("prediction", "") or ""
        if prediction:
            samples.append({
                "type": "story_prediction",
                "instruction": "다음 동화 장면을 읽고, 다음에 어떤 일이 일어날지 예측하세요.",
                "input": src_text,
                "output": prediction,
                "metadata": {
                    "title": title, "theme": theme, "age": age,
                    "source": "labeled_prediction",
                }
            })

    return samples


# ═══════════════════════════════════════════════
# 메인 전처리 실행
# ═══════════════════════════════════════════════
def run_preprocessing():
    print("=" * 55)
    print("  동화 데이터 전처리 시작")
    print("=" * 55)

    all_samples = []
    counts = {
        "sublabel": 0,
        "source": 0,
        "labeled": 0,
    }

    # 1) Sublabel 처리
    print("\n[1/3] Sublabel 텍스트 처리 중...")
    sublabel_files = list(SUBLABEL_DIR.rglob("*.json"))
    for i, fp in enumerate(sublabel_files):
        s = process_sublabel(fp)
        all_samples.extend(s)
        counts["sublabel"] += len(s)
        if (i + 1) % 200 == 0:
            print(f"  진행: {i+1}/{len(sublabel_files)} 파일 처리됨")
    print(f"  → Sublabel 샘플: {counts['sublabel']:,}개")

    # 2) Training 원천데이터 처리
    print("\n[2/3] Training 원천데이터 처리 중...")
    src_files = list(TRAIN_SRC_DIR.rglob("*.json"))
    for fp in src_files:
        s = process_source(fp)
        all_samples.extend(s)
        counts["source"] += len(s)
    print(f"  → 원천데이터 샘플: {counts['source']:,}개")

    # 3) 라벨링 데이터 처리 (Training + Validation)
    print("\n[3/3] 라벨링 데이터 처리 중...")
    lbl_files  = list(TRAIN_LBL_DIR.rglob("*.json"))
    lbl_files += list(VAL_LBL_DIR.rglob("*.json"))
    for fp in lbl_files:
        s = process_labeled(fp)
        all_samples.extend(s)
        counts["labeled"] += len(s)
    print(f"  → 라벨링 샘플: {counts['labeled']:,}개")

    # ── 형식 변환 (ChatML / Alpaca 형식) ──
    print("\n[변환] Instruction 형식으로 변환 중...")
    formatted = []
    for s in all_samples:
        instruction = s["instruction"]
        inp         = s.get("input", "")
        output      = s["output"]

        # ChatML 형식 (HuggingFace 호환)
        if inp:
            prompt = f"<s>[INST] {instruction}\n\n{inp} [/INST]"
        else:
            prompt = f"<s>[INST] {instruction} [/INST]"

        formatted.append({
            "text": f"{prompt} {output} </s>",
            "prompt": prompt,
            "output": output,
            "type": s["type"],
            "metadata": s.get("metadata", {}),
        })

    # ── Train / Val 분리 (9:1) ──
    random.seed(42)
    random.shuffle(formatted)
    split_idx   = int(len(formatted) * 0.9)
    train_data  = formatted[:split_idx]
    val_data    = formatted[split_idx:]

    # ── 저장 ──
    train_path = OUT_DIR / "train.jsonl"
    val_path   = OUT_DIR / "val.jsonl"
    stats_path = OUT_DIR / "stats.json"

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for item in val_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # 타입별 통계
    type_counts = {}
    for s in formatted:
        t = s["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    age_counts = {}
    theme_counts = {}
    for s in formatted:
        age   = s["metadata"].get("age", "unknown")
        theme = s["metadata"].get("theme", "unknown")
        age_counts[age]     = age_counts.get(age, 0) + 1
        theme_counts[theme] = theme_counts.get(theme, 0) + 1

    stats = {
        "total_samples": len(formatted),
        "train_samples": len(train_data),
        "val_samples":   len(val_data),
        "by_source":     counts,
        "by_type":       type_counts,
        "by_age":        age_counts,
        "by_theme":      theme_counts,
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # ── 결과 출력 ──
    print("\n" + "=" * 55)
    print("  전처리 완료!")
    print("=" * 55)
    print(f"\n  총 샘플:  {len(formatted):>7,}개")
    print(f"  학습용:   {len(train_data):>7,}개  → {train_path.name}")
    print(f"  검증용:   {len(val_data):>7,}개  → {val_path.name}")
    print(f"\n  [샘플 타입별 분포]")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:<30} {c:>5,}개")
    print(f"\n  [연령별 분포]")
    for a, c in sorted(age_counts.items()):
        print(f"    {a:<20} {c:>5,}개")
    print(f"\n  [주제별 분포]")
    for th, c in sorted(theme_counts.items()):
        print(f"    {th:<20} {c:>5,}개")
    print(f"\n  통계 저장: {stats_path}")


if __name__ == "__main__":
    run_preprocessing()
