class CharacterProfile {
  final String characterKey;
  final String name;
  final String gender;
  final String ageGroup;
  final String description;
  final List<String> roleTags;
  final String? imageUrl;
  final bool active;

  const CharacterProfile({
    required this.characterKey,
    required this.name,
    required this.gender,
    required this.ageGroup,
    required this.description,
    required this.roleTags,
    this.imageUrl,
    this.active = true,
  });

  factory CharacterProfile.fromJson(Map<String, dynamic> json) {
    final rawAssets = json['assets'] as List? ?? const [];
    final assets = rawAssets
        .whereType<Map>()
        .map(
          (asset) => asset.map(
            (key, value) => MapEntry(key.toString(), value),
          ),
        )
        .toList();
    final faceAsset = assets.firstWhere(
      (asset) =>
          asset['quality_tier'] == 'premium_reference' ||
          asset['pose'] == 'reference',
      orElse: () => assets.isEmpty ? const <String, dynamic>{} : assets.first,
    );

    return CharacterProfile(
      characterKey: json['character_key']?.toString().trim() ?? '',
      name: json['name']?.toString().trim() ?? '',
      gender: json['gender']?.toString().trim().toLowerCase() ?? '',
      ageGroup: json['age_group']?.toString().trim().toLowerCase() ?? '',
      description: json['description']?.toString().trim() ?? '',
      roleTags: (json['role_tags'] as List? ?? const [])
          .map((item) => item.toString().trim().toLowerCase())
          .where((item) => item.isNotEmpty)
          .toList(growable: false),
      imageUrl: _nonEmptyText(faceAsset['image_url'] ?? faceAsset['url']),
      active: json['active'] != false,
    );
  }

  CharacterProfile mergeRemote(CharacterProfile remote) {
    return CharacterProfile(
      characterKey: characterKey,
      name: remote.name.isEmpty ? name : remote.name,
      gender: remote.gender.isEmpty ? gender : remote.gender,
      ageGroup: remote.ageGroup.isEmpty ? ageGroup : remote.ageGroup,
      description:
          remote.description.isEmpty ? description : remote.description,
      roleTags: remote.roleTags.isEmpty ? roleTags : remote.roleTags,
      imageUrl: remote.imageUrl ?? imageUrl,
      active: remote.active,
    );
  }

  String? get localImageAsset =>
      CharacterProfileCatalog.isDefaultProfile(characterKey)
          ? 'assets/characters/${characterKey}_reference_v2.png'
          : null;

  String get displayName =>
      CharacterProfileCatalog.defaultNameFor(characterKey) ??
      (name.isEmpty ? characterKey : name);

  String get roleLabel {
    const labels = <String, String>{
      'hero': '주인공',
      'warrior': '용사',
      'explorer': '탐험가',
      'guardian': '수호자',
      'mage': '마법사',
      'guide': '안내자',
      'mentor': '멘토',
      'companion': '동료',
      'helper': '조력자',
      'fairy': '요정',
      'target': '구출 대상',
      'princess': '공주',
      'prince': '왕자',
      'antagonist': '적대자',
      'rival': '라이벌',
      'healer': '치유사',
      'archer': '궁수',
    };
    for (final role in roleTags) {
      final label = labels[role];
      if (label != null) return label;
    }
    return '동화 캐릭터';
  }

  static String? _nonEmptyText(dynamic value) {
    final text = value?.toString().trim() ?? '';
    return text.isEmpty ? null : text;
  }
}

