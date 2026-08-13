"""Build a 100-word canonical motion-sheet and video pack.

Existing authored motion sheets are copied into one canonical round100 pack.
Missing words use the existing male_01 action art as a stable character base
and add a restrained, action-specific prop or scene anchor. The same renderer
then produces an 8-second H.264 preview for every canonical word.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = ROOT / "assets" / "characters" / "motion_sheets"
ROUND_ROOT = ASSET_ROOT / "generated_round100"
OUTPUT_ROOT = ROOT / "output" / "video_final" / "generated_round100"
CATALOG_PATH = ROOT / "tools" / "next_actions" / "round100_catalog.json"

CHARACTER = "male_01"
SHEET_SIZE = (448, 512)
SHEET_COLUMNS = 4
SHEET_ROWS = 2
FPS = 30
DURATION_SECONDS = 8.0
FRAME_COUNT = 240
VIDEO_SIZE = (960, 480)
GROUND_Y = 430

BACKGROUND_BY_GROUP = {
    "01_posture": ROOT / "assets" / "backgrounds" / "nature_pond_wide_v2.png",
    "02_travel": ROOT / "assets" / "backgrounds" / "adventure_ruins_wide_v2.png",
    "03_objects": ROOT / "assets" / "backgrounds" / "fantasy_castle_wide_v2.png",
    "04_social": ROOT / "assets" / "backgrounds" / "friendship_square_wide_v2.png",
    "05_magic_senses": ROOT / "assets" / "backgrounds" / "mystery_library_wide_v2.png",
}

BASE_MOTION = ASSET_ROOT / "male_01_motion_sheet_v3.png"
BASE_ACTION = ASSET_ROOT / "male_01_action_sheet_v21.png"


def action(
    key: str,
    ko: str,
    group: str,
    anchor: str,
    *,
    solo: bool = True,
    needs: Iterable[str] = (),
    tier: str = "generated_prototype",
) -> dict[str, Any]:
    return {
        "key": key,
        "ko": ko,
        "group": group,
        "anchor": anchor,
        "solo": solo,
        "needs": list(needs),
        "tier": tier,
    }


SPECS = [
    # 01: posture and readable character states
    action("stand", "서다", "01_posture", "stable feet and upright torso", tier="existing"),
    action("sit", "앉다", "01_posture", "bent knees and grounded seat", tier="existing"),
    action("kneel", "무릎 꿇다", "01_posture", "one or both knees touch the ground", tier="existing"),
    action("bow", "고개 숙이다", "01_posture", "upper body bends forward then recovers", tier="existing"),
    action("crouch", "웅크리다", "01_posture", "low center of gravity with bent knees", tier="existing"),
    action("stretch", "기지개 켜다", "01_posture", "arms extend overhead and torso lengthens", tier="existing"),
    action("prone", "엎드리다", "01_posture", "body settles flat on the ground", tier="existing"),
    action("wake", "잠에서 깨다", "01_posture", "eyes and torso rise from rest", tier="existing"),
    action("yawn", "하품하다", "01_posture", "mouth opens and arms lift in a slow stretch", tier="existing"),
    action("sneeze", "재채기하다", "01_posture", "short forward recoil and recovery", tier="existing"),
    action("stagger", "비틀거리다", "01_posture", "weight shifts unevenly before balance returns", tier="existing"),
    action("salute", "경례하다", "01_posture", "hand reaches the forehead and holds", tier="existing"),
    action("clap", "박수치다", "01_posture", "hands meet twice in front of the chest", tier="existing"),
    action("dance", "춤추다", "01_posture", "rhythmic side step with arms moving", tier="existing"),
    action("nod", "고개 끄덕이다", "01_posture", "small repeated head nod", tier="existing"),
    action("smile", "웃다", "01_posture", "open friendly expression"),
    # 02: travel and terrain
    action("journey", "여행하다", "02_travel", "steady forward path", tier="existing"),
    action("walk", "걷다", "02_travel", "alternating feet and gentle arm swing", tier="existing"),
    action("run", "달리다", "02_travel", "alternating stride toward a destination", tier="existing"),
    action("jump", "뛰어오르다", "02_travel", "knees compress then both feet leave the ground", tier="existing"),
    action("crawl", "기어가다", "02_travel", "hands and knees move through a low route", tier="existing"),
    action("climb", "기어오르다", "02_travel", "hands and feet rise against a vertical surface", tier="existing"),
    action("slide", "미끄러지다", "02_travel", "body lowers and travels along the ground", tier="existing"),
    action("hide", "숨다", "02_travel", "body moves behind a visible cover", tier="existing"),
    action("fall_roll", "굴러 넘어지다", "02_travel", "controlled fall becomes a side roll", tier="existing"),
    action("cross_bridge", "다리를 건너다", "02_travel", "feet follow a bridge toward the far side", tier="existing"),
    action("squeeze_through", "비집고 지나가다", "02_travel", "shoulders turn through a narrow gap", tier="existing"),
    action("duck_under", "몸을 숙여 지나가다", "02_travel", "head and torso pass below an obstacle", tier="existing"),
    action("wade", "물살을 헤치며 걷다", "02_travel", "upright steps through shallow water", tier="existing"),
    action("row", "노를 젓다", "02_travel", "oar pulls through water with a boat anchor", tier="existing"),
    action("weave_through", "누비다", "02_travel", "side-to-side path between fixed trees", needs=("trees", "clear destination")),
    action("swim", "헤엄치다", "02_travel", "horizontal body and alternating arm strokes", needs=("water", "far bank")),
    action("vault_over", "타넘다", "02_travel", "hands touch a low wall as legs pass over", needs=("low wall",)),
    action("clamber_over", "기어넘다", "02_travel", "hands and boots alternate over rubble", needs=("low rubble",)),
    action("dive", "잠수하다", "02_travel", "head-first entry through a visible water surface", needs=("water surface",)),
    action("stop", "멈추다", "02_travel", "forward motion settles into a planted stance", tier="existing"),
    # 03: object and environment interactions
    action("investigate", "조사하다", "03_objects", "body leans toward a clue", tier="existing"),
    action("open_chest", "보물상자를 열다", "03_objects", "lid rises and treasure remains visible", tier="existing"),
    action("unlock", "잠금을 풀다", "03_objects", "key turns and latch releases", tier="existing"),
    action("pick_up", "줍다", "03_objects", "hand lowers then lifts a visible object", tier="existing"),
    action("lift", "들어 올리다", "03_objects", "object rises from waist to chest", tier="existing"),
    action("uncover", "덮개를 걷다", "03_objects", "cover moves aside to reveal a target", tier="existing"),
    action("pull_lever", "레버를 당기다", "03_objects", "hand pulls a lever to its end stop", tier="existing"),
    action("turn_dial", "다이얼을 돌리다", "03_objects", "fingers rotate a marked dial", tier="existing"),
    action("place_gem", "보석을 놓다", "03_objects", "gem settles into a matching socket", tier="existing"),
    action("press_seal", "봉인을 누르다", "03_objects", "palm presses a seal and holds", tier="existing"),
    action("light_lantern", "등불을 켜다", "03_objects", "flame appears after a clear lighting gesture", tier="existing"),
    action("plant_flag", "깃발을 꽂다", "03_objects", "flagpole enters a marked ground anchor", needs=("flag", "ground anchor")),
    action("put_on_crown", "왕관을 쓰다", "03_objects", "crown moves from chest height to the head", needs=("crown",)),
    action("touch_probe", "만져보다", "03_objects", "fingertips briefly touch a surface", needs=("rune wall",)),
    action("stack_stones", "돌을 쌓다", "03_objects", "multiple stones remain in a stable stack", needs=("stones", "flat ground")),
    action("hang_sign", "표지판을 걸다", "03_objects", "sign loop catches on a visible hook", needs=("sign", "hook")),
    action("tie_string", "끈을 묶다", "03_objects", "crossed rope ends tighten into a knot", needs=("rope", "post")),
    action("sweep_floor", "바닥을 쓸다", "03_objects", "broom stays on floor while leaves gather", needs=("broom", "leaves")),
    action("knock", "두드리다", "03_objects", "knuckles tap a door three times", needs=("door",)),
    action("push", "밀다", "03_objects", "hands drive a heavy object forward", needs=("door", "crate")),
    action("pull_rope", "밧줄을 당기다", "03_objects", "rope tightens as body leans back", needs=("rope",)),
    action("dig", "파다", "03_objects", "tool breaks the soil and a small hole remains", needs=("spade", "soil")),
    action("read_map", "지도를 읽다", "03_objects", "map opens and gaze tracks a route", needs=("map",)),
    action("write", "쓰다", "03_objects", "hand moves a quill across a page", needs=("paper", "quill")),
    action("open_door", "문을 열다", "03_objects", "hand turns handle and door swings open", needs=("door",)),
    # 04: social and reactions
    action("wave", "손을 흔들다", "04_social", "open hand makes a friendly side-to-side gesture", tier="existing"),
    action("point", "가리키다", "04_social", "finger and gaze stay locked on a target", tier="existing"),
    action("beckon", "손짓해 부르다", "04_social", "palm curls toward a partner", tier="existing", solo=False, needs=("partner",)),
    action("shake_hands", "악수하다", "04_social", "two hands meet and make a short agreement shake", tier="existing", solo=False, needs=("partner",)),
    action("protect", "지키다", "04_social", "body steps between danger and a partner", tier="existing", solo=False, needs=("partner", "danger")),
    action("catch", "받아내다", "04_social", "arms receive a falling or moving target", tier="existing", solo=False, needs=("target",)),
    action("release", "놓아주다", "04_social", "hands open and target moves free", tier="existing", solo=False, needs=("target",)),
    action("cower", "움츠리다", "04_social", "shoulders close around the face in fear", tier="existing"),
    action("hesitate", "망설이다", "04_social", "hand reaches then returns between two choices", tier="existing"),
    action("eavesdrop", "엿듣다", "04_social", "ear leans toward a door while body stays hidden", tier="existing", needs=("door",)),
    action("spot", "발견하다", "04_social", "eyes find a distant clue and body turns", tier="existing"),
    action("gasp", "깜짝 놀라 숨을 들이쉬다", "04_social", "hands rise as mouth opens in surprise", tier="existing"),
    action("present_gift", "선물하다", "04_social", "large gift passes from giver to receiver", solo=False, needs=("partner", "gift")),
    action("shoulder_link", "어깨동무하다", "04_social", "arm rests around a partner shoulder", solo=False, needs=("partner",)),
    action("apologize", "사과하다", "04_social", "clear bow followed by a waiting posture", solo=False, needs=("partner",)),
    action("warn", "경고하다", "04_social", "open palm stops an approaching partner", solo=False, needs=("partner", "danger")),
    action("flinch", "움찔하다", "04_social", "brief shoulder jolt followed by a cautious look", needs=("sudden cue",)),
    action("nod_confirm", "끄덕이다", "04_social", "two deliberate nods after reading a clue", needs=("clue",)),
    action("talk", "이야기하다", "04_social", "facing partner with measured hand gesture", solo=False, needs=("partner",), tier="existing"),
    action("rescue", "구하다", "04_social", "arm reaches toward a partner and pulls them clear", solo=False, needs=("partner", "danger"), tier="existing"),
    # 05: magic, senses, and story props
    action("magic", "마법을 쓰다", "05_magic_senses", "raised hand and controlled magical glow", tier="existing"),
    action("battle", "싸우다", "05_magic_senses", "guarded stance and clear defensive strike", solo=False, needs=("opponent",), tier="existing"),
    action("throw", "던지다", "05_magic_senses", "arm winds up then releases a visible object", needs=("object",)),
    action("dodge", "피하다", "05_magic_senses", "torso shifts away from a visible threat", needs=("threat",)),
    action("block", "막다", "05_magic_senses", "arms form a guard between body and threat", needs=("threat",)),
    action("shoot_bow", "활을 쏘다", "05_magic_senses", "bow draws, aims, and releases an arrow", needs=("bow", "target")),
    action("heal", "치유하다", "05_magic_senses", "hands hover over a wound as warm light settles", needs=("partner", "wound")),
    action("ring_bell", "종을 울리다", "05_magic_senses", "rope pulls a bell and the clapper swings", needs=("bell",)),
    action("close_door", "문을 닫다", "05_magic_senses", "door swings shut and latch remains visible", needs=("door",)),
    action("drink_potion", "물약을 마시다", "05_magic_senses", "bottle reaches mouth then lowers", needs=("potion",)),
    action("eat", "먹다", "05_magic_senses", "food reaches mouth and hand returns", needs=("food",)),
    action("carry", "나르다", "05_magic_senses", "both arms support a visible crate", needs=("crate",)),
    action("read_book", "책을 읽다", "05_magic_senses", "book opens and gaze follows its pages", needs=("book",)),
    action("draw", "그리다", "05_magic_senses", "charcoal hand traces a visible line", needs=("paper", "charcoal")),
    action("listen", "귀 기울이다", "05_magic_senses", "hand cups ear while head turns toward sound", needs=("sound cue",)),
    action("smell", "냄새 맡다", "05_magic_senses", "object rises near nose and character pauses", needs=("flower", "potion")),
    action("feed_dragon", "용에게 먹이를 주다", "05_magic_senses", "food reaches a friendly dragon mouth", solo=False, needs=("dragon", "food")),
    action("sprinkle_fairy_dust", "요정 가루를 뿌리다", "05_magic_senses", "hand scatters visible dust over a target", needs=("dust", "target")),
    action("look_into_mirror", "마법 거울을 들여다보다", "05_magic_senses", "face leans toward a framed mirror", needs=("mirror",)),
]


SOURCE_MAP: dict[str, Path] = {
    "stand": ASSET_ROOT / "male_01_stand_cycle_v1.png",
    "sit": ASSET_ROOT / "male_01_sit_cycle_v1.png",
    "kneel": ASSET_ROOT / "generated_v2" / "team_a_posture" / "male_01_kneel_cycle_v2.png",
    "bow": ASSET_ROOT / "generated_v2" / "team_a_posture" / "male_01_bow_cycle_v2.png",
    "crouch": ASSET_ROOT / "generated_v2" / "team_a_posture" / "male_01_crouch_cycle_v2.png",
    "stretch": ASSET_ROOT / "generated_v2" / "team_a_posture" / "male_01_stretch_cycle_v2.png",
    "clap": ASSET_ROOT / "generated_v2" / "team_b_gestures" / "male_01_clap_cycle_v2.png",
    "point": ASSET_ROOT / "generated_v2" / "team_b_gestures" / "male_01_point_cycle_v2.png",
    "nod": ASSET_ROOT / "generated_v2" / "team_b_gestures" / "male_01_nod_cycle_v2.png",
    "dance": ASSET_ROOT / "generated_v2" / "team_b_gestures" / "male_01_dance_cycle_v2.png",
    "crawl": ASSET_ROOT / "generated_v2" / "team_c_scene_actions" / "male_01_crawl_motion_sheet_v2.png",
    "climb": ASSET_ROOT / "generated_v2" / "team_c_scene_actions" / "male_01_climb_motion_sheet_v2.png",
    "slide": ASSET_ROOT / "generated_v2" / "team_c_scene_actions" / "male_01_slide_motion_sheet_v2.png",
    "hide": ASSET_ROOT / "generated_v2" / "team_c_scene_actions" / "male_01_hide_motion_sheet_v2.png",
    "fall_roll": ASSET_ROOT / "generated_v2" / "team_c_scene_actions" / "male_01_fall_roll_motion_sheet_v2.png",
    "salute": ASSET_ROOT / "generated_round3" / "male_01_salute_cycle_round3.png",
    "prone": ASSET_ROOT / "generated_round3" / "male_01_prone_cycle_round3.png",
    "stagger": ASSET_ROOT / "generated_round3" / "male_01_stagger_cycle_round3.png",
    "wake": ASSET_ROOT / "generated_round3" / "male_01_wake_cycle_round3.png",
    "yawn": ASSET_ROOT / "generated_round3" / "male_01_yawn_cycle_round3.png",
    "sneeze": ASSET_ROOT / "generated_round3" / "male_01_sneeze_cycle_round3.png",
    "journey": ASSET_ROOT / "male_01_target_journey_sheet_v4.png",
    "walk": ASSET_ROOT / "male_01_motion_sheet_v3.png",
    "run": ASSET_ROOT / "male_01_run_cycle_v16.png",
    "jump": ASSET_ROOT / "male_01_jump_cycle_v19.png",
    "battle": ASSET_ROOT / "male_01_battle_cycle_v22.png",
    "magic": ASSET_ROOT / "male_01_magic_cycle_v22.png",
    "rescue": ASSET_ROOT / "male_01_interaction_cycle_v22.png",
    "open_chest": ASSET_ROOT / "generated_round4" / "agent_01_prop_interactions" / "male_01_open_chest_cycle_round4.png",
    "unlock": ASSET_ROOT / "generated_round4" / "agent_01_prop_interactions" / "male_01_unlock_cycle_round4.png",
    "pick_up": ASSET_ROOT / "generated_round4" / "agent_01_prop_interactions" / "male_01_pick_up_cycle_round4.png",
    "lift": ASSET_ROOT / "generated_round4" / "agent_01_prop_interactions" / "male_01_lift_cycle_round4.png",
    "uncover": ASSET_ROOT / "generated_round4" / "agent_01_prop_interactions" / "male_01_uncover_cycle_round4.png",
    "cross_bridge": ASSET_ROOT / "generated_round4" / "agent_02_terrain_traversal" / "male_01_cross_bridge_cycle_round4.png",
    "squeeze_through": ASSET_ROOT / "generated_round4" / "agent_02_terrain_traversal" / "male_01_squeeze_through_cycle_round4.png",
    "duck_under": ASSET_ROOT / "generated_round4" / "agent_02_terrain_traversal" / "male_01_duck_under_cycle_round4.png",
    "wade": ASSET_ROOT / "generated_round4" / "agent_02_terrain_traversal" / "male_01_wade_cycle_round4.png",
    "row": ASSET_ROOT / "generated_round4" / "agent_02_terrain_traversal" / "male_01_row_cycle_round4.png",
    "shake_hands": ASSET_ROOT / "generated_round4" / "agent_03_social_rescue" / "male_01_shake_hands_cycle_round4.png",
    "beckon": ASSET_ROOT / "generated_round4" / "agent_03_social_rescue" / "male_01_beckon_cycle_round4.png",
    "protect": ASSET_ROOT / "generated_round4" / "agent_03_social_rescue" / "male_01_protect_cycle_round4.png",
    "catch": ASSET_ROOT / "generated_round4" / "agent_03_social_rescue" / "male_01_catch_cycle_round4.png",
    "release": ASSET_ROOT / "generated_round4" / "agent_03_social_rescue" / "male_01_release_cycle_round4.png",
    "cower": ASSET_ROOT / "generated_round4" / "agent_04_reactions_observation" / "male_01_cower_cycle_round4.png",
    "hesitate": ASSET_ROOT / "generated_round4" / "agent_04_reactions_observation" / "male_01_hesitate_cycle_round4.png",
    "eavesdrop": ASSET_ROOT / "generated_round4" / "agent_04_reactions_observation" / "male_01_eavesdrop_cycle_round4.png",
    "spot": ASSET_ROOT / "generated_round4" / "agent_04_reactions_observation" / "male_01_spot_cycle_round4.png",
    "gasp": ASSET_ROOT / "generated_round4" / "agent_04_reactions_observation" / "male_01_gasp_cycle_round4.png",
    "pull_lever": ASSET_ROOT / "generated_round4" / "agent_05_fantasy_devices" / "male_01_pull_lever_cycle_round4.png",
    "turn_dial": ASSET_ROOT / "generated_round4" / "agent_05_fantasy_devices" / "male_01_turn_dial_cycle_round4.png",
    "place_gem": ASSET_ROOT / "generated_round4" / "agent_05_fantasy_devices" / "male_01_place_gem_cycle_round4.png",
    "press_seal": ASSET_ROOT / "generated_round4" / "agent_05_fantasy_devices" / "male_01_press_seal_cycle_round4.png",
    "light_lantern": ASSET_ROOT / "generated_round4" / "agent_05_fantasy_devices" / "male_01_light_lantern_cycle_round4.png",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="only build the first N words")
    parser.add_argument("--only", nargs="*", default=[], help="build only these keys")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--no-video", action="store_true")
    return parser.parse_args()


def font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def extract_source_cells(path: Path) -> list[Image.Image]:
    with Image.open(path) as source:
        sheet = source.convert("RGBA")
        result: list[Image.Image] = []
        for index in range(SHEET_COLUMNS * SHEET_ROWS):
            column = index % SHEET_COLUMNS
            row = index // SHEET_COLUMNS
            left = round(column * sheet.width / SHEET_COLUMNS)
            right = round((column + 1) * sheet.width / SHEET_COLUMNS)
            top = round(row * sheet.height / SHEET_ROWS)
            bottom = round((row + 1) * sheet.height / SHEET_ROWS)
            result.append(sheet.crop((left, top, right, bottom)).convert("RGBA"))
        return result


def make_base_sequence(key: str, base_cells: list[Image.Image]) -> list[Image.Image]:
    if key in {"run", "walk", "journey", "weave_through", "swim", "clamber_over"}:
        indexes = [0, 1, 2, 3, 2, 1, 3, 0]
    elif key in {"jump", "dodge", "vault_over", "fall_roll", "battle", "shoot_bow"}:
        indexes = [0, 1, 3, 5, 6, 3, 1, 0]
    elif key in {"magic", "heal", "sprinkle_fairy_dust", "light_lantern"}:
        indexes = [0, 4, 4, 6, 4, 6, 7, 0]
    else:
        indexes = [0, 7, 0, 7, 6, 7, 0, 0]
    return [base_cells[index % len(base_cells)].copy() for index in indexes]


def line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], fill: str, width: int = 6) -> None:
    draw.line(points, fill=fill, width=width, joint="curve")


def draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, fill: str) -> None:
    points: list[tuple[int, int]] = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        value = radius if index % 2 == 0 else radius // 2
        points.append((round(cx + math.cos(angle) * value), round(cy + math.sin(angle) * value)))
    draw.polygon(points, fill=fill, outline="#fff4a8")


def draw_overlay(key: str, stage: int) -> Image.Image:
    layer = Image.new("RGBA", SHEET_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    t = stage / 7.0
    gold = "#e3b34b"
    brown = "#6b3e24"
    blue = "#55a9d8"
    red = "#cf4f51"
    green = "#5f9b68"
    pale = "#f9e5a7"

    if key == "plant_flag":
        x = 330 - round(28 * t)
        line(draw, [(x, 440), (x, 158)], brown, 8)
        draw.polygon([(x, 160), (x + 82, 182), (x, 218)], fill=red, outline="#7a2830")
        draw.ellipse((x - 13, 430, x + 13, 456), fill="#7b5a37")
    elif key == "put_on_crown":
        y = 164 - round(52 * t)
        draw.polygon([(176, y + 30), (188, y - 8), (207, y + 15), (229, y - 14), (248, y + 15), (267, y - 4), (276, y + 30)], fill=gold, outline="#8a5e19")
        draw.line((176, y + 30, 276, y + 30), fill="#fff0a2", width=7)
    elif key in {"touch_probe", "look_into_mirror"}:
        x0 = 326
        draw.rounded_rectangle((x0, 142, 428, 363), radius=16, fill="#6c8ba3", outline="#d4eef5", width=7)
        if key == "look_into_mirror":
            draw.ellipse((x0 + 18, 168, 408, 338), fill="#9fd7e8", outline="#fff3bf", width=5)
            draw.ellipse((x0 + 126, 204, x0 + 176, 255), fill="#f5c5a0", outline="#2a2933", width=3)
        else:
            for dy in range(3):
                line(draw, [(350, 205 + dy * 36), (395, 225 + dy * 36)], "#dcecf2", 5)
    elif key == "stack_stones":
        count = min(4, 1 + round(t * 3))
        for index in range(count):
            y = 444 - index * 38
            draw.ellipse((320 - index * 4, y - 24, 408 + index * 4, y + 12), fill="#777d85", outline="#424854", width=4)
    elif key == "hang_sign":
        line(draw, [(300, 116), (442, 116)], brown, 10)
        y = 155 + round(42 * (1 - t))
        draw.rectangle((328, y, 430, y + 70), fill="#c48a48", outline="#5e3b25", width=5)
        line(draw, [(342, 116), (342, y)], gold, 4)
        draw.polygon([(342, y - 6), (350, y + 5), (334, y + 5)], fill=gold)
    elif key == "tie_string":
        line(draw, [(380, 180), (380, 442)], brown, 9)
        line(draw, [(302, 304), (345, 270), (395, 305), (345, 340), (302, 304)], pale, 5)
        draw.ellipse((335, 288, 356, 310), outline=gold, width=5)
    elif key == "sweep_floor":
        start_x = 184 + round(56 * math.sin(t * math.pi))
        line(draw, [(start_x, 228), (370, 437)], brown, 11)
        draw.line((344, 425, 411, 425), fill="#b67a42", width=10)
        for dx in range(0, 60, 12):
            draw.line((350 + dx, 425, 344 + dx, 448), fill="#d6ae66", width=4)
        draw.ellipse((395, 430, 432, 448), fill="#d7a74d")
    elif key in {"knock", "open_door", "close_door"}:
        x = 332
        open_amount = t if key == "open_door" else (1 - t if key == "close_door" else 0)
        draw.rectangle((x, 112, 438, 443), fill="#68452e", outline="#d4a665", width=7)
        if open_amount > 0.05:
            draw.polygon([(x, 112), (x - round(92 * open_amount), 145), (x - round(92 * open_amount), 420), (x, 443)], fill="#936341", outline="#e1ad6a")
        draw.ellipse((x + 20, 276, x + 42, 298), fill=gold)
    elif key in {"push", "carry"}:
        x = 328 + round(42 * t if key == "push" else 0)
        draw.rounded_rectangle((x, 292, x + 108, 420), radius=10, fill="#bd7b48", outline="#5f3924", width=6)
        line(draw, [(x + 20, 320), (x + 88, 320)], "#e8be70", 5)
        line(draw, [(x + 20, 370), (x + 88, 370)], "#e8be70", 5)
    elif key in {"pull_rope", "ring_bell"}:
        if key == "pull_rope":
            line(draw, [(404, 126), (404, 440)], brown, 7)
            line(draw, [(404, 250), (316 - round(34 * t), 306)], pale, 7)
        else:
            line(draw, [(382, 120), (382, 268)], brown, 7)
            draw.ellipse((342, 244, 422, 330), fill=gold, outline="#8a5e19", width=6)
            line(draw, [(382, 286), (382, 334)], brown, 6)
    elif key == "dig":
        line(draw, [(354, 210), (280, 420)], brown, 12)
        line(draw, [(270, 420), (340, 420)], "#a9b2bc", 10)
        draw.arc((340, 406, 432, 455), 180, 350, fill="#8b663f", width=12)
    elif key in {"read_map", "read_book", "write", "draw"}:
        box = (308, 282, 436, 414)
        draw.rounded_rectangle(box, radius=8, fill="#f3e3b0", outline="#8c6c3b", width=5)
        line(draw, [(330, 318), (412, 318)], "#bb7c61", 4)
        line(draw, [(330, 349), (398, 349)], "#bb7c61", 4)
        if key == "read_map":
            line(draw, [(330, 382), (374, 360), (410, 388)], green, 5)
        elif key in {"write", "draw"}:
            line(draw, [(318, 280), (364, 336)], brown, 7)
    elif key in {"present_gift", "eat", "drink_potion", "feed_dragon"}:
        x = 342
        if key == "present_gift":
            draw.rectangle((x, 302, x + 88, 392), fill="#db5b66", outline="#7a2939", width=6)
            line(draw, [(x + 44, 302), (x + 44, 392)], gold, 6)
            line(draw, [(x, 348), (x + 88, 348)], gold, 6)
        elif key == "drink_potion":
            draw.polygon([(x + 25, 266), (x + 65, 266), (x + 77, 380), (x + 14, 380)], fill="#79c6d1", outline="#3a6f79")
            draw.rectangle((x + 29, 247, x + 61, 276), fill="#b9d6db", outline="#3a6f79")
        elif key == "feed_dragon":
            draw.ellipse((x, 222, x + 120, 354), fill="#6d9e77", outline="#335b42", width=6)
            draw.ellipse((x + 54, 280, x + 98, 319), fill="#263538")
            draw.polygon([(x + 20, 246), (x - 10, 216), (x + 48, 240)], fill="#6d9e77", outline="#335b42")
            draw.ellipse((x + 88, 254, x + 101, 267), fill="#f2dc6f")
        else:
            draw.ellipse((x + 12, 288, x + 88, 364), fill="#d57b49", outline="#6f3928", width=5)
            draw.line((x + 24, 302, x + 50, 276), fill="#5b833f", width=6)
    elif key in {"magic", "heal", "sprinkle_fairy_dust", "light_lantern"}:
        for offset in (-36, 0, 38):
            draw_star(draw, 360 + offset, 235 + round(18 * math.sin(t * math.pi + offset)), 16 if key != "sprinkle_fairy_dust" else 11, pale)
        if key == "light_lantern":
            draw.rounded_rectangle((350, 300, 420, 410), radius=12, fill="#e1a84f", outline="#75421f", width=6)
            draw.ellipse((369, 322, 401, 369), fill="#fff2a1")
    elif key in {"throw", "dodge", "block", "shoot_bow", "battle"}:
        if key in {"shoot_bow", "battle"}:
            line(draw, [(310, 264), (408, 206)], brown, 7)
            line(draw, [(310, 264), (408, 322)], brown, 7)
            line(draw, [(310, 264), (430, 264)], pale, 4)
        else:
            draw.ellipse((370 + round(42 * t), 210, 400 + round(42 * t), 240), fill="#e5b85a", outline="#754d28")
    elif key in {"listen", "smell", "look_up", "look_down", "flinch", "nod_confirm", "point", "wave"}:
        for i in range(3):
            if key == "listen":
                draw.arc((352 - i * 14, 188 - i * 8, 414 + i * 14, 252 + i * 8), 210, 330, fill=blue, width=4)
            elif key == "smell":
                draw.arc((360, 210 - i * 15, 420, 260 + i * 12), 120, 240, fill=green, width=4)
        if key == "point":
            draw_star(draw, 404, 216, 14, pale)
        if key == "wave":
            line(draw, [(362, 166), (409, 128)], blue, 4)
    elif key in {"close_door", "open_door"}:
        pass
    else:
        # A small story anchor keeps a generated action visually grounded even
        # when it is primarily a body or facial movement.
        draw.ellipse((365, 364, 414, 413), fill="#8fb9c2", outline="#406b73", width=4)

    return layer


def generated_sheet(spec: dict[str, Any]) -> Image.Image:
    source = BASE_ACTION if spec["key"] in {"battle", "magic", "jump", "shoot_bow"} else BASE_MOTION
    base_cells = extract_source_cells(source)
    cells = make_base_sequence(spec["key"], base_cells)
    sheet = Image.new("RGBA", (SHEET_SIZE[0] * SHEET_COLUMNS, SHEET_SIZE[1] * SHEET_ROWS), (0, 0, 0, 0))
    for index, cell in enumerate(cells):
        composed = Image.alpha_composite(cell.resize(SHEET_SIZE, Image.Resampling.LANCZOS), draw_overlay(spec["key"], index))
        x = (index % SHEET_COLUMNS) * SHEET_SIZE[0]
        y = (index // SHEET_COLUMNS) * SHEET_SIZE[1]
        sheet.alpha_composite(composed, (x, y))
    return sheet


def fit_background(path: Path) -> Image.Image:
    with Image.open(path) as source:
        source = source.convert("RGB")
        scale = max(VIDEO_SIZE[0] / source.width, VIDEO_SIZE[1] / source.height)
        resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
        left = max(0, (resized.width - VIDEO_SIZE[0]) // 2)
        top = max(0, (resized.height - VIDEO_SIZE[1]) // 2)
        return resized.crop((left, top, left + VIDEO_SIZE[0], top + VIDEO_SIZE[1])).convert("RGBA")


def extract_cells(path: Path) -> list[Image.Image]:
    with Image.open(path) as source:
        sheet = source.convert("RGBA")
        result: list[Image.Image] = []
        for index in range(8):
            column = index % 4
            row = index // 4
            cell = sheet.crop((column * sheet.width // 4, row * sheet.height // 2, (column + 1) * sheet.width // 4, (row + 1) * sheet.height // 2))
            bbox = cell.getchannel("A").getbbox()
            result.append(cell.crop(bbox) if bbox else cell)
        return result


def fit_pose(cell: Image.Image, target_height: int = 370) -> Image.Image:
    cell = cell.convert("RGBA")
    scale = target_height / max(1, cell.height)
    return cell.resize((max(1, round(cell.width * scale)), target_height), Image.Resampling.LANCZOS)


def aligned_canvas(image: Image.Image, width: int, height: int) -> Image.Image:
    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.alpha_composite(image, ((width - image.width) // 2, height - image.height))
    return result


def alpha_blend(first: Image.Image, second: Image.Image, amount: float) -> Image.Image:
    width = max(first.width, second.width)
    height = max(first.height, second.height)
    first_array = np.asarray(aligned_canvas(first, width, height), dtype=np.float32) / 255.0
    second_array = np.asarray(aligned_canvas(second, width, height), dtype=np.float32) / 255.0
    amount = amount * amount * (3.0 - 2.0 * amount)
    first_alpha = first_array[..., 3:4]
    second_alpha = second_array[..., 3:4]
    first_array[..., :3] *= first_alpha
    second_array[..., :3] *= second_alpha
    rgb = first_array[..., :3] * (1 - amount) + second_array[..., :3] * amount
    alpha = first_alpha * (1 - amount) + second_alpha * amount
    rgb = np.divide(rgb, np.maximum(alpha, 1e-6), out=np.zeros_like(rgb), where=alpha > 1e-6)
    return Image.fromarray(np.clip(np.concatenate((rgb, alpha), axis=-1) * 255, 0, 255).astype(np.uint8), "RGBA")


def pose_at(cells: list[Image.Image], progress: float) -> Image.Image:
    value = min(max(progress, 0.0), 1.0) * 7
    first = min(6, int(math.floor(value)))
    return alpha_blend(cells[first], cells[first + 1], value - first)


def render_video(spec: dict[str, Any], sheet_path: Path, output_path: Path, background: Image.Image) -> dict[str, Any]:
    cells = [fit_pose(cell) for cell in extract_cells(sheet_path)]
    moving = spec["group"] == "02_travel" and spec["key"] not in {"stop", "row", "wade", "dive"}
    with imageio.get_writer(str(output_path), fps=FPS, codec="libx264", quality=7, ffmpeg_log_level="error", output_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]) as writer:
        for frame_index in range(FRAME_COUNT):
            progress = frame_index / max(1, FRAME_COUNT - 1)
            frame = background.copy()
            pose = pose_at(cells, progress)
            x = round(130 + 540 * progress) if moving else round(480 + 8 * math.sin(progress * math.pi * 2))
            y = GROUND_Y - pose.height
            shadow = Image.new("RGBA", VIDEO_SIZE, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow, "RGBA")
            shadow_draw.ellipse((x - 86, GROUND_Y - 8, x + 86, GROUND_Y + 12), fill=(25, 30, 40, 85))
            frame.alpha_composite(shadow)
            frame.alpha_composite(pose, (x - pose.width // 2, y))
            writer.append_data(np.asarray(frame.convert("RGB")))
    return {"path": str(output_path), "frames": FRAME_COUNT, "fps": FPS, "size": list(VIDEO_SIZE), "duration_seconds": DURATION_SECONDS, "codec": "H.264/libx264"}


def learning_semantics(spec: dict[str, Any]) -> dict[str, Any]:
    partner_terms = {"partner", "opponent"}
    environmental_terms = {"danger", "threat", "target", "wound", "sudden cue", "clue", "sound cue"}
    requires_partner = not bool(spec["solo"]) or any(item in partner_terms for item in spec["needs"])
    requires_object = any(item not in partner_terms and item not in environmental_terms for item in spec["needs"])
    if spec["group"] == "02_travel":
        motion_mode = "journey"
    elif spec["group"] == "01_posture":
        motion_mode = "stationary"
    elif requires_partner:
        motion_mode = "partner_interaction"
    elif requires_object:
        motion_mode = "object_interaction"
    else:
        motion_mode = "gesture_or_reaction"
    return {
        "vocabulary_key": spec["key"],
        "word": spec["ko"],
        "participant_count": 2 if requires_partner else 1,
        "requires_partner": requires_partner,
        "requires_object": requires_object,
        "motion_mode": motion_mode,
        "visual_anchor": spec["anchor"],
        "needs": spec["needs"],
        "learning_status": "catalogued_for_visual_vocabulary",
    }


def build_overview(group: str, records: list[dict[str, Any]], output_dir: Path) -> None:
    entries = [item for item in records if item["group"] == group]
    tile_w, tile_h, label_h = 240, 135, 28
    columns = 4
    rows = math.ceil(len(entries) / columns)
    canvas = Image.new("RGB", (columns * tile_w, rows * (tile_h + label_h)), "#f3f5f7")
    draw = ImageDraw.Draw(canvas)
    for index, record in enumerate(entries):
        row, column = divmod(index, columns)
        video = Path(record["video_path"])
        reader = imageio.get_reader(str(video))
        frame = Image.fromarray(reader.get_data(min(FRAME_COUNT - 1, FRAME_COUNT // 2))).convert("RGB")
        reader.close()
        frame.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (tile_w, tile_h), "black")
        tile.paste(frame, ((tile_w - frame.width) // 2, (tile_h - frame.height) // 2))
        x, y = column * tile_w, row * (tile_h + label_h)
        canvas.paste(tile, (x, y))
        draw.text((x + 5, y + tile_h + 6), record["key"], fill="#20242b", font=font(14))
    overview_dir = output_dir / group
    overview_dir.mkdir(parents=True, exist_ok=True)
    canvas.save(overview_dir / "group_overview.png", "PNG", optimize=True)


def build_pack(args: argparse.Namespace) -> dict[str, Any]:
    if len(SPECS) != 100:
        raise AssertionError(f"Expected exactly 100 specs, found {len(SPECS)}")
    keys = [item["key"] for item in SPECS]
    if len(set(keys)) != len(keys):
        raise AssertionError("Duplicate canonical word key")

    selected = SPECS
    if args.only:
        requested = set(args.only)
        selected = [item for item in SPECS if item["key"] in requested]
    if args.limit:
        selected = selected[: args.limit]

    ROUND_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    backgrounds = {group: fit_background(path) for group, path in BACKGROUND_BY_GROUP.items() if path.is_file()}
    base_cells = extract_source_cells(BASE_MOTION)
    records: list[dict[str, Any]] = []

    for index, spec in enumerate(selected, start=1):
        group_dir = ROUND_ROOT / spec["group"]
        output_dir = OUTPUT_ROOT / spec["group"]
        group_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        sheet_path = group_dir / f"{CHARACTER}_{spec['key']}_motion_sheet_round100.png"
        video_path = output_dir / f"{CHARACTER}_{spec['key']}_round100.mp4"
        source_path = SOURCE_MAP.get(spec["key"])
        source_kind = "existing" if source_path and source_path.is_file() else "generated_composite"

        if not (args.skip_existing and sheet_path.is_file()):
            if source_kind == "existing":
                shutil.copy2(source_path, sheet_path)
            else:
                sheet = generated_sheet(spec)
                sheet.save(sheet_path, "PNG", optimize=True)

        video_info: dict[str, Any] | None = None
        if not args.no_video and not (args.skip_existing and video_path.is_file()):
            background = backgrounds.get(spec["group"])
            if background is None:
                raise FileNotFoundError(f"No background available for {spec['group']}")
            video_info = render_video(spec, sheet_path, video_path, background)
        elif video_path.is_file():
            video_info = {"path": str(video_path), "frames": FRAME_COUNT, "fps": FPS, "size": list(VIDEO_SIZE), "duration_seconds": DURATION_SECONDS, "codec": "H.264/libx264"}

        record = {
            **spec,
            "learning": learning_semantics(spec),
            "index": index,
            "asset_kind": source_kind,
            "motion_sheet_path": str(sheet_path),
            "video_path": str(video_path),
            "video": video_info,
        }
        records.append(record)
        print(f"[{index:03d}/{len(selected):03d}] {spec['key']} asset={source_kind} video={'yes' if video_info else 'no'}", flush=True)

    manifest = {
        "manifest_version": "round100-v1",
        "status": "generated",
        "target_word_count": 100,
        "built_word_count": len(records),
        "character": CHARACTER,
        "phase_contract": ["prepare", "act", "hold", "recover"],
        "format": {"width": VIDEO_SIZE[0], "height": VIDEO_SIZE[1], "fps": FPS, "duration_seconds": DURATION_SECONDS, "frame_count": FRAME_COUNT, "codec": "H.264/libx264"},
        "records": records,
    }
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for group in BACKGROUND_BY_GROUP:
        if any(item["group"] == group for item in records) and all(Path(item["video_path"]).is_file() for item in records if item["group"] == group):
            build_overview(group, records, OUTPUT_ROOT)
    return manifest


def main() -> None:
    manifest = build_pack(parse_args())
    print(json.dumps({"built_word_count": manifest["built_word_count"], "catalog": str(CATALOG_PATH), "output_root": str(OUTPUT_ROOT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
