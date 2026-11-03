import io
import os
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageDraw

from motion_asset_candidate import candidate_generation_enabled, generate_candidate, validate_motion_sheet


def sheet(overlap=False):
    image = Image.new('RGBA', (800, 400))
    draw = ImageDraw.Draw(image)
    for i in range(8):
        x, y = (i % 4) * 200, (i // 4) * 200
        draw.rectangle((x + (0 if overlap and i == 0 else 30), y + 20, x + 160, y + 180), fill='red')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


class CandidateTests(unittest.IsolatedAsyncioTestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(candidate_generation_enabled())

    def test_rejects_touching_cell_boundary(self):
        with self.assertRaises(ValueError):
            validate_motion_sheet(sheet(overlap=True))

    async def test_candidate_is_quarantined_with_reference(self):
        generator = AsyncMock(return_value=sheet())
        data, metadata = await generate_candidate(
            {'character_key': 'male_01', 'action': 'wave'}, b'reference', generator)
        self.assertEqual(data, sheet())
        self.assertEqual(metadata['status'], 'review_required')
        self.assertEqual(metadata['identity_verification'], 'not_performed')
        self.assertEqual(generator.await_args.args[0], b'reference')

    async def test_multi_character_interactions_do_not_call_generator(self):
        generator = AsyncMock()
        with self.assertRaises(ValueError):
            await generate_candidate(
                {'action': 'handoff', 'requires_partner': True}, b'reference', generator)
        generator.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
