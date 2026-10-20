"""Landscape backgrounds with conservative, normalized ground routes.

Routes stop before steps, doors and other obstacles. They are layout hints,
not a guarantee of collision-free animation at every character scale.
"""

PACK = [
    ('fantasy_woodland_cottage', ['fantasy', 'nature'], ['숲속 오두막', '오두막 입구', 'woodland cottage'], [(0.46, .93), (.50, .80), (.58, .66), (.56, .55)]),
    ('adventure_stone_bridge', ['adventure', 'nature'], ['돌다리', 'stone bridge'], [(.48, .93), (.51, .78), (.53, .65), (.54, .52)]),
    ('friendship_village_square', ['friendship'], ['마을 광장', '분수대', 'village square'], [(.48, .93), (.39, .79), (.28, .65), (.25, .55)]),
    ('fantasy_castle_gate', ['fantasy', 'adventure'], ['성문', 'castle gate'], [(.50, .93), (.50, .78), (.50, .62), (.50, .49)]),
    ('mystery_grand_library', ['mystery', 'fantasy'], ['도서관 내부', '도서관 안', '서가', 'library interior'], [(.50, .93), (.50, .80), (.50, .68), (.50, .58)]),
    ('fantasy_crystal_arch', ['fantasy', 'adventure'], ['수정 아치', '수정 동굴 입구', 'crystal arch'], [(.49, .93), (.49, .80), (.48, .68), (.48, .57)]),
    ('nature_lakeside_pavilion', ['nature', 'friendship'], ['호숫가', '호수 정자', 'lakeside'], [(.46, .80), (.57, .65), (.70, .55), (.79, .47)]),
    ('nature_snowy_shelter', ['nature', 'adventure'], ['눈 덮인 숲', '겨울 쉼터', 'snowy shelter'], [(.47, .93), (.47, .76), (.49, .59), (.59, .40)]),
]

STORY_BACKGROUND_ASSETS = [
    {
        'key': key, 'genres': genres,
        'filename': key + '_wide_v1.png',
        'video_filename': key + '_wide_v1.png',
        'scene_keywords': keywords, 'visual_tags': [],
        'video_source': 'landscape_asset',
        'min_aspect_ratio': 1.5,
        'requires_scene_match': True,
        'keyword_weight': 4,
    }
    for key, genres, keywords, route in PACK
]

STORY_BACKGROUND_ROUTES = {key: tuple(route) for key, _, _, route in PACK}


def prefers_rear_journey(motion_plan):
    if str(motion_plan.get('directionality') or '').lower() in {'right_to_left', 'reverse'}:
        return False
    route = STORY_BACKGROUND_ROUTES.get(str(motion_plan.get('background_key') or ''))
    if not route:
        return False
    dx = abs(route[-1][0] - route[0][0])
    depth = route[0][1] - route[-1][1]
    return depth > 0 and dx < depth * .6

# Approximate ground-plane vanishing lines measured in each original image.
# These affect character perspective, not camera cropping or route geometry.
STORY_BACKGROUND_HORIZONS = {
    'fantasy_woodland_cottage': .32,
    'adventure_stone_bridge': .24,
    'friendship_village_square': .28,
    'fantasy_castle_gate': .27,
    'mystery_grand_library': .34,
    'fantasy_crystal_arch': .28,
    'nature_lakeside_pavilion': .22,
    'nature_snowy_shelter': .20,
}
