class StoryVideoClip {
  final String id;
  final String assetPath;
  final String title;
  final String description;
  final List<String> keywords;
  final String characterKey;

  const StoryVideoClip({
    required this.id,
    required this.assetPath,
    required this.title,
    required this.description,
    required this.keywords,
    required this.characterKey,
  });
}

class StoryVideoCatalog {
  static const List<StoryVideoClip> clips = <StoryVideoClip>[
    StoryVideoClip(
      id: 'forest_door_adventure',
      assetPath: 'assets/story_videos/forest_door_adventure_15s.mp4',
      title: '\uc232\uc758 \ubb38\uacfc \ubcf4\ubb3c',
      description:
          '\ubb38\uc744 \uc5f4\uace0 \ub9c8\ubc95\uc758 \ubcf4\uc11d\uc744 \ubc1c\uacac\ud558\ub294 \uc7a5\uba74',
      characterKey: 'male_01',
      keywords: <String>[
        '\ubb38',
        '\uc5f4\uc5b4',
        '\ubcf4\uc11d',
        '\ub9c8\ubc95',
        '\uc7a0\uae08',
        'door',
        'gem',
        'treasure',
        'magic',
        'unlock',
      ],
    ),
    StoryVideoClip(
      id: 'lantern_path',
      assetPath: 'assets/story_videos/lantern_path_15s.mp4',
      title: '\ub4f1\ubd88\uc744 \ucc3e\uc544\uac00\ub294 \uae38',
      description:
          '\uae38\uc744 \uac78\uc73c\uba70 \uc9c0\ub3c4\ub97c \ucc3e\uace0 \ub4f1\ubd88\uc744 \ucf1c\ub294 \uc7a5\uba74',
      characterKey: 'male_01',
      keywords: <String>[
        '\ub4f1\ubd88',
        '\ube5b',
        '\uc9c0\ub3c4',
        '\uac77',
        '\uae38',
        '\ucc3e',
        '\uc5ec\ud589',
        '\ub5a0\ub098',
        'lantern',
        'light',
        'map',
        'walk',
        'travel',
      ],
    ),
    StoryVideoClip(
      id: 'hidden_treasure',
      assetPath: 'assets/story_videos/hidden_treasure_15s.mp4',
      title: '\uc228\uc740 \ubcf4\ubb3c',
      description:
          '\ub36e\uac1c\ub97c \uac77\uace0 \ub808\ubc84\ub97c \ub2f9\uae30\uba70 \ubcf4\ubb3c\uc0c1\uc790\ub97c \uc5ec\ub294 \uc7a5\uba74',
      characterKey: 'male_01',
      keywords: <String>[
        '\ubcf4\ubb3c',
        '\uc0c1\uc790',
        '\ub808\ubc84',
        '\ub36e\uac1c',
        '\uc8fc\uc6cc',
        '\uc5f4\uc1e0',
        '\ubc1c\uacac',
        '\uc5f4\ub2e4',
        'treasure',
        'chest',
        'lever',
        'pick',
        'discover',
      ],
    ),
    StoryVideoClip(
      id: 'bridge_to_castle',
      assetPath: 'assets/story_videos/bridge_to_castle_15s.mp4',
      title: '\uc131\uc73c\ub85c \uac00\ub294 \ub2e4\ub9ac',
      description:
          '\ub2e4\ub9ac\uc640 \uc7a5\uc560\ubb3c\uc744 \ud1b5\uacfc\ud574 \uc131\uc73c\ub85c \ud5a5\ud558\ub294 \uc7a5\uba74',
      characterKey: 'male_01',
      keywords: <String>[
        '\ub2e4\ub9ac',
        '\uac74\ub108',
        '\uc219\uc5ec',
        '\uac00\ub9ac',
        '\uc131\uc73c\ub85c',
        '\ud5a5\ud558',
        '\ub2ec\ub9ac',
        '\uc774\ub3d9',
        'bridge',
        'cross',
        'castle',
        'journey',
        'run',
      ],
    ),
  ];

  static StoryVideoClip? forChapter({
    required String text,
    String? choice,
    required int chapter,
    String? genre,
    required String? characterKey,
  }) {
    final normalizedCharacterKey = characterKey?.trim().toLowerCase() ?? '';
    if (normalizedCharacterKey.isEmpty) return null;
    final matchingClips = clips
        .where((clip) => clip.characterKey == normalizedCharacterKey)
        .toList(growable: false);
    if (matchingClips.isEmpty) return null;

    final source = '${choice ?? ''} $text'.toLowerCase();
    StoryVideoClip? best;
    var bestScore = 0;

    for (final clip in matchingClips) {
      var score = 0;
      for (final keyword in clip.keywords) {
        if (source.contains(keyword.toLowerCase())) {
          score += keyword.length >= 3 ? 3 : 2;
        }
      }
      if (score > bestScore) {
        best = clip;
        bestScore = score;
      }
    }

    return bestScore > 0 ? best : null;
  }
}
