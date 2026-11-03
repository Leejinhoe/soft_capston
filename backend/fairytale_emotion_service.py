"""Lazy CPU-only KOTE inference, separate from story generation and MongoDB."""
import json
import os
from pathlib import Path
from threading import Lock

from fastapi import APIRouter
from pydantic import BaseModel, Field
from kote_inference import prepare_target_input, summarize_logits, presentation_review, verify_token_id_mapping

LABELS = ['불평/불만', '환영/호의', '감동/감탄', '지긋지긋', '고마움', '슬픔', '화남/분노', '존경',
    '기대감', '우쭐댐/무시함', '안타까움/실망', '비장함', '의심/불신', '뿌듯함', '편안/쾌적',
    '신기함/관심', '아껴주는', '부끄러움', '공포/무서움', '절망', '한심함', '역겨움/징그러움',
    '짜증', '어이없음', '없음', '패배/자기혐오', '귀찮음', '힘듦/지침', '즐거움/신남', '깨달음',
    '죄책감', '증오/혐오', '흐뭇함(귀여움/예쁨)', '당황/난처', '경악', '부담/안_내킴', '서러움',
    '재미없음', '불쌍함/연민', '놀람', '행복', '불안/걱정', '기쁨', '안심/신뢰']
VOCAB_SHA = 'f81fa98571d4c6bd0deb045bc2f0ed8f8b5c64a2994b3b0f013eb707167839e9'
router = APIRouter(prefix='/api/emotions', tags=['emotions'])


class EmotionRequest(BaseModel):
    story_text: str = Field(default='', max_length=20000)
    choices: list[str] = Field(default_factory=list, max_length=3)
    selected_choice: str | None = Field(default=None, max_length=1000)


def unavailable(status='unavailable'):
    return {'emotion_label_source': 'kote_checkpoint_v1', 'analysis_status': status,
        'emotion_scoring_enabled': False, 'abstained': True,
        'primary_emotion_index': None, 'primary_emotion': '', 'primary_emotion_display': '',
        'primary_score': 0, 'top_emotions': [], 'active_emotions': [], 'scores': {}, 'scores_by_index': {}}


class KoteRuntime:
    def __init__(self):
        self.lock = Lock()
        self.model = self.tokenizer = None

    def load(self):
        if self.model is not None:
            return
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from kote_inference import resolve_labels
        default = Path(__file__).resolve().parent.parent / 'models' / 'emotion_checkpoint'
        local = Path(r'D:\New project 2\emotion_checkpoint')
        path = Path(os.getenv('KOTE_MODEL_PATH', str(default if default.exists() else local)))
        if not (path / 'model.safetensors').is_file():
            raise RuntimeError('KOTE checkpoint unavailable')
        tokenizer = AutoTokenizer.from_pretrained(os.getenv('KOTE_TOKENIZER', 'beomi/KcELECTRA-base-v2022'),
            local_files_only=True, trust_remote_code=False)
        verify_token_id_mapping(tokenizer, VOCAB_SHA)
        config = json.loads((path / 'config.json').read_text(encoding='utf-8'))
        resolve_labels(config, verified_labels=LABELS)
        torch.set_num_threads(min(torch.get_num_threads(), 4))
        model = AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True,
            trust_remote_code=False, use_safetensors=True).to('cpu').eval()
        self.tokenizer, self.model = tokenizer, model

    def analyze(self, text):
        if not text or not text.strip():
            return unavailable('empty_input')
        with self.lock:
            try:
                self.load()
                import torch
                encoded, budget = prepare_target_input(self.tokenizer, text, max_length=512)
                inputs = {k: torch.tensor([v], dtype=torch.long) for k, v in encoded.items()
                          if k in self.tokenizer.model_input_names}
                with torch.inference_mode():
                    logits = self.model(**inputs).logits[0].tolist()
                summary = summarize_logits(logits, LABELS)
                review = presentation_review(summary)
                summary.update(review)
                summary.update(emotion_label_source='kote_checkpoint_v1', emotion_scoring_enabled=True,
                               input_policy='target_only', budget=budget)
                if review['presentation_status'] != 'emotion_candidates':
                    summary.update(primary_emotion_index=None, primary_emotion='', primary_emotion_display='',
                                   primary_score=0, top_emotions=[], active_emotions=[], scores={}, scores_by_index={}, abstained=True)
                return summary
            except ValueError:
                return unavailable('input_or_mapping_requires_review')
            except Exception:
                return unavailable()


runtime = KoteRuntime()


@router.get('/health')
def emotion_health():
    return {'loaded': runtime.model is not None, 'device': 'cpu', 'policy': 'target_only',
            'score_kind': 'uncalibrated_sigmoid', 'psychological_diagnosis': False}


@router.post('/analyze')
def analyze_emotions(payload: EmotionRequest):
    if any(not choice.strip() or len(choice) > 1000 for choice in payload.choices):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail='Choices must contain 1 to 1000 characters')
    analyzed = {}

    def analyze_once(text):
        if text not in analyzed:
            result = runtime.analyze(text)
            if result.get('emotion_scoring_enabled'):
                analyzed[text] = result
            return result
        return analyzed[text]

    story = analyze_once(payload.story_text)
    choices = [analyze_once(choice) for choice in payload.choices]
    selected = analyze_once(payload.selected_choice) if payload.selected_choice else None
    return {'emotion_scoring_enabled': any(item and item.get('emotion_scoring_enabled') for item in [story, selected, *choices]),
            'story_emotion': story, 'choice_emotions': choices, 'selected_choice_emotion': selected,
            'policy': 'target_only', 'psychological_diagnosis': False}
