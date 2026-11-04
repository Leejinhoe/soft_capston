"""Combine already generated scene clips, illustrations, and character action animations without a GPU provider."""
from io import BytesIO
import math
import re
import tempfile
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

WIDTH, HEIGHT, FPS = 640, 360, 12
HIGH_QUALITY_FPS = 24
HD_WIDTH, HD_HEIGHT = 1024, 1024
MAX_SCENES = 20
SCENE_SECONDS = 2
MAX_TOTAL_SECONDS = 20
MAX_FRAMES_PER_SCENE = FPS * 3
IMAGE_SCENE_FRAMES = FPS * SCENE_SECONDS
FADE_FRAMES = 8
IMAGE_ZOOM = 0.085

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "assets"
CHARACTER_PATTERN = re.compile(r"^(male|female)_0[1-8]$")

# Deterministic fairytale bokeh motes: (x_norm, y_norm, speed_y, drift_x, radius, phase, peak_alpha)
_BOKEH_MOTES = (
    (0.08, 0.82, 0.045, 0.012, 5.5, 0.0, 0.14),
    (0.16, 0.38, 0.038, -0.010, 4.0, 1.1, 0.11),
    (0.24, 0.68, 0.052, 0.014, 3.5, 2.3, 0.10),
    (0.35, 0.88, 0.042, -0.008, 4.5, 0.7, 0.09),
    (0.48, 0.25, 0.036, 0.010, 3.2, 3.4, 0.08),
    (0.62, 0.76, 0.048, -0.012, 4.2, 1.9, 0.09),
    (0.75, 0.58, 0.044, 0.011, 3.8, 4.2, 0.10),
    (0.84, 0.85, 0.050, -0.013, 5.0, 2.8, 0.13),
    (0.92, 0.42, 0.039, 0.009, 6.0, 5.1, 0.14),
    (0.12, 0.18, 0.041, 0.010, 4.8, 3.9, 0.11),
)

_ACTION_ROUTES = {
    "castle": ((0.30, 0.90), (0.42, 0.85), (0.54, 0.79), (0.66, 0.72)),
    "mystery": ((0.26, 0.89), (0.40, 0.84), (0.54, 0.78), (0.68, 0.71)),
    "nature": ((0.24, 0.87), (0.40, 0.84), (0.56, 0.81), (0.72, 0.78)),
    "adventure": ((0.24, 0.88), (0.40, 0.83), (0.56, 0.78), (0.72, 0.72)),
    "friendship": ((0.26, 0.87), (0.42, 0.86), (0.58, 0.85), (0.74, 0.83)),
}


def detect_story_action(story_text: str) -> str | None:
    """Match action keywords in a scene's text (aligned with StoryCharacterAnimation in Flutter)."""
    text = (story_text or "").lower()
    if any(k in text for k in ("jump", "leap", "hop", "점프", "도약", "뛰어오", "뛰어올", "올랐", "오르")):
        return "jump"
    if any(k in text for k in ("battle", "fight", "attack", "strike", "slash", "sword", "싸우", "공격", "전투", "칼", "베")):
        return "battle"
    if any(k in text for k in ("interact", "reach", "receive", "give", "hand", "rescue", "help", "건네", "받", "잡", "구해", "돕", "열쇠", "발견")):
        return "interaction"
    if any(k in text for k in ("wave", "greet", "magic", "spell", "investigate", "search", "인사", "마법", "주문", "살펴", "조사", "외워", "외웠")):
        return "action"
    if any(k in text for k in ("run", "running", "rush", "walk", "walking", "toward", "move", "travel", "달리", "달려", "뛰", "걷", "걸어", "향해", "나아가", "이동", "떠나", "따라")):
        return "run"
    return None


