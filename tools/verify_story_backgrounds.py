"""Render every story background using real selected-character assets."""
import asyncio
import json
import sys
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'DB연결 테스트'))
from story_background_pack import PACK
from background_assets import BACKGROUND_ASSETS
from hf_video_provider import generate_hf_fairytale_video


async def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    frame_count = round(duration * 30)
    output = ROOT / f'output/background_validation_final_{duration:g}s'
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    cases = list(PACK) + [('fantasy_castle', ['fantasy'], ['castle'], [])]
    sheet = Image.new('RGB', (960, len(cases) * 238), 'white')
    for index, (key, genres, keywords, _) in enumerate(cases):
        if only and key != only:
            continue
        character = 'male_01' if index % 2 == 0 else 'female_01'
        asset = next(asset for asset in BACKGROUND_ASSETS if asset['key'] == key)
        background = (ROOT / 'assets/backgrounds' / asset['video_filename']).read_bytes()
        assets = ROOT / 'assets/characters'
        result = await generate_hf_fairytale_video(
            image_bytes=background, story_text='The child runs along the path toward the destination.',
            genre=genres[0], age='7', width=640, height=384,
            num_frames=frame_count, frame_rate=30, steps=8,
            motion_context={
                'background_key': key, 'background_bytes': background,
                'character_key': character, 'character_pose': 'walking',
                'character_bytes': (assets / f'{character}_reference_v2.png').read_bytes(),
                'character_run_cycle_sheet_bytes': (assets / f'motion_sheets/{character}_run_cycle_v16.png').read_bytes(),
                'character_target_journey_sheet_bytes': (assets / f'motion_sheets/{character}_target_journey_sheet_v4.png').read_bytes(),
                'action_tags': ['running'], 'motion_focus': 'character',
                'action_semantics': {'motion_mode': 'locomotion', 'animation_action': 'journey',
                    'pace': 'run', 'directionality': 'toward_target', 'path_pattern': 'direct',
                    'requires_target': True, 'target_type': 'destination', 'participant_count': 1},
            },
        )
        path = output / f'{key}.mp4'
        path.write_bytes(result['video_bytes'])
        reader = imageio.get_reader(str(path))
        try:
            count = reader.count_frames()
            assert count == frame_count
            assert abs(reader.get_meta_data()['fps'] - 30) < .01
            for column, frame in enumerate((0, frame_count // 2, frame_count - 1)):
                image = Image.fromarray(reader.get_data(frame))
                assert image.size == (640, 384)
                assert image.convert('L').getextrema()[0] != image.convert('L').getextrema()[1]
                image.thumbnail((320, 192))
                sheet.paste(image, (column * 320, index * 238 + 30))
            ImageDraw.Draw(sheet).text((8, index * 238 + 8), key, fill='black')
        finally:
            reader.close()
        reports.append({'key': key, 'character': character, 'frames': count, 'duration_seconds': duration,
                        'animation_mode': result['parameters'].get('animation_mode')})
        print(key, 'OK', flush=True)
    suffix = '_' + only if only else ''
    sheet.save(output / f'contact_sheet{suffix}.jpg')
    (output / f'report{suffix}.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')


if __name__ == '__main__':
    asyncio.run(main())