class CharacterProfileCatalog {
  static const defaults = <CharacterProfile>[
    CharacterProfile(
      characterKey: 'male_01',
      name: '민호',
      gender: 'male',
      ageGroup: 'child',
      description: 'A brave young adventurer.',
      roleTags: ['hero', 'warrior'],
    ),
    CharacterProfile(
      characterKey: 'male_02',
      name: '준',
      gender: 'male',
      ageGroup: 'teen',
      description: 'A curious field explorer.',
      roleTags: ['hero', 'explorer', 'companion'],
    ),
    CharacterProfile(
      characterKey: 'male_03',
      name: '태산',
      gender: 'male',
      ageGroup: 'adult',
      description: 'A warm-hearted forest guardian.',
      roleTags: ['guardian', 'guide', 'warrior'],
    ),
    CharacterProfile(
      characterKey: 'male_04',
      name: '도윤',
      gender: 'male',
      ageGroup: 'elder',
      description: 'A map-carrying elder guide.',
      roleTags: ['guide', 'mentor'],
    ),
    CharacterProfile(
      characterKey: 'male_05',
      name: '보리',
      gender: 'male',
      ageGroup: 'child',
      description: 'A cheerful young helper.',
      roleTags: ['companion', 'helper'],
    ),
    CharacterProfile(
      characterKey: 'male_06',
      name: '레이븐',
      gender: 'male',
      ageGroup: 'young_adult',
      description: 'A mysterious royal rival.',
      roleTags: ['antagonist', 'rival'],
    ),
    CharacterProfile(
      characterKey: 'male_07',
      name: '이안',
      gender: 'male',
      ageGroup: 'child',
      description: 'A kind young prince.',
      roleTags: ['target', 'prince', 'companion'],
    ),
    CharacterProfile(
      characterKey: 'male_08',
      name: '하늘',
      gender: 'male',
      ageGroup: 'adult',
      description: 'A star-robed storyteller mage.',
      roleTags: ['mage', 'guide', 'healer'],
    ),
    CharacterProfile(
      characterKey: 'female_01',
      name: '미나',
      gender: 'female',
      ageGroup: 'child',
      description: 'A bright young magic hero.',
      roleTags: ['hero', 'mage'],
    ),
    CharacterProfile(
      characterKey: 'female_02',
      name: '하나',
      gender: 'female',
      ageGroup: 'child',
      description: 'A friendly nature helper.',
      roleTags: ['companion', 'helper'],
    ),
    CharacterProfile(
      characterKey: 'female_03',
      name: '미란',
      gender: 'female',
      ageGroup: 'teen',
      description: 'A royal keeper of a magic key.',
      roleTags: ['target', 'princess', 'healer'],
    ),
    CharacterProfile(
      characterKey: 'female_04',
      name: '루나',
      gender: 'female',
      ageGroup: 'young_adult',
      description: 'A wise forest fairy.',
      roleTags: ['companion', 'guide', 'fairy'],
    ),
    CharacterProfile(
      characterKey: 'female_05',
      name: '서연',
      gender: 'female',
      ageGroup: 'adult',
      description: 'A confident adventure detective.',
      roleTags: ['hero', 'explorer'],
    ),
    CharacterProfile(
      characterKey: 'female_06',
      name: '아린',
      gender: 'female',
      ageGroup: 'elder',
      description: 'A gentle healing mentor.',
      roleTags: ['guide', 'mentor', 'healer'],
    ),
    CharacterProfile(
      characterKey: 'female_07',
      name: '나라',
      gender: 'female',
      ageGroup: 'young_adult',
      description: 'A dark royal rival.',
      roleTags: ['antagonist', 'rival'],
    ),
    CharacterProfile(
      characterKey: 'female_08',
      name: '솔',
      gender: 'female',
      ageGroup: 'teen',
      description: 'A nature-loving young archer.',
      roleTags: ['guardian', 'companion', 'archer'],
    ),
  ];

  static bool isDefaultProfile(String characterKey) =>
      defaults.any((profile) => profile.characterKey == characterKey);

  static String? defaultNameFor(String characterKey) {
    for (final profile in defaults) {
      if (profile.characterKey == characterKey) return profile.name;
    }
    return null;
  }

  static CharacterProfile? findByKey(String characterKey) {
    for (final profile in defaults) {
      if (profile.characterKey == characterKey) return profile;
    }
    return null;
  }

  static List<CharacterProfile> mergeRemoteProfiles(
    List<CharacterProfile> remoteProfiles,
  ) {
    final remoteByKey = {
      for (final profile in remoteProfiles) profile.characterKey: profile,
    };
    final merged = defaults
        .map(
          (fallback) => remoteByKey[fallback.characterKey] == null
              ? fallback
              : fallback.mergeRemote(remoteByKey[fallback.characterKey]!),
        )
        .where((profile) => profile.active)
        .toList();
    merged.addAll(
      remoteProfiles.where(
        (profile) =>
            profile.active &&
            !defaults.any(
              (fallback) => fallback.characterKey == profile.characterKey,
            ),
      ),
    );
    return merged;
  }
}
