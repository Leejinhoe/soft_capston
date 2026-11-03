import asyncio
import io
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from hf_space_character import (
    CHARACTER_TRIGGER_MAP,
    CHARACTER_IDENTITY_DESCRIPTIONS,
    _create_space_client,
    action_for_scene,
    build_sdxl_lora_prompt,
    build_sdxl_lora_negative_prompt,
    build_sdxl_scene_prompt,
    enabled,
    extract_character,
    generate_character_sdxl_lora,
    get_character_trigger,
    sdxl_lora_enabled,
)


def picture(extra=False, touching=False):
    image = Image.new("RGB", (128, 128), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0 if touching else 40, 15, 75, 110), fill="blue")
    if extra:
        draw.rectangle((95, 45, 123, 110), fill="red")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class SpaceCharacterTests(unittest.TestCase):
    def test_space_client_supports_both_token_parameter_versions(self):
        def old(space, hf_token=None, **kwargs):
            return space, hf_token, kwargs
        def new(space, token=None, **kwargs):
            return space, token, kwargs
        for constructor in (old, new):
            result = _create_space_client(constructor, 'private/test', 'secret', 'folder')
            self.assertEqual(result[1], 'secret')
            self.assertEqual(result[2]['download_files'], 'folder')

    def test_scene_plan_supplies_action_without_hiding_story_in_background(self):
        prompt = build_sdxl_scene_prompt('male_03', 'The hero runs toward the castle.', {'action': 'journey', 'pace': 'run'})
        self.assertIn('running through the scene', prompt)
        self.assertIn('scene: The hero runs toward the castle.', prompt)
        self.assertNotIn('scene background:', prompt)
        unknown = build_sdxl_scene_prompt('female_01', 'The hero waits.', {'action': 'unknown'})
        self.assertIn('a character in a fairytale scene', unknown)

    def test_castle_destination_changes_camera_direction_only_when_explicit(self):
        plan = {'action': 'journey', 'pace': 'run', 'target': 'castle'}
        prompt = build_sdxl_scene_prompt('male_03', 'The hero runs toward the castle.', plan)
        self.assertIn('running away from the viewer toward the castle', prompt)
        self.assertNotIn('back facing viewer', build_sdxl_scene_prompt('male_03', 'The castle is behind the hero.', plan))

    def test_taesan_identity_prompt_preserves_beard_and_tied_hair(self):
        prompt = build_sdxl_lora_prompt('male_03', 'walking', scene_description='a forest')
        self.assertIn('topknot', prompt)
        self.assertIn('beard and moustache', prompt)
        self.assertIn('clean-shaven', build_sdxl_lora_negative_prompt('male_03'))
        self.assertNotIn('clean-shaven', build_sdxl_lora_negative_prompt('male_01'))

    def test_every_character_has_identity_description_without_clothing_lock(self):
        self.assertEqual(set(CHARACTER_TRIGGER_MAP), set(CHARACTER_IDENTITY_DESCRIPTIONS))
        prompt = build_sdxl_lora_prompt('female_01', 'looking around', scene_description='a castle')
        self.assertIn('short dark-brown bob', prompt)
        self.assertNotIn('lavender tunic', prompt)
        self.assertNotIn('white background', prompt)

    def test_disabled_by_default_and_action_mapping_is_limited(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(enabled())
            self.assertFalse(sdxl_lora_enabled())
        self.assertIsNone(action_for_scene("A child plays in a forest"))
        self.assertIsNotNone(action_for_scene("아이가 망원경으로 성을 바라본다"))

    def test_sdxl_lora_enabled_flag(self):
        with patch.dict("os.environ", {"HF_SDXL_LORA_ENABLED": "true"}, clear=True):
            self.assertTrue(sdxl_lora_enabled())

    def test_white_background_becomes_transparent(self):
        cutout = Image.open(io.BytesIO(extract_character(picture())))
        self.assertEqual(cutout.mode, "RGBA")
        self.assertEqual(cutout.getpixel((0, 0))[3], 0)
        self.assertEqual(cutout.getpixel((50, 50))[3], 255)

    def test_rejects_extra_objects_and_cropped_character(self):
        for image in (picture(extra=True), picture(touching=True)):
            with self.assertRaises(ValueError):
                extract_character(image)

    def test_character_trigger_and_prompt_builder(self):
        self.assertEqual(get_character_trigger("male_01"), "sks_minho")
        self.assertEqual(get_character_trigger("female_01"), "sks_mina")
        self.assertEqual(get_character_trigger("female_02"), "sks_hana")
        self.assertEqual(get_character_trigger("male_03"), "sks_taesan")
        self.assertEqual(get_character_trigger("female_03"), "sks_miran")
        self.assertEqual(get_character_trigger("female_04"), "sks_luna")
        self.assertEqual(get_character_trigger("female_06"), "sks_arin")
        self.assertEqual(get_character_trigger("sks_custom"), "sks_custom")

        prompt = build_sdxl_lora_prompt("male_01", "looking through a telescope")
        self.assertIn("sks_minho", prompt)
        self.assertIn("looking through a telescope", prompt)
        self.assertIn("watercolor fairytale", prompt)
        scene = build_sdxl_lora_prompt("female_01", "reading", scene_description="a forest library")
        self.assertIn("sks_mina", scene)
        self.assertIn("a forest library", scene)
        self.assertNotIn("solid plain white background", scene)

    def test_generate_character_sdxl_lora_mock(self):
        raw_png = picture()
        with patch("hf_space_character._call_sdxl_lora_space", return_value=raw_png):
            result = asyncio.run(generate_character_sdxl_lora("sks_male_01, reading book"))
            cutout = Image.open(io.BytesIO(result))
            self.assertEqual(cutout.mode, "RGBA")
            self.assertEqual(cutout.getpixel((0, 0))[3], 0)

    def test_scene_mode_preserves_background(self):
        image = Image.new("RGB", (128, 128), (50, 100, 150))
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        with patch("hf_space_character._call_sdxl_lora_space", return_value=raw.getvalue()):
            result = asyncio.run(generate_character_sdxl_lora("scene", output_mode="scene"))
        self.assertEqual(Image.open(io.BytesIO(result)).getpixel((0, 0)), (50, 100, 150))

    def test_invalid_mode_does_not_call_provider(self):
        with patch("hf_space_character._call_sdxl_lora_space") as provider:
            with self.assertRaises(ValueError):
                asyncio.run(generate_character_sdxl_lora("scene", output_mode="bad"))
        provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()

