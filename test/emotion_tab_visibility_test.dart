import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/psych_page.dart';
import 'package:fairytale_hyeonlim_merged/story_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('emotion results are shown in the psychology tab only', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final state = AppState();
    addTearDown(state.dispose);
    expect(
      await state.startTemporaryStory(genre: '판타지', age: '7', prompt: '모험'),
      isTrue,
    );
    final story = state.currentStory!;

    await tester.pumpWidget(ChangeNotifierProvider.value(
      value: state,
      child: MaterialApp(home: StoryPage(preloadedStory: story)),
    ));
    await tester.pumpAndSettle();
    expect(find.text('감정 그래프'), findsNothing);
    expect(find.textContaining('현재 감정'), findsNothing);
    expect(find.text('이야기 감정'), findsNothing);
    expect(find.text('선택한 감정'), findsNothing);

    await tester.pumpWidget(ChangeNotifierProvider.value(
      value: state,
      child: const MaterialApp(home: PsychPage()),
    ));
    await tester.pumpAndSettle();
    expect(find.text('감정 그래프'), findsNothing);
    expect(find.textContaining('엔딩을 본 뒤'), findsOneWidget);

    final selected = story.choiceOptions.first;
    story.chapters.add(StoryChapter(
      chapter: 2,
      text: '마침내 모험을 마쳤어요.',
      choiceMade: selected.text,
      selectedChoiceEmotion: selected.emotion,
    ));
    story.chapters.add(StoryChapter(
      chapter: 3,
      text: '또 다른 선택을 마쳤어요.',
      choiceMade: '조용히 기다린다',
      storyEmotion: selected.emotion,
    ));
    story.allChoicesMade = [selected.text, '조용히 기다린다'];
    story.choices = [];
    await tester.pumpWidget(ChangeNotifierProvider.value(
      value: state,
      child: const MaterialApp(home: PsychPage()),
    ));
    await tester.pumpAndSettle();
    expect(find.text('감정 그래프'), findsOneWidget);
    expect(find.text('선택 2개 중 분석 결과 1개'), findsOneWidget);
    expect(find.textContaining('실제 감정 분석 결과가 아니에요'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('saved results marked for review or abstention stay hidden', () {
    for (final flag in ['requires_review', 'abstained']) {
      final analysis = EmotionAnalysis.fromJson({
        'emotion_label_source': 'kote_checkpoint_v1',
        'emotion_scoring_enabled': true,
        flag: true,
        'primary_emotion': '기쁨',
        'top_emotions': [
          {'label_index': 42, 'label': '기쁨', 'score': 0.9},
        ],
      });
      expect(analysis.topEmotions, isEmpty);
      expect(analysis.displayLabel, isEmpty);
    }
  });

  testWidgets('psychology screen opened from a story can return', (tester) async {
    final state = AppState();
    addTearDown(state.dispose);
    await tester.pumpWidget(ChangeNotifierProvider.value(
      value: state,
      child: MaterialApp(
        home: Builder(builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => const PsychPage()),
            ),
            child: const Text('열기'),
          ),
        )),
      ),
    ));
    await tester.tap(find.text('열기'));
    await tester.pumpAndSettle();
    expect(find.byType(BackButton), findsOneWidget);
    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    expect(find.text('열기'), findsOneWidget);
  });
}