def _resolve_motion_sheet_path(character_key: str, action: str) -> Path | None:
    key = (character_key or "").strip().lower()
    if not CHARACTER_PATTERN.match(key):
        return None
    sheets_dir = ASSETS_ROOT / "characters" / "motion_sheets"
    candidates = {
        "jump": (f"{key}_jump_cycle_v28.png", f"{key}_jump_cycle_v23.png"),
        "battle": (f"{key}_battle_cycle_v28.png", f"{key}_battle_cycle_v23.png"),
        "interaction": (f"{key}_interaction_cycle_v28.png", f"{key}_interaction_cycle_v23.png"),
        "action": (f"{key}_action_sheet_v28.png", f"{key}_action_sheet_v23.png"),
        "run": (f"{key}_run_cycle_v16.png", f"{key}_run_cycle_v12.png", f"{key}_target_journey_sheet_v4.png"),
    }.get(action, (f"{key}_run_cycle_v16.png",))
    for name in candidates:
        path = sheets_dir / name
        if path.is_file():
            return path
    return None


def _resolve_wide_background_path(genre: str, story_text: str) -> tuple[Path | None, str]:
    bg_dir = ASSETS_ROOT / "backgrounds"
    text = (story_text or "").lower()
    g = (genre or "").strip().lower()
    if any(k in text for k in ("도서관", "책", "지도", "library", "book")):
        path = bg_dir / "mystery_library_wide_v2.png"
        if path.is_file():
            return path, "mystery"
    if any(k in text for k in ("연못", "샘물", "숲", "언덕", "정령", "pond", "forest")):
        path = bg_dir / "nature_pond_wide_v2.png"
        if path.is_file():
            return path, "nature"
    if any(k in text for k in ("다리", "유적", "모험", "bridge", "ruins")):
        path = bg_dir / "adventure_ruins_wide_v2.png"
        if path.is_file():
            return path, "adventure"
    if g in ("미스터리", "mystery"):
        return bg_dir / "mystery_library_wide_v2.png", "mystery"
    if g in ("자연", "동물", "nature"):
        return bg_dir / "nature_pond_wide_v2.png", "nature"
    if g in ("모험", "adventure"):
        return bg_dir / "adventure_ruins_wide_v2.png", "adventure"
    if g in ("우정", "friendship"):
        return bg_dir / "friendship_square_wide_v2.png", "friendship"
    return bg_dir / "fantasy_castle_wide_v2.png", "castle"


def _build_frame_shadow_and_border(fg_w, fg_h, offset, width=WIDTH, height=HEIGHT):
    """Precompute a soft drop-shadow alpha mask and subtle warm border around the foreground viewport."""
    ox, oy = offset
    shadow_mask = Image.new("L", (width, height), 0)
    s_draw = ImageDraw.Draw(shadow_mask)
    s_draw.rectangle((ox - 2, oy + 4, ox + fg_w + 2, oy + fg_h + 6), fill=150)
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=10))
    shadow_alpha = (np.asarray(shadow_mask, dtype=np.float32) / 255.0)[..., None]

    border_overlay = np.zeros((height, width, 4), dtype=np.float32)
    x0, y0 = max(0, ox), max(0, oy)
    x1, y1 = min(width - 1, ox + fg_w - 1), min(height - 1, oy + fg_h - 1)
    warm_rgb = np.array([255.0, 244.0, 218.0], dtype=np.float32)
    border_overlay[y0 : y1 + 1, x0, :3] = warm_rgb
    border_overlay[y0 : y1 + 1, x1, :3] = warm_rgb
    border_overlay[y0, x0 : x1 + 1, :3] = warm_rgb
    border_overlay[y1, x0 : x1 + 1, :3] = warm_rgb
    border_overlay[y0 : y1 + 1, x0, 3] = 0.22
    border_overlay[y0 : y1 + 1, x1, 3] = 0.22
    border_overlay[y0, x0 : x1 + 1, 3] = 0.22
    border_overlay[y1, x0 : x1 + 1, 3] = 0.22
    return shadow_alpha, border_overlay


