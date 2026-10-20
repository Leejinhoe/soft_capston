"""Render real local assets through the production image compositor."""
import json
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'DB연결 테스트'))
from media_compositor import compose_story_scene


def main():
    output = ROOT / 'output' / 'image_checks'
    output.mkdir(parents=True, exist_ok=True)
    background = (ROOT / 'assets/backgrounds/fantasy_castle_wide_v2.png').read_bytes()
    records = []
    for gender in ('male', 'female'):
        for number in range(1, 9):
            key = f'{gender}_{number:02d}'
            asset = ROOT / f'assets/characters/{key}_reference_v2.png'
            start = time.perf_counter()
            result = compose_story_scene(background, asset.read_bytes(), width=768, height=512)
            with Image.open(BytesIO(result)) as image:
                image.load()
                assert image.size == (768, 512)
                assert image.convert('L').getextrema()[0] != image.convert('L').getextrema()[1]
            (output / f'{key}.png').write_bytes(result)
            records.append({'character': key, 'seconds': round(time.perf_counter() - start, 3)})
    result = compose_story_scene(
        background,
        (ROOT / 'assets/characters/male_01_reference_v2.png').read_bytes(),
        secondary_character_bytes=(ROOT / 'assets/characters/female_01_reference_v2.png').read_bytes(),
        effect_tags=['sunset_glow'], prop_tags=['woven_basket'], width=768, height=512,
    )
    (output / 'two_characters_sunset.png').write_bytes(result)
    (output / 'results.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'passed': len(records), 'seconds': sum(r['seconds'] for r in records), 'output': str(output)}))


if __name__ == '__main__':
    main()
