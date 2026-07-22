class VocabWord {
  final String? id;
  final String? userId;
  final String? originStoryId;
  final String? sourceStoryTitle;
  final String hard;
  final String easy;
  final String definition;
  final DateTime? createdAt;

  VocabWord({
    this.id,
    this.userId,
    this.originStoryId,
    this.sourceStoryTitle,
    required this.hard,
    required this.easy,
    required this.definition,
    this.createdAt,
  });

  factory VocabWord.fromJson(Map<String, dynamic> json) {
    final meaning = json['definition'] ?? json['meaning'] ?? '';
    return VocabWord(
      id: json['id']?.toString(),
      userId: json['user_id']?.toString(),
      originStoryId: json['origin_story_id']?.toString(),
      sourceStoryTitle:
          json['source_story_title']?.toString() ??
          json['origin_story_title']?.toString(),
      hard: json['hard']?.toString() ?? json['word']?.toString() ?? '',
      easy: json['easy']?.toString() ?? meaning.toString(),
      definition: meaning.toString(),
      createdAt:
          DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.tryParse(json['saved_at']?.toString() ?? ''),
    );
  }

  VocabWord copyWith({
    String? id,
    String? userId,
    String? originStoryId,
    String? sourceStoryTitle,
    String? hard,
    String? easy,
    String? definition,
    DateTime? createdAt,
  }) {
    return VocabWord(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      originStoryId: originStoryId ?? this.originStoryId,
      sourceStoryTitle: sourceStoryTitle ?? this.sourceStoryTitle,
      hard: hard ?? this.hard,
      easy: easy ?? this.easy,
      definition: definition ?? this.definition,
      createdAt: createdAt ?? this.createdAt,
    );
  }
}

class EmotionScoreItem {
  final int labelIndex;
  final String label;
  final String labelDisplay;
  final double score;

  EmotionScoreItem({
    required this.labelIndex,
    required this.label,
    required this.labelDisplay,
    required this.score,
  });

  factory EmotionScoreItem.fromJson(Map<String, dynamic> json) {
    return EmotionScoreItem(
      labelIndex: (json['label_index'] as num?)?.toInt() ?? -1,
      label: json['label']?.toString() ?? '',
      labelDisplay: json['label_display']?.toString() ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0,
    );
  }
}

class EmotionAnalysis {
  final String emotionLabelSource;
  final bool emotionLabelsAreGeneric;
  final int? primaryEmotionIndex;
  final String primaryEmotion;
  final String primaryEmotionDisplay;
  final double primaryScore;
  final List<EmotionScoreItem> topEmotions;
  final List<EmotionScoreItem> activeEmotions;
  final Map<String, double> scores;
  final Map<int, double> scoresByIndex;

  EmotionAnalysis({
    required this.emotionLabelSource,
    required this.emotionLabelsAreGeneric,
    required this.primaryEmotionIndex,
    required this.primaryEmotion,
    required this.primaryEmotionDisplay,
    required this.primaryScore,
    required this.topEmotions,
    required this.activeEmotions,
    required this.scores,
    required this.scoresByIndex,
  });

