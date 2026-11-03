import unittest
from pathlib import Path

from PIL import Image


class CharacterReferenceViewsTests(unittest.TestCase):
    def test_all_catalog_characters_have_valid_side_and_back_views(self):
        directory = Path(__file__).resolve().parent.parent / 'assets' / 'characters' / 'reference_views'
        for gender in ('male', 'female'):
            for number in range(1, 9):
                for view in ('side', 'back'):
                    with self.subTest(gender=gender, number=number, view=view):
                        path = directory / f'{gender}_{number:02d}_{view}.png'
                        self.assertTrue(path.is_file(), f'Missing {path.name}')
                        with Image.open(path) as image:
                            self.assertEqual(image.format, 'PNG')
                            self.assertEqual(image.mode, 'RGBA')
                            self.assertGreaterEqual(min(image.size), 512)
                            image.verify()
