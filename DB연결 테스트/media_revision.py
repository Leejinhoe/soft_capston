"""Version local rendering inputs without hashing unchanged assets repeatedly."""
import hashlib
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8192)
def _digest(path, size, modified):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_revision(root):
    root = Path(root)
    files = []
    for folder in ('characters', 'backgrounds', 'effects'):
        directory = root / 'assets' / folder
        if directory.exists():
            files.extend(p for p in directory.rglob('*') if p.is_file())
    backend = root / 'DB연결 테스트'
    files.extend(backend / name for name in (
        'hf_video_provider.py', 'media_compositor.py', 'character_assets.py',
        'background_assets.py', 'story_background_pack.py',
        'motion_policy.py', 'media_quality_gate.py') if (backend / name).exists())
    digest = hashlib.sha256()
    for path in sorted(files):
        stat = path.stat()
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(_digest(str(path), stat.st_size, stat.st_mtime_ns).encode('ascii'))
    return digest.hexdigest()
