class CharacterReadiness {
  final String characterKey;
  final String name;
  final int assetCount;
  final int targetAssetCount;
  final bool ready;

  const CharacterReadiness({
    required this.characterKey,
    required this.name,
    required this.assetCount,
    required this.targetAssetCount,
    required this.ready,
  });

  factory CharacterReadiness.fromJson(Map<String, dynamic> json) {
    return CharacterReadiness(
      characterKey: json['character_key']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      assetCount: (json['asset_count'] as num?)?.toInt() ?? 0,
      targetAssetCount: (json['target_asset_count'] as num?)?.toInt() ?? 0,
      ready: json['ready'] == true,
    );
  }
}

class MediaQueueStatus {
  final int pending;
  final int running;
  final int completed;
  final int failed;

  const MediaQueueStatus({
    required this.pending,
    required this.running,
    required this.completed,
    required this.failed,
  });

  factory MediaQueueStatus.fromJson(Map<String, dynamic> json) {
    return MediaQueueStatus(
      pending: (json['pending'] as num?)?.toInt() ?? 0,
      running: (json['running'] as num?)?.toInt() ?? 0,
      completed: (json['completed'] as num?)?.toInt() ?? 0,
      failed: (json['failed'] as num?)?.toInt() ?? 0,
    );
  }
}

class MediaReadiness {
  final int progressPercent;
  final int readyProfiles;
  final int targetProfiles;
  final int readyAssets;
  final int targetAssets;
  final bool workerRunning;
  final List<CharacterReadiness> characters;
  final MediaQueueStatus queue;

  const MediaReadiness({
    required this.progressPercent,
    required this.readyProfiles,
    required this.targetProfiles,
    required this.readyAssets,
    required this.targetAssets,
    required this.workerRunning,
    required this.characters,
    required this.queue,
  });

  factory MediaReadiness.fromJson(Map<String, dynamic> json) {
    final profiles = json['profiles'] as Map<String, dynamic>? ?? const {};
    final assets = json['assets'] as Map<String, dynamic>? ?? const {};
    final worker = json['worker'] as Map<String, dynamic>? ?? const {};
    final characterItems = json['characters'] as List<dynamic>? ?? const [];

    return MediaReadiness(
      progressPercent: (json['progress_percent'] as num?)?.round() ?? 0,
      readyProfiles: (profiles['ready'] as num?)?.toInt() ?? 0,
      targetProfiles: (profiles['target'] as num?)?.toInt() ?? 0,
      readyAssets: (assets['ready'] as num?)?.toInt() ?? 0,
      targetAssets: (assets['target'] as num?)?.toInt() ?? 0,
      workerRunning: worker['running'] == true,
      characters: characterItems
          .whereType<Map<String, dynamic>>()
          .map(CharacterReadiness.fromJson)
          .toList(),
      queue: MediaQueueStatus.fromJson(
        json['queue'] as Map<String, dynamic>? ?? const {},
      ),
    );
  }
}