  factory EmotionAnalysis.fromJson(Map<String, dynamic> json) {
    final rawScores = (json['scores'] as Map<String, dynamic>? ?? {});
    final rawScoresByIndex =
        (json['scores_by_index'] as Map<String, dynamic>? ?? {});

    return EmotionAnalysis(
      emotionLabelSource: json['emotion_label_source']?.toString() ?? '',
      emotionLabelsAreGeneric:
          json['emotion_labels_are_generic'] as bool? ?? false,
      primaryEmotionIndex: (json['primary_emotion_index'] as num?)?.toInt(),
      primaryEmotion: json['primary_emotion']?.toString() ?? '',
      primaryEmotionDisplay: json['primary_emotion_display']?.toString() ?? '',
      primaryScore: (json['primary_score'] as num?)?.toDouble() ?? 0,
      topEmotions: (json['top_emotions'] as List? ?? [])
          .map((e) => EmotionScoreItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      activeEmotions: (json['active_emotions'] as List? ?? [])
          .map((e) => EmotionScoreItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      scores: rawScores.map((k, v) => MapEntry(k, (v as num).toDouble())),
      scoresByIndex: rawScoresByIndex.map(
        (k, v) => MapEntry(int.tryParse(k) ?? -1, (v as num).toDouble()),
      ),
    );
  }
}

class ChoiceOption {
  final String text;
  final EmotionAnalysis? emotion;

  ChoiceOption({required this.text, this.emotion});
}

class SceneMediaResult {
  final String? imageUrl;
  final String? videoUrl;
  final String? provider;
  final double? elapsedSeconds;
  final bool saved;
  final String? jobId;
  final String? status;
  final String? statusUrl;

  const SceneMediaResult({
    this.imageUrl,
    this.videoUrl,
    this.provider,
    this.elapsedSeconds,
    this.saved = false,
    this.jobId,
    this.status,
    this.statusUrl,
  });

  bool get hasMedia =>
      (imageUrl?.trim().isNotEmpty ?? false) ||
      (videoUrl?.trim().isNotEmpty ?? false);

  factory SceneMediaResult.fromJson(Map<String, dynamic> json) {
    final rawResult = json['result'];
    final result = rawResult is Map
        ? Map<String, dynamic>.from(rawResult)
        : <String, dynamic>{};
    String? readString(String key) {
      final nestedValue = result[key];
      if (nestedValue != null) return nestedValue.toString();

      final topLevelValue = json[key];
      if (topLevelValue != null) return topLevelValue.toString();

      return null;
    }

    bool readBool(String key, {bool fallback = false}) {
      final nestedValue = result[key];
      if (nestedValue is bool) return nestedValue;

      final topLevelValue = json[key];
      if (topLevelValue is bool) return topLevelValue;

      return fallback;
    }

    double? readDouble(String key) {
      final nestedValue = result[key];
      if (nestedValue is num) return nestedValue.toDouble();

      final topLevelValue = json[key];
      if (topLevelValue is num) return topLevelValue.toDouble();

      return null;
    }

    return SceneMediaResult(
      imageUrl: readString('image_url'),
      videoUrl: readString('video_url'),
      provider: readString('provider'),
      elapsedSeconds: readDouble('elapsed_seconds'),
      saved: readBool('saved'),
      jobId: readString('job_id'),
      status: readString('status'),
      statusUrl: readString('status_url'),
    );
  }
}

class StoryChapter {
  final int chapter;
  final String text;
  final String? choiceMade;
  String? imageUrl;
  String? videoUrl;
  final DateTime? createdAt;
  String? imageB64;
  EmotionAnalysis? storyEmotion;
  EmotionAnalysis? selectedChoiceEmotion;

  StoryChapter({
    required this.chapter,
    required this.text,
    this.choiceMade,
    this.imageUrl,
    this.videoUrl,
    this.createdAt,
    this.imageB64,
    this.storyEmotion,
    this.selectedChoiceEmotion,
  });
}

class StorySession {
  String storyId;
  String? dbStoryId;
  String genre;
  String age;
  String initialPrompt;
  List<StoryChapter> chapters;
  List<String> choices;
  List<ChoiceOption> choiceOptions;
  List<VocabWord> candidateVocab;
  List<VocabWord> vocab;
  List<String> allChoicesMade;
  int currentChapter;
  final DateTime? createdAt;
  final Set<String> syncedVocabKeys;
  final Set<int> syncedChapterNumbers;
  final Set<int> mediaGenerationChapterNumbers;

  StorySession({
    required this.storyId,
    this.dbStoryId,
    required this.genre,
    required this.age,
    required this.initialPrompt,
    required this.chapters,
    required this.choices,
    required this.choiceOptions,
    this.candidateVocab = const [],
    required this.vocab,
    this.allChoicesMade = const [],
    this.currentChapter = 1,
    this.createdAt,
    Set<String>? syncedVocabKeys,
    Set<int>? syncedChapterNumbers,
    Set<int>? mediaGenerationChapterNumbers,
  }) : syncedVocabKeys = syncedVocabKeys ?? <String>{},
       syncedChapterNumbers = syncedChapterNumbers ?? <int>{},
       mediaGenerationChapterNumbers = mediaGenerationChapterNumbers ?? <int>{};

  String get fullStoryText => chapters.map((c) => c.text).join('\n\n');

  EmotionAnalysis? emotionForChoice(String choice) {
    for (final option in choiceOptions) {
      if (option.text == choice) return option.emotion;
    }
    return null;
  }

  factory StorySession.fromDatabaseJson(Map<String, dynamic> json) {
    final dbStoryId = json['id']?.toString();
    final rawScenes = json['scenes'] as List? ?? const [];
    final chapters = rawScenes
        .whereType<Map<String, dynamic>>()
        .map(
          (scene) => StoryChapter(
            chapter: (scene['step_number'] as num?)?.toInt() ?? 1,
            text:
                scene['story_text']?.toString() ??
                scene['content']?.toString() ??
                '',
            choiceMade:
                scene['choice_made']?.toString() ??
                scene['user_choice']?.toString(),
            imageUrl: scene['image_url']?.toString(),
            videoUrl: scene['video_url']?.toString(),
            createdAt: DateTime.tryParse(scene['created_at']?.toString() ?? ''),
          ),
        )
        .where((chapter) => chapter.text.trim().isNotEmpty)
        .toList();

    final rawVocab = json['vocab'] as List? ?? const [];
    final vocab = rawVocab
        .whereType<Map<String, dynamic>>()
        .map(VocabWord.fromJson)
        .where((word) => word.hard.trim().isNotEmpty)
        .toList();

    final choicesMade = chapters
        .map((chapter) => chapter.choiceMade?.trim())
        .whereType<String>()
        .where((choice) => choice.isNotEmpty)
        .toList();

    final syncedKeys = vocab
        .map((word) => '${word.hard}|${word.easy}|${word.definition}')
        .toSet();
    final syncedChapterNumbers = chapters
        .map((chapter) => chapter.chapter)
        .toSet();
    final mediaGenerationChapterNumbers = chapters
        .where(
          (chapter) =>
              (chapter.imageUrl?.trim().isNotEmpty ?? false) ||
              (chapter.videoUrl?.trim().isNotEmpty ?? false),
        )
        .map((chapter) => chapter.chapter)
        .toSet();

    return StorySession(
      storyId: dbStoryId == null || dbStoryId.isEmpty
          ? 'db_${DateTime.now().microsecondsSinceEpoch}'
          : 'db_$dbStoryId',
      dbStoryId: dbStoryId,
      genre: json['genre']?.toString() ?? '동화',
      age: json['age']?.toString() ?? json['target_age']?.toString() ?? '',
      initialPrompt: json['title']?.toString().trim().isNotEmpty == true
          ? json['title'].toString()
          : json['prompt']?.toString() ?? '제목 없는 동화',
      chapters: chapters,
      choices: const [],
      choiceOptions: const [],
      candidateVocab: const [],
      vocab: vocab,
      allChoicesMade: choicesMade,
      currentChapter: chapters.fold<int>(
        0,
        (max, chapter) => chapter.chapter > max ? chapter.chapter : max,
      ),
      createdAt: DateTime.tryParse(json['created_at']?.toString() ?? ''),
      syncedVocabKeys: syncedKeys,
      syncedChapterNumbers: syncedChapterNumbers,
      mediaGenerationChapterNumbers: mediaGenerationChapterNumbers,
    );
  }
}

class PsychResult {
  final String type;
  final String description;
  final Map<String, int> traits;

  PsychResult({
    required this.type,
    required this.description,
    required this.traits,
  });

  factory PsychResult.fromJson(Map<String, dynamic> json) {
    final rawTraits = json['traits'] as Map<String, dynamic>? ?? {};
    return PsychResult(
      type: json['type'] ?? '탐험가',
      description: json['description'] ?? '',
      traits: rawTraits.map((k, v) => MapEntry(k, (v as num).toInt())),
    );
  }
}

class CommunityComment {
  final String id;
  final String authorName;
  final String? authorAccountId;
  final String content;
  final DateTime createdAt;

  CommunityComment({
    required this.id,
    required this.authorName,
    required this.content,
    required this.createdAt,
    this.authorAccountId,
  });

  factory CommunityComment.fromJson(Map<String, dynamic> json) {
    return CommunityComment(
      id: json['id']?.toString() ?? '',
      authorName: json['author_name']?.toString() ?? '동화 친구',
      authorAccountId: json['author_account_id']?.toString(),
      content: json['content']?.toString() ?? '',
      createdAt:
          DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.now(),
    );
  }
}

class CommunityPost {
  final String id;
  final String authorName;
  final String? authorAccountId;
  final String genre;
  final String title;
  final String preview;
  final String fullText;
  final String storyEmoji;
  final DateTime createdAt;
  final int viewCount;
  final int likeCount;
  final List<String> likedBy;
  final List<CommunityComment> comments;

  CommunityPost({
    required this.id,
    required this.authorName,
    required this.genre,
    required this.title,
    required this.preview,
    required this.fullText,
    required this.storyEmoji,
    required this.createdAt,
    required this.viewCount,
    required this.likeCount,
    this.likedBy = const [],
    required this.comments,
    this.authorAccountId,
  });

  int get commentCount => comments.length;

  bool isLikedBy(String? accountId) {
    final normalized = accountId?.trim();
    if (normalized == null || normalized.isEmpty) return false;
    return likedBy.contains(normalized);
  }

  factory CommunityPost.fromJson(Map<String, dynamic> json) {
    final rawComments = json['comments'] as List? ?? const [];
    final rawLikedBy = json['liked_by'] as List? ?? const [];
    return CommunityPost(
      id: json['id']?.toString() ?? '',
      authorName: json['author_name']?.toString() ?? '동화 친구',
      authorAccountId: json['author_account_id']?.toString(),
      genre: json['genre']?.toString() ?? '동화',
      title: json['title']?.toString() ?? '제목 없는 동화',
      preview: json['preview']?.toString() ?? '',
      fullText: json['full_text']?.toString() ?? '',
      storyEmoji: json['story_emoji']?.toString() ?? '📖',
      createdAt:
          DateTime.tryParse(json['created_at']?.toString() ?? '') ??
          DateTime.now(),
      viewCount: (json['view_count'] as num?)?.toInt() ?? 0,
      likeCount: (json['like_count'] as num?)?.toInt() ?? 0,
      likedBy: rawLikedBy.map((item) => item.toString()).toList(),
      comments: rawComments
          .map((e) => CommunityComment.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
