from typing import Any, Dict

from hf_image_provider import generate_hf_fairytale_image, get_hf_image_config
from hf_media_common import HfMediaError
from hf_video_provider import generate_hf_fairytale_video, get_hf_video_config


def get_hf_media_config() -> Dict[str, Any]:
    return {
        "provider": "huggingface",
        **get_hf_image_config(),
        **get_hf_video_config(),
    }
