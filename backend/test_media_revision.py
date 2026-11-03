import tempfile
import unittest
from pathlib import Path
from media_revision import render_revision


class RevisionTests(unittest.TestCase):
    def test_asset_update_addition_and_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assets = root/'assets/characters'
            assets.mkdir(parents=True)
            first = render_revision(root)
            image = assets/'hero.png'
            image.write_bytes(b'first')
            second = render_revision(root)
            self.assertNotEqual(first, second)
            self.assertEqual(second, render_revision(root))
            image.write_bytes(b'updated image')
            self.assertNotEqual(second, render_revision(root))
            image.unlink()
            self.assertEqual(first, render_revision(root))
