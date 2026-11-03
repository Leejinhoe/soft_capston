"""Offline inference safeguards; no checkpoint loading, training, or API changes."""
import hashlib
import json
import math
import re
from numbers import Integral


class TargetTooLongError(ValueError):
    pass


def vocabulary_fingerprint(tokenizer):
    """Fingerprint token-to-ID correspondence, not the full tokenizer pipeline."""
    vocab = tokenizer.get_vocab()
    if not isinstance(vocab, dict) or not vocab:
        raise ValueError('Tokenizer vocabulary is missing')
    if any(not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, Integral)
           or v < 0 for k, v in vocab.items()):
        raise ValueError('Invalid token-to-ID correspondence')
    if len(set(vocab.values())) != len(vocab):
        raise ValueError('Tokenizer IDs must be unique')
    payload = json.dumps({k: int(v) for k, v in vocab.items()}, sort_keys=True,
                         ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def verify_token_id_mapping(tokenizer, expected_sha256):
    if not isinstance(expected_sha256, str) or not re.fullmatch('[a-f0-9]{64}', expected_sha256):
        raise ValueError('An independently verified original vocabulary hash is required')
    actual = vocabulary_fingerprint(tokenizer)
    if actual != expected_sha256:
        raise ValueError('Tokenizer token-to-ID correspondence differs from the original')
    return actual


def _ordered_labels(value, count):
    if isinstance(value, (list, tuple)):
        labels = list(value)
    elif isinstance(value, dict):
        mapping = {}
        for key, label in value.items():
            if isinstance(key, bool) or not re.fullmatch(r'0|[1-9][0-9]*', str(key)):
                raise ValueError('Label IDs must be contiguous nonnegative integers')
            index = int(key)
            if index in mapping:
                raise ValueError('Repeated label ID')
            mapping[index] = label
        if set(mapping) != set(range(count)):
            raise ValueError('Label IDs must cover every output exactly once')
        labels = [mapping[i] for i in range(count)]
    else:
        raise ValueError('An explicit ordered label mapping is required')
    if len(labels) != count or any(not isinstance(x, str) or not x.strip() or x != x.strip()
                                  for x in labels):
        raise ValueError('Labels must be nonempty names matching the output count')
    if len(set(labels)) != count:
        raise ValueError('Duplicate label names')
    return labels


def resolve_labels(config, verified_labels=None, expected_count=44):
    """Never infer KOTE order merely from a 44-output generic classifier."""
    if type(expected_count) is not int or expected_count < 1:
        raise ValueError('Invalid expected output count')
    if config.get('num_labels', expected_count) != expected_count:
        raise ValueError('Classifier output count differs from the expected task')
    source = config.get('id2label')
    configured = _ordered_labels(source, expected_count) if source else None
    explicit = (_ordered_labels(verified_labels, expected_count)
                if verified_labels is not None else None)
    generic_count = lambda labels: sum(bool(re.fullmatch(r'LABEL_[0-9]+', x, flags=re.I)) for x in labels)
    if explicit is not None and generic_count(explicit):
        raise ValueError('Verified labels must identify actual emotions')
    if configured is not None and 0 < generic_count(configured) < expected_count:
        raise ValueError('Partially generic config labels require manual review')
    if configured is not None and not generic_count(configured):
        if explicit is not None and explicit != configured:
            raise ValueError('Verified order conflicts with model config')
        labels = configured
    elif explicit is not None:
        labels = explicit
    else:
        raise ValueError('Generic or missing labels require a verified original label file')
    inverse = config.get('label2id')
    if inverse and configured is not None and not generic_count(configured):
        if inverse != {label: i for i, label in enumerate(labels)}:
            raise ValueError('Model label2id and id2label disagree')
    return labels


def prepare_target_input(tokenizer, target, history='', max_length=512):
    """Preserve target IDs; spend only remaining space on recent history."""
    if not isinstance(target, str) or not target.strip():
        raise ValueError('A nonempty current target is required')
    if not isinstance(history, str):
        raise ValueError('History must be text')
    if type(max_length) is not int or max_length < 1:
        raise ValueError('max_length must be positive')
    limit = getattr(tokenizer, 'model_max_length', None)
    if isinstance(limit, Integral) and 0 < limit < 1_000_000 and max_length > limit:
        raise ValueError('Requested length exceeds tokenizer capacity')
    budget = max_length - tokenizer.num_special_tokens_to_add(pair=False)
    target_ids = tokenizer.encode(target, add_special_tokens=False)
    if budget < 1 or not target_ids:
        raise ValueError('No content token budget')
    if len(target_ids) > budget:
        raise TargetTooLongError('Target exceeds capacity; split it explicitly, do not silently truncate')
    history_ids = tokenizer.encode(history, add_special_tokens=False) if history.strip() else []
    delimiter = tokenizer.encode('\n[선택]\n', add_special_tokens=False) if history_ids else []
    available = budget - len(target_ids) - len(delimiter)
    kept_history = history_ids[-available:] if available > 0 else []
    content = kept_history + delimiter + target_ids if kept_history else target_ids
    if callable(getattr(tokenizer, 'prepare_for_model', None)):
        encoded = dict(tokenizer.prepare_for_model(
            content, add_special_tokens=True, truncation=False,
            return_attention_mask=True,
            return_token_type_ids='token_type_ids' in tokenizer.model_input_names,
        ))
    else:
        from tokenizers import Encoding, Tokenizer
        # Transformers 5 removes prepare_for_model; do not mutate shared backend settings.
        backend = Tokenizer.from_str(tokenizer.backend_tokenizer.to_str())
        backend.no_truncation()
        backend.no_padding()
        pieces = []
        if kept_history:
            history_encoding = backend.encode(history, add_special_tokens=False)
            history_encoding.truncate(len(kept_history), direction='left')
            pieces.extend([history_encoding, backend.encode('\n[선택]\n', add_special_tokens=False)])
        pieces.append(backend.encode(target, add_special_tokens=False))
        result = backend.post_process(Encoding.merge(pieces), add_special_tokens=True)
        encoded = {'input_ids': result.ids, 'attention_mask': result.attention_mask}
        if 'token_type_ids' in tokenizer.model_input_names:
            encoded['token_type_ids'] = result.type_ids
    if len(encoded['input_ids']) > max_length:
        raise ValueError('Tokenizer added more special tokens than declared')
    return encoded, {
        'input_policy': 'target_priority_single_sequence_v1',
        'target_tokens': len(target_ids), 'target_tokens_kept': len(target_ids),
        'target_truncated': False, 'history_tokens': len(history_ids),
        'history_tokens_kept': len(kept_history),
        'history_truncated': len(kept_history) < len(history_ids),
        'encoded_tokens': len(encoded['input_ids']), 'max_length': max_length,
    }


def presentation_review(summary, none_label='없음'):
    """Conservative optional display review; never changes the model's raw scores."""
    scores, threshold = summary['scores'], summary['threshold']
    if none_label not in scores:
        raise ValueError('The verified no-emotion label must exist in the output mapping')
    none_active = scores[none_label] >= threshold
    emotion_active = any(score >= threshold for label, score in scores.items() if label != none_label)
    conflict = none_active and emotion_active
    if conflict:
        status = 'review_required'
    elif none_active:
        status = 'no_emotion_candidate'
    elif summary['abstained']:
        status = 'below_threshold'
    else:
        status = 'emotion_candidates'
    return {'presentation_status': status, 'requires_review': conflict,
            'display_emotions': [] if conflict or none_active else list(summary['top_emotions']),
            'warning': 'No-emotion and emotional labels coactivate; do not infer a user psychological state.' if conflict else None,
            'policy': 'optional_none_coactivation_review_v1'}


def summarize_logits(logits, labels, threshold=0.25, top_k=5):
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('threshold must be finite and between zero and one')
    if type(top_k) is not int or top_k < 1:
        raise ValueError('top_k must be positive')
    if not isinstance(labels, (list, tuple)) or not labels:
        raise ValueError('An ordered nonempty label list is required')
    labels = _ordered_labels(labels, len(labels))
    values = list(logits)
    if len(values) != len(labels):
        raise ValueError('Logit count and label count differ')
    pairs = []
    for index, (value, label) in enumerate(zip(values, labels)):
        if isinstance(value, bool):
            raise ValueError('Boolean is not a model logit')
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('Nonfinite model output')
        score = 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))
        pairs.append({'label_index': index, 'label': label, 'label_display': label, 'score': score})
    pairs.sort(key=lambda item: item['score'], reverse=True)
    active = [item for item in pairs if item['score'] >= threshold]
    primary = active[0] if active else None
    return {
        'emotion_label_source': 'verified_checkpoint_labels',
        'emotion_labels_are_generic': False,
        'score_kind': 'sigmoid_activation', 'scores_calibrated': False,
        'abstained': not bool(active),
        'analysis_status': 'detected' if active else 'below_threshold',
        'primary_emotion_index': primary['label_index'] if primary else None,
        'primary_emotion': primary['label'] if primary else '',
        'primary_emotion_display': primary['label_display'] if primary else '',
        'primary_score': primary['score'] if primary else 0.0,
        'top_emotions': active[:top_k], 'active_emotions': active[:top_k],
        'active_emotion_count': len(active),
        'scores': {item['label']: item['score'] for item in pairs},
        'scores_by_index': {str(item['label_index']): item['score'] for item in pairs},
        'threshold': threshold,
    }
