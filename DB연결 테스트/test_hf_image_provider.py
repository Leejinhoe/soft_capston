import unittest
from unittest.mock import patch

import httpx
from PIL import Image

import hf_image_provider
from hf_media_common import HfMediaError


def http_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://router.huggingface.co/test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


class FakeClient:
    def __init__(self, result):
        self.result = result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def text_to_image(self, *args, **kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class HuggingFaceImageProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_prompt_includes_stable_character_context(self):
        prompt = hf_image_provider.build_fairytale_image_prompt(
            story_text="The child enters a moonlit library.",
            genre="fantasy",
            age="7",
            character_description="A child with short brown hair and a red cloak",
            character_style_prompt="soft watercolor with rounded shapes",
            character_action_hint="waving pose, joyful expression",
        )

        self.assertIn("short brown hair and a red cloak", prompt)
        self.assertIn("soft watercolor with rounded shapes", prompt)
        self.assertIn("waving pose, joyful expression", prompt)

    async def test_transient_error_uses_next_provider(self):
        calls = []

        def client_factory(**kwargs):
            provider = kwargs["provider"]
            calls.append(provider)
            if provider == "first":
                return FakeClient(http_error(504))
            return FakeClient(Image.new("RGB", (32, 32), "navy"))

        with (
            patch.object(hf_image_provider, "HF_TOKEN", "test-token"),
            patch.object(hf_image_provider, "HF_IMAGE_API_URL", ""),
            patch.object(hf_image_provider, "HF_IMAGE_PROVIDERS", ("first", "second")),
            patch.object(hf_image_provider, "HF_IMAGE_RETRY_DELAY_SECONDS", 0),
            patch.object(hf_image_provider, "AsyncInferenceClient", side_effect=client_factory),
        ):
            result = await hf_image_provider.generate_hf_fairytale_image(
                story_text="A glowing forest door",
            )

        self.assertEqual(calls, ["first", "second"])
        self.assertEqual(result["inference_provider"], "second")
        self.assertEqual(result["attempted_providers"], ["first", "second"])
        self.assertGreater(len(result["image_bytes"]), 0)

    async def test_non_retryable_error_stops_immediately(self):
        calls = []

        def client_factory(**kwargs):
            calls.append(kwargs["provider"])
            return FakeClient(http_error(402))

        with (
            patch.object(hf_image_provider, "HF_TOKEN", "test-token"),
            patch.object(hf_image_provider, "HF_IMAGE_API_URL", ""),
            patch.object(hf_image_provider, "HF_IMAGE_PROVIDERS", ("first", "second")),
            patch.object(hf_image_provider, "HF_IMAGE_RETRY_DELAY_SECONDS", 0),
            patch.object(hf_image_provider, "AsyncInferenceClient", side_effect=client_factory),
        ):
            with self.assertRaisesRegex(HfMediaError, "first: HTTP 402"):
                await hf_image_provider.generate_hf_fairytale_image(
                    story_text="A glowing forest door",
                )

        self.assertEqual(calls, ["first"])


if __name__ == "__main__":
    unittest.main()
