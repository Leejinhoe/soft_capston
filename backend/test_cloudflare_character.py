import base64
import io
import os
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

import cloudflare_character as cf


def picture():
    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), (30, 60, 90, 255)).save(buf, "PNG")
    return buf.getvalue()


class Response:
    def raise_for_status(self):
        pass

    def json(self):
        return {"success": True, "result": {"image": base64.b64encode(picture()).decode()}}


class Client:
    calls = []
    fail_first = False

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.fail_first and len(self.calls) == 1:
            req = httpx.Request("POST", url)
            resp = httpx.Response(502, request=req)
            raise httpx.HTTPStatusError("Bad Gateway", request=req, response=resp)
        return Response()


class CloudflareTests(unittest.IsolatedAsyncioTestCase):
    async def test_reference_and_scene_are_sent_and_image_returned(self):
        Client.calls.clear()
        Client.fail_first = False
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32, "CLOUDFLARE_AI_TOKEN": "test"}), patch.object(cf.httpx, "AsyncClient", Client):
            output = await cf.generate_scene(picture(), "A girl opens a chest")
        self.assertEqual(Image.open(io.BytesIO(output)).size, (256, 256))
        self.assertIn("opens a chest", Client.calls[0][1]["data"]["prompt"])
        self.assertEqual(Client.calls[0][1]["files"]["input_image_0"][0], "reference.png")

    async def test_transient_502_retries_once_and_succeeds(self):
        Client.calls.clear()
        Client.fail_first = True
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32, "CLOUDFLARE_AI_TOKEN": "test"}), patch.object(cf.httpx, "AsyncClient", Client), patch.object(cf.asyncio, "sleep", return_value=None):
            output = await cf.generate_scene(picture(), "A girl opens a chest")
        self.assertEqual(len(Client.calls), 2)
        self.assertEqual(Image.open(io.BytesIO(output)).size, (256, 256))
        Client.fail_first = False

    async def test_missing_configuration_does_not_send_request(self):
        Client.calls.clear()
        with patch.dict(os.environ, {}, clear=True), patch.object(cf.httpx, "AsyncClient", Client):
            with self.assertRaises(ValueError):
                await cf.generate_scene(picture(), "A scene")
        self.assertFalse(Client.calls)

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(cf.enabled())

    def test_running_is_not_translated_as_walking(self):
        hint = cf._english_visual_hint("미나는 친구를 향해 힘껏 달려갑니다.")
        self.assertIn("running", hint)
        self.assertNotIn("walking", hint)

    def test_walking_remains_walking(self):
        hint = cf._english_visual_hint("미나는 오솔길을 걸어갑니다.")
        self.assertIn("walking", hint)

    async def test_korean_scene_includes_english_visual_action_hint(self):
        Client.calls.clear()
        Client.fail_first = False
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32, "CLOUDFLARE_AI_TOKEN": "test"}), patch.object(cf.httpx, "AsyncClient", Client):
            await cf.generate_scene(picture(), "미나는 무지갯빛 다리를 건너 수정 열쇠를 들고 나아갔습니다.")
        sent_prompt = Client.calls[0][1]["data"]["prompt"]
        self.assertIn("Visual action:", sent_prompt)
        self.assertIn("rainbow bridge", sent_prompt)