def _make_backdrop_and_viewport(rgb, width=WIDTH, height=HEIGHT):
    # Full bleed optimization: when image aspect matches canvas or canvas is square
    if width == height and rgb.width == rgb.height:
        fg_w, fg_h = width, height
        offset = (0, 0)
        return None, (fg_w, fg_h), offset, None, None

    bg_hi = ImageOps.fit(
        rgb, (int(width * 1.12), int(height * 1.12)), method=Image.Resampling.BICUBIC
    )
    bg_hi = bg_hi.filter(ImageFilter.GaussianBlur(radius=18))
    bg_hi = ImageEnhance.Brightness(bg_hi).enhance(0.46)
    bg_hi = ImageEnhance.Color(bg_hi).enhance(1.12)
    scale = min(width / max(rgb.width, 1), height / max(rgb.height, 1))
    fg_w = max(1, int(round(rgb.width * scale)))
    fg_h = max(1, int(round(rgb.height * scale)))
    offset = ((width - fg_w) // 2, (height - fg_h) // 2)
    shadow_alpha, border_overlay = _build_frame_shadow_and_border(fg_w, fg_h, offset, width=width, height=height)
    return bg_hi, (fg_w, fg_h), offset, shadow_alpha, border_overlay


def _render_parallax_bg(bg_hi, progress, pan_x=0.0, pan_y=0.0, width=WIDTH, height=HEIGHT):
    if bg_hi is None:
        return None
    bw, bh = bg_hi.size
    bg_scale = 1.0 / (1.06 - 0.045 * max(0.0, min(1.2, progress)))
    cw = bw * bg_scale
    ch = bh * bg_scale
    avail_x = max(0.0, bw - cw)
    avail_y = max(0.0, bh - ch)
    left = avail_x * (0.5 - 0.35 * pan_x)
    top = avail_y * (0.5 - 0.35 * pan_y)
    return bg_hi.resize(
        (width, height),
        resample=Image.Resampling.BILINEAR,
        box=(left, top, left + cw, top + ch),
    )


def _paste_with_shadow_and_border(bg_img, fg_img, offset, shadow_alpha, border_overlay):
    if bg_img is None or shadow_alpha is None:
        return np.asarray(fg_img, dtype=np.uint8)
    bg_arr = np.asarray(bg_img, dtype=np.float32) * (1.0 - 0.55 * shadow_alpha)
    canvas = Image.fromarray(np.clip(bg_arr, 0, 255).astype(np.uint8))
    canvas.paste(fg_img, offset)
    out = np.asarray(canvas, dtype=np.float32)
    if border_overlay is not None:
        b_alpha = border_overlay[..., 3:4]
        out = out * (1.0 - b_alpha) + border_overlay[..., :3] * b_alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _compose_canvas(pil_image, width=WIDTH, height=HEIGHT):
    rgb = pil_image.convert("RGB")
    bg_hi, (fg_w, fg_h), offset, shadow_alpha, border_overlay = (
        _make_backdrop_and_viewport(rgb, width=width, height=height)
    )
    if bg_hi is None:
        return np.asarray(rgb.resize((width, height), resample=Image.Resampling.LANCZOS), dtype=np.uint8)
    bg = _render_parallax_bg(bg_hi, 0.5, width=width, height=height)
    fg = rgb.resize((fg_w, fg_h), resample=Image.Resampling.LANCZOS)
    return _paste_with_shadow_and_border(bg, fg, offset, shadow_alpha, border_overlay)


def _fit(frame, width=WIDTH, height=HEIGHT):
    return _compose_canvas(Image.fromarray(frame), width=width, height=height)


def _render_zoom_frame(
    rgb,
    bg_hi,
    fg_size,
    offset,
    shadow_alpha,
    border_overlay,
    progress,
    pan_dir=1.0,
    width=WIDTH,
    height=HEIGHT,
):
    fg_w, fg_h = fg_size
    src_w, src_h = rgb.size
    clamped_p = max(0.0, float(progress))
    crop_scale = min(1.0, 1.0 / (1.0 + IMAGE_ZOOM * clamped_p))
    crop_w = min(float(src_w), src_w * crop_scale)
    crop_h = min(float(src_h), src_h * crop_scale)
    avail_x = max(0.0, src_w - crop_w)
    avail_y = max(0.0, src_h - crop_h)
    pan_x = pan_dir * 0.28 * (clamped_p - 0.5)
    pan_y = -pan_dir * 0.18 * (clamped_p - 0.5)
    left = max(0.0, min(avail_x, avail_x * max(0.0, min(1.0, 0.5 + pan_x))))
    top = max(0.0, min(avail_y, avail_y * max(0.0, min(1.0, 0.5 + pan_y))))
    right = min(float(src_w), max(left + 1.0, left + crop_w))
    bottom = min(float(src_h), max(top + 1.0, top + crop_h))
    fg = rgb.resize(
        (fg_w, fg_h),
        resample=Image.Resampling.LANCZOS,
        box=(left, top, right, bottom),
    )
    if bg_hi is None or shadow_alpha is None:
        return np.asarray(fg, dtype=np.uint8)
    bg = _render_parallax_bg(bg_hi, progress, pan_x=pan_x, pan_y=pan_y, width=width, height=height)
    return _paste_with_shadow_and_border(bg, fg, offset, shadow_alpha, border_overlay)


def _apply_story_atmosphere(frame_arr, time_sec):
    """Add subtle fairytale floating bokeh motes."""
    out = frame_arr.astype(np.float32)
    h, w, _ = out.shape
    mote_color = np.array([255.0, 238.0, 195.0], dtype=np.float32)
    for x0, y0, speed_y, drift_x, radius, phase, peak_alpha in _BOKEH_MOTES:
        pulse = 0.5 + 0.5 * math.sin(time_sec * 2.2 + phase)
        alpha = peak_alpha * (0.35 + 0.65 * pulse)
        cx = ((x0 + math.sin(time_sec * 0.9 + phase) * drift_x) % 1.0) * w
        cy = ((y0 - time_sec * speed_y) % 1.0) * h
        r_pad = int(math.ceil(radius * 2.4))
        x_min, x_max = max(0, int(cx) - r_pad), min(w, int(cx) + r_pad + 1)
        y_min, y_max = max(0, int(cy) - r_pad), min(h, int(cy) + r_pad + 1)
        if x_min >= x_max or y_min >= y_max:
            continue
        yy, xx = np.ogrid[y_min:y_max, x_min:x_max]
        dist_sq = (xx - cx) ** 2 + (yy - cy) ** 2
        sigma_sq = max(1.0, (radius * 0.75) ** 2)
        weight = (np.exp(-dist_sq / (2.0 * sigma_sq)) * alpha)[..., None]
        patch = out[y_min:y_max, x_min:x_max]
        out[y_min:y_max, x_min:x_max] = patch * (1.0 - weight) + mote_color * weight
    return np.clip(out, 0, 255).astype(np.uint8)


def _image_frames_with_tail(
    data,
    reverse_zoom=False,
    pan_dir=1.0,
    scene_frames=IMAGE_SCENE_FRAMES,
    fade_frames=FADE_FRAMES,
    width=WIDTH,
    height=HEIGHT,
):
    """Turn a still illustration or multi-frame animated GIF/WebP into a smooth clip plus dissolve tail."""
    if not data or len(data) > 10_000_000:
        raise ValueError("Invalid scene image size")
    with Image.open(BytesIO(data)) as im:
        im.load()
        frames = []
        try:
            while True:
                frames.append(im.copy())
                im.seek(len(frames))
        except EOFError:
            pass
        if not frames:
            raise ValueError("Scene image has no frames")

        # Multi-frame animated GIF/WebP
        if len(frames) > 1:
            main_frames = []
            tail_frames = []
            total_wanted = scene_frames + fade_frames
            for index in range(total_wanted):
                src = frames[index % len(frames)]
                composed = _compose_canvas(src, width=width, height=height)
                if index < scene_frames:
                    main_frames.append(composed)
                else:
                    tail_frames.append(composed)
            return main_frames, tail_frames

        # High-res still: sub-pixel LANCZOS Pan + Zoom
        rgb = frames[0].convert("RGB")
        bg_hi, fg_size, offset, shadow_alpha, border_overlay = (
            _make_backdrop_and_viewport(rgb, width=width, height=height)
        )
        main_frames = []
        tail_frames = []
        total_wanted = scene_frames + fade_frames
        for index in range(total_wanted):
            raw_progress = index / max(scene_frames - 1, 1)
            eased = 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, raw_progress)))
            if raw_progress > 1.0:
                eased += (raw_progress - 1.0) * 0.4
            progress = (1.0 - eased) if reverse_zoom else eased
            composed = _render_zoom_frame(
                rgb,
                bg_hi,
                fg_size,
                offset,
                shadow_alpha,
                border_overlay,
                progress,
                pan_dir=pan_dir,
                width=width,
                height=height,
            )
            if index < scene_frames:
                main_frames.append(composed)
            else:
                tail_frames.append(composed)
        return main_frames, tail_frames


