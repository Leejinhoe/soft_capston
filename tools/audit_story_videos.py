"""Decode every frame; report integrity and temporal diagnostics, not aesthetic scores."""
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / 'output/background_validation_final_3s'
    renders = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    reports = []
    for render in renders:
        path = folder / (render['key'] + '.mp4')
        reader = imageio.get_reader(str(path))
        deltas = []
        previous = None
        count = 0
        try:
            for frame in reader:
                frame = np.asarray(frame)
                assert frame.shape[:2] == (384, 640), path
                assert int(frame.max()) - int(frame.min()) > 32, path
                if previous is not None:
                    deltas.append(float(np.abs(frame.astype(np.int16) - previous).mean()))
                previous = frame.astype(np.int16)
                count += 1
        finally:
            reader.close()
        assert count == render['frames'], (path, count)
        assert max(deltas) > 0, path
        reports.append({**render, 'decoded_frames': count,
                        'identical_adjacent_frames': sum(value == 0 for value in deltas),
                        'mean_frame_difference': round(float(np.mean(deltas)), 3),
                        'max_frame_difference': round(max(deltas), 3)})
    (folder / 'frame_audit.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
