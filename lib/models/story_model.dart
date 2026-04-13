class VocabWord {
  final String hard;
  final String easy;
  final String definition;

  VocabWord({required this.hard, required this.easy, required this.definition});

  factory VocabWord.fromJson(Map<String, dynamic> json) => VocabWord(
        hard: json['hard'] ?? '',
        easy: json['easy'] ?? '',
        definition: json['definition'] ?? '',
      );
}

class StoryChapter {
  final int chapter;
  final String text;
  final String? choiceMade;

  StoryChapter({required this.chapter, required this.text, this.choiceMade});
}

class StorySession {
  final String storyId;
  final String genre;
  final String age;
  final String initialPrompt;
  List<StoryChapter> chapters;
  List<String> choices;
  List<VocabWord> vocab;
  List<String> allChoicesMade;
  int currentChapter;

  StorySession({
    required this.storyId,
    required this.genre,
    required this.age,
    required this.initialPrompt,
    required this.chapters,
    required this.choices,
    required this.vocab,
    this.allChoicesMade = const [],
    this.currentChapter = 1,
  });

  String get fullStoryText =>
      chapters.map((c) => c.text).join('\n\n');
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
