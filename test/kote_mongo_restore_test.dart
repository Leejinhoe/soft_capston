import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';

void main() {
  const path = String.fromEnvironment('KOTE_E2E_REPORT');
  test(
    'actual MongoDB response restores selected emotion and pending choices',
    () {
      final report =
          jsonDecode(File(path).readAsStringSync()) as Map<String, dynamic>;
      expect(report['passed'], true);
      final story = StorySession.fromDatabaseJson(
        Map<String, dynamic>.from(report['restored_story'] as Map),
      );
      expect(story.chapters.length, 2);
      expect(story.chapters.last.choiceMade, report['selected_choice']);
      expect(story.chapters.last.selectedChoiceEmotion?.displayLabel, '공포/무서움');
      expect(story.choiceEmotionHistory.single.emotion?.displayLabel, '공포/무서움');
      expect(story.choices, ['친구에게 정말 고맙다고 말한다.']);
      expect(story.choiceOptions.single.emotion?.topEmotions, isNotEmpty);
      expect(story.runtimeState, 'test_state_2');
      expect(story.storyId, startsWith('fixture_'));
    },
    skip: path.isEmpty
        ? 'Pass a newly generated real-Mongo report using KOTE_E2E_REPORT'
        : false,
  );
}
