"""Conservative, optional CPU-only review signals for Space candidates.

Object counts are experimental: they do not verify identity or approve images.
"""
import io
import math
from functools import lru_cache

from PIL import Image

MODEL_ID = "google/owlv2-base-patch16-ensemble"
MIN_SCORE = 0.45


def _overlap_fraction(first, second):
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    b = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    return intersection / min(a, b) if min(a, b) else 0.0


def count_distinct_detections(detections, min_score=MIN_SCORE):
    if not math.isfinite(min_score) or not 0 <= min_score <= 1:
        raise ValueError("Invalid detection threshold")
    accepted = []
    for item in detections:
        score = float(item["score"])
        box = tuple(float(value) for value in item["box"])
        if not math.isfinite(score) or len(box) != 4 or not all(math.isfinite(v) for v in box):
            raise ValueError("Invalid detection")
        if score >= min_score and box[2] > box[0] and box[3] > box[1]:
            accepted.append({"score": score, "box": box})
    accepted.sort(key=lambda item: item["score"], reverse=True)
    selected = []
    for item in accepted:
        if all(_overlap_fraction(item["box"], previous["box"]) < 0.8 for previous in selected):
            selected.append(item)
    return selected


@lru_cache(maxsize=1)
def _load_detector():
    import torch
    from transformers import Owlv2ForObjectDetection, Owlv2Processor

    processor = Owlv2Processor.from_pretrained(MODEL_ID, local_files_only=True)
    model = Owlv2ForObjectDetection.from_pretrained(MODEL_ID, local_files_only=True).to("cpu").eval()
    return torch, processor, model


def review_telescope(data):
    torch, processor, model = _load_detector()
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError("Image too large")
        image = source.convert("RGB")
    inputs = processor(text=[["a brass telescope"]], images=image, return_tensors="pt")
    with torch.inference_mode():
        output = model(**inputs)
    result = processor.post_process_grounded_object_detection(
        output, threshold=MIN_SCORE, target_sizes=torch.tensor([[image.height, image.width]])
    )[0]
    detections = count_distinct_detections([
        {"score": score.item(), "box": box.tolist()}
        for score, box in zip(result["scores"], result["boxes"])
    ])
    return {
        "model": MODEL_ID,
        "threshold": MIN_SCORE,
        "object_count": len(detections),
        "object_status": "one_detected" if len(detections) == 1 else "review_required",
        "identity_status": "unverified",
        "approval": "review_required",
    }
