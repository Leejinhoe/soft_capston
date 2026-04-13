"""
동화 AI — QLoRA Fine-tuning 스크립트
----------------------------------------------
SOLAR-10.7B 또는 EXAONE-3.5-7.8B 기반 QLoRA 학습

요구사항:
  pip install transformers peft trl datasets bitsandbytes accelerate
  GPU: 최소 16GB VRAM (24GB 권장)
"""

import json
import torch
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, TaskType
from trl import SFTTrainer

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
class Config:
    # ── 모델 선택 (둘 중 하나) ──
    # 옵션 A: SOLAR (가볍고 빠름, 한국어 우수)
    MODEL_NAME = "Upstage/SOLAR-10.7B-v1.0"

    # 옵션 B: EXAONE (LG, 한국어 최적화, 오픈소스)
    # MODEL_NAME = "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"

    # 옵션 C: 로컬 환경 부족 시 소형 모델
    # MODEL_NAME = "beomi/Llama-3-Open-Ko-8B"

    # ── 데이터 경로 ──
    DATA_DIR   = Path(__file__).parent / "data"
    OUTPUT_DIR = Path(__file__).parent / "checkpoints"

    # ── QLoRA 설정 ──
    LOAD_IN_4BIT     = True        # 4비트 양자화 (GPU 절약)
    LORA_R           = 16          # LoRA rank (8~64, 높을수록 성능↑ 속도↓)
    LORA_ALPHA       = 32          # LoRA 스케일 (보통 r * 2)
    LORA_DROPOUT     = 0.05        # 드롭아웃
    TARGET_MODULES   = ["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"]

    # ── 학습 설정 ──
    MAX_SEQ_LEN      = 1024        # 최대 토큰 길이 (동화 특성상 1024 충분)
    BATCH_SIZE       = 2           # GPU 메모리에 따라 조정 (16GB → 2, 24GB → 4)
    GRAD_ACCUM       = 8           # Gradient Accumulation (실질 배치 = 2*8=16)
    LEARNING_RATE    = 2e-4
    EPOCHS           = 3
    WARMUP_RATIO     = 0.05
    LOGGING_STEPS    = 20
    SAVE_STEPS       = 200
    EVAL_STEPS       = 200


# ─────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────
def load_dataset_from_jsonl(path: Path) -> Dataset:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                samples.append({"text": obj["text"]})
    return Dataset.from_list(samples)


def load_datasets():
    print(f"데이터 로드: {Config.DATA_DIR}")
    train_ds = load_dataset_from_jsonl(Config.DATA_DIR / "train.jsonl")
    val_ds   = load_dataset_from_jsonl(Config.DATA_DIR / "val.jsonl")
    print(f"  학습 샘플: {len(train_ds):,}개")
    print(f"  검증 샘플: {len(val_ds):,}개")
    return train_ds, val_ds


# ─────────────────────────────────────────────
# 모델 & 토크나이저 로드
# ─────────────────────────────────────────────
def load_model_and_tokenizer():
    print(f"\n모델 로드: {Config.MODEL_NAME}")

    # 4비트 양자화 설정
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",          # 정규화 float4 (권장)
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,     # 이중 양자화로 추가 압축
    ) if Config.LOAD_IN_4BIT else None

    model = AutoModelForCausalLM.from_pretrained(
        Config.MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",                  # GPU 자동 분배
        trust_remote_code=True,             # EXAONE 사용 시 필요
    )

    tokenizer = AutoTokenizer.from_pretrained(
        Config.MODEL_NAME,
        trust_remote_code=True,
    )

    # 패딩 토큰 설정 (없는 경우)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id

    print(f"  모델 파라미터: {model.num_parameters() / 1e9:.1f}B")
    return model, tokenizer


# ─────────────────────────────────────────────
# LoRA 설정
# ─────────────────────────────────────────────
def apply_lora(model):
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=Config.LORA_R,
        lora_alpha=Config.LORA_ALPHA,
        lora_dropout=Config.LORA_DROPOUT,
        target_modules=Config.TARGET_MODULES,
        bias="none",
    )
    model = get_peft_model(model, lora_config)

    trainable, total = model.get_nb_trainable_parameters()
    print(f"\nLoRA 적용 완료")
    print(f"  학습 파라미터: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")
    return model


# ─────────────────────────────────────────────
# 학습 실행
# ─────────────────────────────────────────────
def train():
    Config.OUTPUT_DIR.mkdir(exist_ok=True)

    # 데이터 로드
    train_ds, val_ds = load_datasets()

    # 모델 로드
    model, tokenizer = load_model_and_tokenizer()

    # LoRA 적용
    model = apply_lora(model)

    # 학습 인자
    training_args = TrainingArguments(
        output_dir=str(Config.OUTPUT_DIR),
        num_train_epochs=Config.EPOCHS,
        per_device_train_batch_size=Config.BATCH_SIZE,
        per_device_eval_batch_size=Config.BATCH_SIZE,
        gradient_accumulation_steps=Config.GRAD_ACCUM,
        learning_rate=Config.LEARNING_RATE,
        warmup_ratio=Config.WARMUP_RATIO,
        lr_scheduler_type="cosine",
        fp16=True,                          # half precision 학습
        logging_steps=Config.LOGGING_STEPS,
        evaluation_strategy="steps",
        eval_steps=Config.EVAL_STEPS,
        save_strategy="steps",
        save_steps=Config.SAVE_STEPS,
        save_total_limit=3,                 # 최근 3개 체크포인트만 보존
        load_best_model_at_end=True,
        report_to="none",                   # wandb 사용 시 "wandb"로 변경
        dataloader_num_workers=2,
    )

    # SFT Trainer (Supervised Fine-Tuning)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=Config.MAX_SEQ_LEN,
        packing=True,                       # 짧은 샘플들을 합쳐서 GPU 효율 극대화
    )

    print("\n학습 시작!")
    print(f"  예상 스텝: {len(train_ds) * Config.EPOCHS // (Config.BATCH_SIZE * Config.GRAD_ACCUM):,}")
    trainer.train()

    # 저장
    final_dir = Config.OUTPUT_DIR / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"\n모델 저장 완료: {final_dir}")


if __name__ == "__main__":
    train()
