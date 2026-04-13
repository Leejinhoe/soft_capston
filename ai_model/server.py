"""
동화 AI — FastAPI 서버
----------------------------------------------
Flutter 앱과 통신하는 REST API 서버

실행:
  pip install fastapi uvicorn transformers peft torch accelerate python-dotenv
  python server.py

모드:
  - MODE=api   : Claude API 사용 (ANTHROPIC_API_KEY 필요)
  - MODE=local : 로컬 fine-tuned 모델 사용 (default, final_model/ 필요)
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="동화 AI API",
    description="어린이 동화 생성 AI — Flutter 앱 연동용",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# 실행 모드
# ─────────────────────────────────────────────
MODE = os.getenv("MODE", "local")
BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"

# ─────────────────────────────────────────────
# 모드 A: Claude API
# ─────────────────────────────────────────────
if MODE == "api":
    import anthropic
    claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def call_model(prompt: str, max_tokens: int = 800) -> str:
        msg = claude.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

# ─────────────────────────────────────────────
# 모드 B: 로컬 Fine-tuned 모델 (Qwen2.5-3B + LoRA)
# ─────────────────────────────────────────────
else:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel

    ADAPTER_PATH = Path(__file__).parent / "final_model"

    # adapter_config.json 에서 베이스 모델 이름 읽기
    _cfg_path = ADAPTER_PATH / "adapter_config.json"
    if _cfg_path.exists():
        with open(_cfg_path) as f:
            _adapter_cfg = json.load(f)
        BASE_MODEL = _adapter_cfg.get("base_model_name_or_path", BASE_MODEL)

    # 디바이스 자동 감지
    # MPS(Apple Silicon)는 4GB 텐서 제한으로 3B 모델 불가 → CPU 사용
    if torch.cuda.is_available():
        _device = "cuda"
        _dtype  = torch.float16
    else:
        _device = "cpu"
        _dtype  = torch.float32

    print(f"[서버] 베이스 모델: {BASE_MODEL}")
    print(f"[서버] 어댑터: {ADAPTER_PATH}")
    print(f"[서버] 디바이스: {_device}")

    # CUDA 있을 때만 4-bit 양자화 사용
    _bnb_config = None
    if _device == "cuda":
        _bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )

    print("[서버] 베이스 모델 로딩 중...")
    _tokenizer = AutoTokenizer.from_pretrained(
        str(ADAPTER_PATH),
        trust_remote_code=True,
    )
    _base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=_bnb_config,          # None이면 그냥 무시됨
        device_map=_device if _device != "mps" else None,
        torch_dtype=_dtype,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    if _device == "mps":
        _base_model = _base_model.to(_device)

    print("[서버] LoRA 어댑터 적용 중...")
    _model = PeftModel.from_pretrained(_base_model, str(ADAPTER_PATH))
    _model.eval()
    print("[서버] 모델 준비 완료 ✓")

    def call_model(prompt: str, max_tokens: int = 800) -> str:
        messages = [{"role": "user", "content": prompt}]
        text = _tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _tokenizer(text, return_tensors="pt").to(_model.device)
        with torch.no_grad():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=0.85,
                top_p=0.92,
                repetition_penalty=1.15,
                do_sample=True,
                pad_token_id=_tokenizer.eos_token_id,
            )
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        return _tokenizer.decode(generated, skip_special_tokens=True).strip()


# ─────────────────────────────────────────────
# 프롬프트 빌더
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 어린이를 위한 한국어 동화 작가 AI입니다.
규칙:
1. 쉽고 따뜻한 문체로 써주세요 (어려운 한자어 금지)
2. 각 문장은 짧고 명확하게
3. 아이들이 상상할 수 있는 생생한 묘사 포함
4. 폭력적/공포스러운 내용 절대 금지
5. 긍정적이고 교육적인 메시지 포함"""

def build_story_prompt(genre: str, age: str, prompt: str, prev_story: str = "") -> str:
    age_guide = {
        "유아": "4-6세 아이를 위해 매우 짧고 간단한 문장으로",
        "초등_저학년": "7-9세 아이를 위해 쉬운 단어와 흥미로운 묘사로",
        "초등_고학년": "10-12세 아이를 위해 풍부한 어휘와 생동감 있는 표현으로",
    }.get(age, "어린이를 위해")
    context = f"\n이전 줄거리:\n{prev_story}\n" if prev_story else ""
    return f"""{SYSTEM_PROMPT}

장르: {genre}
대상 연령: {age} ({age_guide} 작성)
{context}
아이의 요청: {prompt}

위 내용을 바탕으로 동화의 다음 내용을 2-3 문단으로 작성하세요.
각 문단은 3-5 문장으로 구성하고, 마지막에 자연스럽게 멈추세요."""

def build_choices_prompt(story_so_far: str, genre: str, age: str) -> str:
    return f"""{SYSTEM_PROMPT}

다음 동화 내용을 읽고 이야기가 이어질 수 있는 선택지 3가지를 만들어주세요.

[현재까지의 이야기]
{story_so_far[-500:]}

조건:
- 각 선택지는 15자 이내의 짧고 명확한 행동
- 선택지는 서로 확연히 다른 방향으로
- {age} 아이가 이해할 수 있는 수준
- 장르({genre})에 맞는 흥미로운 선택지

반드시 아래 JSON 형식으로만 답하세요:
{{"choices": ["선택지1", "선택지2", "선택지3"]}}"""