def _action_frames_with_tail(
    action_spec: dict,
    scene_frames=IMAGE_SCENE_FRAMES,
    fade_frames=FADE_FRAMES,
    width=WIDTH,
    height=HEIGHT,
):
    """Render a dynamic character motion sequence across an ambient wide storybook background."""
    if not isinstance(action_spec, dict):
        raise ValueError("Invalid action animation spec")
    character_key = str(action_spec.get("character_key") or "")
    action = str(action_spec.get("action") or "run").lower()
    genre = str(action_spec.get("genre") or "castle")
    story_text = str(action_spec.get("story_text") or "")
    fallback_image_bytes = action_spec.get("image_bytes")

    sheet_path = _resolve_motion_sheet_path(character_key, action)
    bg_path, route_key = _resolve_wide_background_path(genre, story_text)

    if not sheet_path or not bg_path:
        if fallback_image_bytes:
            return _image_frames_with_tail(
                fallback_image_bytes,
                scene_frames=scene_frames,
                fade_frames=fade_frames,
                width=width,
                height=height,
            )
        raise ValueError("Action animation assets are unavailable")

    with Image.open(sheet_path) as sheet_im:
        sheet_rgba = sheet_im.convert("RGBA")
        sheet_w, sheet_h = sheet_rgba.size
        cell_w, cell_h = sheet_w // 4, sheet_h // 2
        cells = []
        for idx in range(8):
            col, row = idx % 4, idx // 4
            cell = sheet_rgba.crop((col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h))
            cells.append(cell)

    with Image.open(bg_path) as bg_im:
        wide_bg = bg_im.convert("RGB")

    stage_size = height
    fg_w, fg_h = (stage_size, stage_size) if width != height else (width, height)
    offset = ((width - fg_w) // 2, (height - fg_h) // 2)

    bg_hi, _, _, shadow_alpha, border_overlay = _make_backdrop_and_viewport(
        wide_bg.crop(
            (
                (wide_bg.width - wide_bg.height) // 2,
                0,
                (wide_bg.width + wide_bg.height) // 2,
                wide_bg.height,
            )
        ),
        width=width,
        height=height,
    )
    if width != height:
        shadow_alpha, border_overlay = _build_frame_shadow_and_border(fg_w, fg_h, offset, width=width, height=height)
    else:
        shadow_alpha, border_overlay = None, None

    route = _ACTION_ROUTES.get(route_key, _ACTION_ROUTES["castle"])
    is_locomotion = action == "run"
    cycle_speed = 2.4 if is_locomotion else (1.4 if action == "jump" else 1.8)

    pan_bg_h = fg_h
    pan_bg_w = max(fg_w, int(round(wide_bg.width * (pan_bg_h / max(wide_bg.height, 1)))))
    pan_bg = wide_bg.resize((pan_bg_w, pan_bg_h), resample=Image.Resampling.LANCZOS)
    max_pan_x = max(0.0, float(pan_bg_w - fg_w))

    fx_path = ASSETS_ROOT / "effects" / "action_fx_sheet_v23.png"
    fx_cells = []
    if fx_path.is_file():
        try:
            with Image.open(fx_path) as fx_im:
                fx_rgba = fx_im.convert("RGBA")
                fw, fh = fx_rgba.size
                fc_w, fc_h = fw // 4, fh // 2
                for i in range(8):
                    c, r = i % 4, i // 4
                    fx_cells.append(fx_rgba.crop((c * fc_w, r * fc_h, (c + 1) * fc_w, (r + 1) * fc_h)))
        except Exception:
            fx_cells = []

    main_frames = []
    tail_frames = []
    total_wanted = scene_frames + fade_frames

    for index in range(total_wanted):
        raw_p = index / max(scene_frames - 1, 1)
        clamped_p = max(0.0, min(1.0, raw_p))
        if raw_p > 1.0:
            clamped_p = 1.0 + (raw_p - 1.0) * 0.35

        pan_progress = 0.5 - 0.5 * math.cos(math.pi * min(1.0, clamped_p))
        left_pan = int(round(max_pan_x * pan_progress))
        bg_crop = pan_bg.crop((left_pan, 0, left_pan + fg_w, fg_h))
        stage_img = bg_crop.convert("RGBA")

        # Route-based character position
        if len(route) >= 2:
            seg_count = len(route) - 1
            scaled_p = max(0.0, min(0.999, clamped_p)) * seg_count
            seg_idx = int(scaled_p)
            seg_t = scaled_p - seg_idx
            p0 = route[seg_idx]
            p1 = route[min(seg_idx + 1, len(route) - 1)]
            char_x_norm = p0[0] + (p1[0] - p0[0]) * seg_t
            char_y_norm = p0[1] + (p1[1] - p0[1]) * seg_t
        else:
            char_x_norm = 0.35 + 0.30 * clamped_p
            char_y_norm = 0.82

        # Jump arc
        if action == "jump":
            jump_arc = math.sin(math.pi * max(0.0, min(1.0, clamped_p)))
            char_y_norm -= 0.16 * jump_arc

        char_size = int(round(fg_h * (0.50 + 0.08 * (char_y_norm - 0.70))))
        cell_idx = int(math.floor(raw_p * len(cells) * cycle_speed)) % len(cells)
        sprite_cell = cells[cell_idx]
        char_resized = sprite_cell.resize((char_size, char_size), resample=Image.Resampling.LANCZOS)

        cx = int(round(char_x_norm * fg_w - char_size * 0.5))
        cy = int(round(char_y_norm * fg_h - char_size * 0.90))

        # Soft character shadow
        shadow_w, shadow_h = int(char_size * 0.55), max(4, int(char_size * 0.12))
        shadow_im = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
        sh_draw = ImageDraw.Draw(shadow_im)
        sh_draw.ellipse((0, 0, shadow_w, shadow_h), fill=(20, 20, 30, 95))
        shadow_im = shadow_im.filter(ImageFilter.GaussianBlur(radius=3))
        stage_img.alpha_composite(shadow_im, (cx + (char_size - shadow_w) // 2, cy + char_size - shadow_h // 2))

        stage_img.alpha_composite(char_resized, (cx, cy))

        # Action effect
        if fx_cells and action in ("magic", "action", "interaction"):
            fx_cell = fx_cells[cell_idx % len(fx_cells)]
            fx_sz = int(char_size * 0.45)
            fx_res = fx_cell.resize((fx_sz, fx_sz), resample=Image.Resampling.LANCZOS)
            fx_layer = Image.new("RGBA", (fg_w, fg_h), (0, 0, 0, 0))
            fx_layer.alpha_composite(fx_res, (cx + int(char_size * 0.55), cy + int(char_size * 0.20)))
            stage_img = Image.alpha_composite(stage_img, fx_layer)

        fg_rgb = stage_img.convert("RGB")
        if width == height:
            composed = np.asarray(fg_rgb, dtype=np.uint8)
        else:
            bg = _render_parallax_bg(bg_hi, clamped_p, width=width, height=height)
            composed = _paste_with_shadow_and_border(bg, fg_rgb, offset, shadow_alpha, border_overlay)

        if index < scene_frames:
            main_frames.append(composed)
        else:
            tail_frames.append(composed)

    return main_frames, tail_frames


def _video_frames_with_tail(
    clip,
    folder,
    scene_index,
    out_fps=FPS,
    max_frames=MAX_FRAMES_PER_SCENE,
    fade_frames=FADE_FRAMES,
    target_frames=None,
    width=WIDTH,
    height=HEIGHT,
):
    if not clip or len(clip) > 30_000_000:
        raise ValueError("Invalid scene video size")
    path = Path(folder) / f"scene_{scene_index}.mp4"
    path.write_bytes(clip)
    main_frames = []
    tail_frames = []
    with imageio.get_reader(str(path)) as reader:
        source_fps = float(reader.get_meta_data().get("fps") or FPS)
        if not math.isfinite(source_fps) or source_fps <= 0:
            raise ValueError("Invalid scene video frame rate")
        raw_frames = []
        for raw in reader:
            raw_frames.append(raw)
            if len(raw_frames) >= int(MAX_FRAMES_PER_SCENE * max(source_fps / FPS, 1.0)) + 16:
                break
        if not raw_frames:
            raise ValueError("Scene video contains no frames")

        first_rgb = Image.fromarray(raw_frames[0]).convert("RGB")
        bg_hi, fg_size, offset, shadow_alpha, border_overlay = (
            _make_backdrop_and_viewport(first_rgb, width=width, height=height)
        )
        fg_w, fg_h = fg_size
        bg_static = _render_parallax_bg(bg_hi, 0.45, width=width, height=height)
        natural_frames = max(1, int(round(len(raw_frames) * out_fps / source_fps)))
        desired_main = (
            min(max_frames, max(natural_frames, target_frames))
            if target_frames is not None
            else min(max_frames, natural_frames)
        )
        total_wanted = desired_main + fade_frames
        for index in range(total_wanted):
            if target_frames is not None and len(raw_frames) > 1:
                pos = (index / max(desired_main, 1)) * (len(raw_frames) - 1)
            else:
                pos = index * source_fps / out_fps
            idx0 = int(math.floor(pos))
            if idx0 >= len(raw_frames):
                if target_frames is None:
                    break
                idx0 = len(raw_frames) - 1
            idx1 = min(idx0 + 1, len(raw_frames) - 1)
            frac = max(0.0, min(1.0, pos - idx0))
            if idx1 != idx0 and frac > 1e-3:
                blended_raw = (
                    raw_frames[idx0].astype(np.float32) * (1.0 - frac)
                    + raw_frames[idx1].astype(np.float32) * frac
                ).astype(np.uint8)
            else:
                blended_raw = raw_frames[idx0]
            fg = (
                Image.fromarray(blended_raw)
                .convert("RGB")
                .resize((fg_w, fg_h), resample=Image.Resampling.LANCZOS)
            )
            if width == height and fg_w == width and fg_h == height:
                composed = np.asarray(fg, dtype=np.uint8)
            else:
                composed = _paste_with_shadow_and_border(
                    bg_static, fg, offset, shadow_alpha, border_overlay
                )
            if index < desired_main:
                main_frames.append(composed)
            else:
                tail_frames.append(composed)
        last_raw = raw_frames[-1]
    if len(tail_frames) < fade_frames:
        rgb = Image.fromarray(last_raw).convert("RGB")
        bg_hi, fg_size, offset, shadow_alpha, border_overlay = (
            _make_backdrop_and_viewport(rgb, width=width, height=height)
        )
        needed = fade_frames - len(tail_frames)
        for i in range(needed):
            progress = 0.018 * ((i + 1) / max(needed, 1))
            tail_frames.append(
                _render_zoom_frame(
                    rgb,
                    bg_hi,
                    fg_size,
                    offset,
                    shadow_alpha,
                    border_overlay,
                    progress,
                    width=width,
                    height=height,
                )
            )
    return main_frames, tail_frames


def assemble_scene_media(items, fps=FPS, width=WIDTH, height=HEIGHT, enable_atmosphere=False):
    """Combine scenes given as ("video"|"image"|"action", payload) in story order with smooth cross-dissolves."""
    if not items or len(items) > MAX_SCENES:
        raise ValueError("A story must have between 1 and 20 scenes")
    scale_fps = max(1, int(round(fps / FPS)))
    out_fps = FPS * scale_fps
    max_total_frames = int(MAX_TOTAL_SECONDS * out_fps)
    per_scene_cap = max(out_fps, max_total_frames // len(items))
    base_scene_frames = (
        int(round(2.4 * out_fps)) if scale_fps > 1 else IMAGE_SCENE_FRAMES * scale_fps
    )
    scene_frames = min(base_scene_frames, per_scene_cap)
    max_video_frames = min(MAX_FRAMES_PER_SCENE * scale_fps, per_scene_cap)
    target_video_frames = scene_frames if scale_fps > 1 else None
    fade_frames = min(FADE_FRAMES * scale_fps, max(2, scene_frames // 3))
    with tempfile.TemporaryDirectory(prefix="story_video_") as folder:
        output = Path(folder) / "story.mp4"
        prev_tail = None
        prev_image_bytes = None
        reverse_zoom = False
        pan_dir = 1.0
        global_frame_idx = 0
        with imageio.get_writer(
            str(output),
            fps=out_fps,
            codec="libx264",
            macro_block_size=2,
            ffmpeg_log_level="error",
            output_params=["-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"],
        ) as writer:
            for scene_index, (kind, data) in enumerate(items):
                same_image_as_prev = (
                    kind == "image"
                    and prev_image_bytes is not None
                    and data == prev_image_bytes
                )
                if kind == "image":
                    if same_image_as_prev:
                        reverse_zoom = not reverse_zoom
                    else:
                        reverse_zoom = False
                        pan_dir = 1.0 if (scene_index % 2 == 0) else -1.0
                    frames, tail_frames = _image_frames_with_tail(
                        data,
                        reverse_zoom=reverse_zoom,
                        pan_dir=pan_dir,
                        scene_frames=scene_frames,
                        fade_frames=fade_frames,
                        width=width,
                        height=height,
                    )
                    prev_image_bytes = data
                elif kind == "action":
                    reverse_zoom = False
                    prev_image_bytes = None
                    frames, tail_frames = _action_frames_with_tail(
                        data,
                        scene_frames=scene_frames,
                        fade_frames=fade_frames,
                        width=width,
                        height=height,
                    )
                else:
                    reverse_zoom = False
                    prev_image_bytes = None
                    frames, tail_frames = _video_frames_with_tail(
                        data,
                        folder,
                        scene_index,
                        out_fps=out_fps,
                        max_frames=max_video_frames,
                        fade_frames=fade_frames,
                        target_frames=target_video_frames,
                        width=width,
                        height=height,
                    )
                if not frames:
                    raise ValueError("Scene contains no frames")
                for index, frame in enumerate(frames):
                    if (
                        prev_tail is not None
                        and not same_image_as_prev
                        and index < fade_frames
                    ):
                        outgoing = prev_tail[min(index, len(prev_tail) - 1)]
                        t = (index + 1) / (fade_frames + 1)
                        alpha = 0.5 - 0.5 * math.cos(math.pi * t)
                        blended = (
                            outgoing.astype(np.float32) * (1.0 - alpha)
                            + frame.astype(np.float32) * alpha
                        )
                        frame = np.clip(blended, 0, 255).astype(np.uint8)
                    if enable_atmosphere:
                        time_sec = global_frame_idx / out_fps
                        frame = _apply_story_atmosphere(frame, time_sec)
                    writer.append_data(frame)
                    global_frame_idx += 1
                prev_tail = tail_frames
        return output.read_bytes()


def assemble_scene_videos(clips, fps=FPS, width=WIDTH, height=HEIGHT):
    if not clips or len(clips) > MAX_SCENES:
        raise ValueError("A story must have between 1 and 20 scene videos")
    return assemble_scene_media([("video", clip) for clip in clips], fps=fps, width=width, height=height)
