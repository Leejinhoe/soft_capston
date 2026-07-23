import 'dart:convert';

import 'package:flutter/services.dart';

import '../models/story_model.dart';

/// Loads the elementary vocabulary workbook that is bundled with the app.
///
/// Only words that actually occur in a story are passed to the story UI, so
/// the full dictionary is not rendered or saved automatically.
class VocabularyCatalog {
  static const String _assetPath =
      'assets/vocabulary/elementary_vocabulary.json';

  static Future<List<VocabWord>>? _loading;

  static Future<List<VocabWord>> findMatches(
    String text, {
    required String sourceStoryTitle,
  }) async {
    if (text.trim().isEmpty) return const [];

    final catalog = await (_loading ??= _load());
    final matches = catalog
        // One-syllable entries create many false positives inside longer
        // Korean words, so they remain bundled but are not auto-highlighted.
        .where((word) => word.hard.length >= 2 && text.contains(word.hard))
        .map(
          (word) => word.copyWith(sourceStoryTitle: sourceStoryTitle),
        )
        .toList();

    matches.sort((a, b) => b.hard.length.compareTo(a.hard.length));
    return matches;
  }

  static Future<List<VocabWord>> _load() async {
    final raw = await rootBundle.loadString(_assetPath);
    final entries = jsonDecode(raw) as List<dynamic>;
    return entries
        .whereType<Map<String, dynamic>>()
        .map(
          (entry) {
            final definition = entry['definition']?.toString().trim() ?? '';
            return VocabWord(
              hard: entry['word']?.toString().trim() ?? '',
              // The source sheet has one official definition rather than a
              // separate easy synonym. Keeping it in both fields preserves
              // the existing word-book and quiz data model.
              easy: definition,
              definition: definition,
            );
          },
        )
        .where((word) => word.hard.isNotEmpty && word.definition.isNotEmpty)
        .toList(growable: false);
  }
}
