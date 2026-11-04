"""Build a local test montage from an existing synthetic story's GridFS media."""
import argparse
import io
import math
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import gridfs
import imageio.v2 as imageio
import numpy as np
from bson import ObjectId
from dotenv import dotenv_values
from PIL import Image, ImageOps
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS, SECONDS = 960, 540, 24, 3
FADE_FRAMES = 12


def file_id(url, kind):
    parts = urlparse(url or '').path.strip('/').split('/')
    if len(parts) == 4 and parts[:3] == ['api', 'media', kind] and ObjectId.is_valid(parts[3]):
        return ObjectId(parts[3])
    return None


def fit(image):
    image = ImageOps.contain(image.convert('RGB'), (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (WIDTH, HEIGHT), (12, 10, 20))
    canvas.paste(image, ((WIDTH - image.width) // 2, (HEIGHT - image.height) // 2))
    return np.asarray(canvas, dtype=np.uint8)


class FadeWriter:
    def __init__(self, writer, enabled):
        self.writer = writer
        self.enabled = enabled
        self.previous = None

    def append(self, frame, scene_index, scene_count, index):
        original = frame
        if self.enabled and index < FADE_FRAMES:
            alpha = (index + 1) / (FADE_FRAMES + 1)
            previous = self.previous if scene_index else np.zeros_like(frame)
            frame = np.clip(previous.astype(np.float32) * (1 - alpha) + frame.astype(np.float32) * alpha, 0, 255).astype(np.uint8)
        if self.enabled and scene_index == scene_count - 1 and index >= FPS * SECONDS - FADE_FRAMES:
            alpha = (FPS * SECONDS - 1 - index) / FADE_FRAMES
            frame = (frame.astype(np.float32) * alpha).astype(np.uint8)
        self.writer.append_data(frame)
        if index == FPS * SECONDS - 1:
            self.previous = original.copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--story-id', required=True)
    parser.add_argument('--fade', action='store_true')
    args = parser.parse_args()
    env = dotenv_values(ROOT / '.env')
    mongo = MongoClient(env.get('MONGO_URI') or env.get('MONGO_DETAILS'), serverSelectionTimeoutMS=10000)
    db = mongo[env.get('DB_NAME') or env.get('MONGO_DB_NAME') or env.get('MONGO_DATABASE_NAME') or 'fairytale_db']
    bucket = gridfs.GridFSBucket(db, bucket_name=env.get('MEDIA_FILES_BUCKET') or env.get('MEDIA_GRIDFS_BUCKET') or 'media_files')
    story = db.stories.find_one({'_id': ObjectId(args.story_id)})
    if not story or not story.get('completed') or not str(story.get('title', '')).startswith('[테스트]'):
        raise RuntimeError('Only a completed, explicitly marked test story is supported')
    scenes = sorted(story.get('scenes') or [], key=lambda scene: scene.get('step_number', 0))
    if not scenes or len(scenes) > 5:
        raise RuntimeError('This test supports one to five scenes')
    suffix = '_fade' if args.fade else ''
    output = ROOT / 'artifacts' / f'story_assembly_test_{args.story_id}{suffix}.mp4'
    started = time.monotonic()
    selections = []
    with tempfile.TemporaryDirectory(prefix='story_assembly_') as folder:
        with imageio.get_writer(str(output), fps=FPS, codec='libx264', macro_block_size=2,
                                ffmpeg_log_level='error', output_params=['-preset', 'veryfast', '-pix_fmt', 'yuv420p']) as writer:
            fade_writer = FadeWriter(writer, args.fade)
            for scene_index, scene in enumerate(scenes):
                video_id = file_id(scene.get('video_url'), 'videos')
                image_id = file_id(scene.get('image_url'), 'images')
                if not video_id and not image_id:
                    raise RuntimeError(f"Scene {scene.get('step_number')} has no available media")
                if video_id:
                    raw = bucket.open_download_stream(video_id).read()
                    path = Path(folder) / f'{video_id}.mp4'
                    path.write_bytes(raw)
                    with imageio.get_reader(str(path)) as reader:
                        source_fps = float(reader.get_meta_data().get('fps') or FPS)
                        if not math.isfinite(source_fps) or source_fps <= 0:
                            source_fps = FPS
                        last = None
                        for index in range(FPS * SECONDS):
                            try:
                                last = fit(Image.fromarray(reader.get_data(int(index * source_fps / FPS))))
                            except IndexError:
                                if last is None:
                                    raise RuntimeError('Video has no readable frames')
                            fade_writer.append(last, scene_index, len(scenes), index)
                    selections.append('video')
                else:
                    frame = fit(Image.open(io.BytesIO(bucket.open_download_stream(image_id).read())))
                    for index in range(FPS * SECONDS):
                        fade_writer.append(frame, scene_index, len(scenes), index)
                    selections.append('image')
    print('scenes:', len(scenes), 'sources:', ','.join(selections), 'seconds:', len(scenes) * SECONDS)
    print('elapsed_seconds:', round(time.monotonic() - started, 2), 'bytes:', output.stat().st_size)
    print('output:', output)


if __name__ == '__main__':
    main()