def build_continuation_prompt(story: str, choice: str, genre: str, age: str) -> str:
    return f"""{SYSTEM_PROMPT}

장르: {genre}, 대상 연령: {age}

[앞 이야기]
{story[-600:]}

[아이의 선택]
{choice}

위 선택을 바탕으로 동화를 자연스럽게 이어주세요.
2-3 문단으로 작성하고 다음 선택이 필요한 시점에서 멈추세요."""

def build_vocab_prompt(story_text: str, age: str) -> str:
    return f"""다음 동화 내용에서 {age} 아이들이 배울 만한 어려운 단어를 찾아주세요.

[동화 내용]
{story_text[:600]}

반드시 아래 JSON 형식으로만 3-5개 답하세요:
{{"words": [{{"hard": "입수하다", "easy": "물에 빠지다", "definition": "물속으로 들어가다"}}]}}"""

def build_psych_prompt(choices_made: list) -> str:
    choices_str = "\n".join(f"- {c}" for c in choices_made)
    return f"""어린이가 동화에서 아래와 같은 선택을 했습니다:
{choices_str}

이 선택 패턴을 분석하여 아이의 성격 특성을 평가해주세요.
반드시 아래 JSON 형식으로만 답하세요:
{{
  "type": "용감한 탐험가",
  "description": "새로운 것을 두려워하지 않는 성격...",
  "traits": {{"모험적": 85, "친절함": 70, "용감함": 90, "창의적": 65, "협동심": 60}}
}}"""


# ─────────────────────────────────────────────
# 요청/응답 스키마
# ─────────────────────────────────────────────
class StoryStartRequest(BaseModel):
    genre: str
    age: str
    prompt: str

class ContinueRequest(BaseModel):
    story_id: str
    story_so_far: str
    choice: str
    genre: str
    age: str

class ChoicesRequest(BaseModel):
    story_so_far: str
    genre: str
    age: str

class VocabRequest(BaseModel):
    story_text: str
    age: str

class PsychRequest(BaseModel):
    story_id: str
    choices_made: list


# ─────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "동화 AI API",
        "version": "1.0.0",
        "mode": MODE,
        "base_model": BASE_MODEL,
    }

@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE, "timestamp": int(time.time())}


@app.post("/story/start")
async def start_story(req: StoryStartRequest):
    try:
        story_text = call_model(
            build_story_prompt(req.genre, req.age, req.prompt), max_tokens=600
        )
        choices_raw = call_model(
            build_choices_prompt(story_text, req.genre, req.age), max_tokens=200
        )
        try:
            choices = json.loads(choices_raw).get("choices", [])
        except Exception:
            choices = ["계속 앞으로 나아간다", "친구에게 도움을 요청한다", "잠깐 멈추고 생각한다"]

        vocab_raw = call_model(
            build_vocab_prompt(story_text, req.age), max_tokens=300
        )
        try:
            vocab = json.loads(vocab_raw).get("words", [])
        except Exception:
            vocab = []

        return {
            "story_id": f"story_{int(time.time())}",
            "story_text": story_text,
            "choices": choices,
            "vocab": vocab,
            "chapter": 1,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/story/choices")
async def get_choices(req: ChoicesRequest):
    try:
        raw = call_model(
            build_choices_prompt(req.story_so_far, req.genre, req.age), max_tokens=200
        )
        try:
            choices = json.loads(raw).get("choices", [])
        except Exception:
            choices = ["앞으로 나아간다", "도움을 요청한다", "다른 방법을 찾는다"]
        return {"choices": choices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/story/continue")
async def continue_story(req: ContinueRequest):
    try:
        new_text = call_model(
            build_continuation_prompt(req.story_so_far, req.choice, req.genre, req.age),
            max_tokens=600,
        )
        updated_story = req.story_so_far + "\n\n" + new_text
        choices_raw = call_model(
            build_choices_prompt(updated_story, req.genre, req.age), max_tokens=200
        )
        try:
            choices = json.loads(choices_raw).get("choices", [])
        except Exception:
            choices = ["계속 나아간다", "도움을 요청한다", "새로운 방법을 찾는다"]

        vocab_raw = call_model(
            build_vocab_prompt(new_text, req.age), max_tokens=300
        )
        try:
            vocab = json.loads(vocab_raw).get("words", [])
        except Exception:
            vocab = []

        return {
            "story_id": req.story_id,
            "new_text": new_text,
            "choices": choices,
            "vocab": vocab,
            "choice_made": req.choice,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/story/vocab")
async def extract_vocab(req: VocabRequest):
    try:
        raw = call_model(build_vocab_prompt(req.story_text, req.age), max_tokens=400)
        try:
            words = json.loads(raw).get("words", [])
        except Exception:
            words = []
        return {"words": words}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/story/psych")
async def analyze_psychology(req: PsychRequest):
    try:
        if len(req.choices_made) < 2:
            return {
                "type": "탐험가",
                "description": "아직 더 많은 선택이 필요해요!",
                "traits": {"모험적": 50, "친절함": 50, "용감함": 50, "창의적": 50, "협동심": 50},
            }
        raw = call_model(build_psych_prompt(req.choices_made), max_tokens=300)
        try:
            result = json.loads(raw)
        except Exception:
            result = {
                "type": "용감한 탐험가",
                "description": "새로운 것을 두려워하지 않는 멋진 성격이에요!",
                "traits": {"모험적": 80, "친절함": 70, "용감함": 85, "창의적": 65, "협동심": 60},
            }
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
