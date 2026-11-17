import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/psych_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

class _TestAppState extends AppState {
  StorySession? requestedStory;
  bool requestedForceRegenerate = false;
  StorySession? loadedEmotionStory;
  StorySession? requestedPsychStory;
  StorySession? restoredPsychStory;
  bool showPsychResult = false;

  @override
  Future<void> loadUserData() async {}

  @override
  Future<void> loadStoryEmotionAnalysis(StorySession story) async {
    loadedEmotionStory = story;
    notifyListeners();
  }

  @override
  Future<void> loadCumulativeEmotionSummary() async {
    cumulativeEmotionSummary = {
      'total_stories': 3,
      'analyzed_stories': 2,
      'decisions': 4,
      'averages': {'행복': 0.3, '중립': 0.2, '슬픔': 0.1},
    };
    notifyListeners();
  }

  @override
  Future<void> analyzeStoryAndHistory(
    StorySession story, {
    bool forceRegenerate = false,
  }) async {
    requestedStory = story;
    requestedForceRegenerate = forceRegenerate;
  }

  @override
  Future<void> restoreSavedPsychAnalysis(StorySession story) async {
    restoredPsychStory = story;
  }

  @override
  Future<void> loadPsychAnalysis({StorySession? selectedStory}) async {
    requestedPsychStory = selectedStory;
  }

  @override
  Map<String, dynamic>? emotionReportFor(StorySession story) =>
      identical(loadedEmotionStory, story)
      ? {
          'model': 'test classifier',
          'items': [
            {
              'step': 1,
              'status': 'classified',
              'label': '행복',
              'scores': {'행복': 0.7, '중립': 0.2, '슬픔': 0.1},
            },
          ],
        }
      : null;

  @override
  PsychResult? psychResultFor(StorySession story) => showPsychResult
      ? PsychResult(
          type: '선택 관찰',
          description: '저장된 해설을 표시합니다.',
          traits: const {},
        )
      : null;
}

class _TemporaryAnalysisAppState extends AppState {
  StorySession? loadedEmotionStory;
  StorySession? requestedPsychStory;

  @override
  Future<void> loadStoryEmotionAnalysis(StorySession story) async {
    loadedEmotionStory = story;
    notifyListeners();
  }

  @override
  Map<String, dynamic>? emotionReportFor(StorySession story) =>
      identical(loadedEmotionStory, story)
      ? {
          'model': 'test classifier',
          'items': [
            {
              'step': 1,
              'status': 'classified',
              'label': '행복',
              'scores': {'행복': 0.7},
            },
          ],
        }
      : null;

  @override
  Future<void> loadPsychAnalysis({StorySession? selectedStory}) async {
    requestedPsychStory = selectedStory;
  }

  @override
  Future<void> loadCumulativeEmotionSummary() async {}
}

void main() {
  testWidgets('shows trained-model scores and provides a back action', (
    tester,
  ) async {
    final state = _TestAppState()
      ..currentUserId = 'user-1'
      ..currentStory = StorySession(
        storyId: 'ai-1',
        dbStoryId: 'db-1',
        genre: '모험',
        age: '',
        initialPrompt: '동화',
        chapters: [
          StoryChapter(chapter: 8, text: '이야기 끝', choiceMade: '친구를 돕는다'),
        ],
        choices: [],
        choiceOptions: [],
        vocab: [],
        allChoicesMade: ['친구를 돕는다'],
        currentChapter: 8,
      );
    var backPressed = false;
    await tester.pumpWidget(
      ChangeNotifierProvider<AppState>.value(
        value: state,
        child: MaterialApp(home: PsychPage(onBack: () => backPressed = true)),
      ),
    );
    await tester.pump();
    expect(find.text('분석할 동화를 선택하세요'), findsOneWidget);
    await tester.tap(find.byKey(const Key('psych-story-db:db-1')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
    expect(state.loadedEmotionStory, same(state.currentStory));
    expect(state.restoredPsychStory, same(state.currentStory));
    expect(find.text('이번 동화의 감정 그래프'), findsOneWidget);
    expect(find.text('test classifier'), findsOneWidget);
    expect(find.byKey(const Key('story-emotion-radar')), findsOneWidget);
    expect(find.byKey(const Key('psych-analysis-panel')), findsOneWidget);
    await tester.ensureVisible(
      find.byKey(const Key('cumulative-emotion-disclosure')),
    );
    await tester.tap(find.byKey(const Key('cumulative-emotion-disclosure')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('cumulative-emotion-panel')), findsOneWidget);
    expect(find.byKey(const Key('cumulative-emotion-radar')), findsOneWidget);
    expect(find.byType(CustomPaint), findsAtLeastNWidgets(2));
    expect(find.textContaining('진단하지 않아요'), findsOneWidget);
    await tester.tap(find.byKey(const Key('psych-back')));
    await tester.pump();
    expect(find.text('분석할 동화를 선택하세요'), findsOneWidget);
    await tester.tap(find.byKey(const Key('psych-back')));
    expect(backPressed, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  testWidgets('서재에서 지정한 동화로 분류와 해설을 함께 요청한다', (tester) async {
    StorySession story(String id) => StorySession(
      storyId: id,
      dbStoryId: id,
      genre: '모험',
      age: '',
      initialPrompt: id,
      chapters: [StoryChapter(chapter: 8, text: '끝', choiceMade: '선택')],
      choices: [],
      choiceOptions: [],
      vocab: [],
      allChoicesMade: ['선택'],
      currentChapter: 8,
    );
    final selected = story('selected');
    final state = _TestAppState()
      ..currentUserId = 'user-1'
      ..currentStory = story('different');
    await tester.pumpWidget(
      ChangeNotifierProvider<AppState>.value(
        value: state,
        child: MaterialApp(home: PsychPage(story: selected)),
      ),
    );
    await tester.pump();
    expect(find.text('분석할 동화를 선택하세요'), findsOneWidget);
    await tester.tap(find.byKey(const Key('psych-story-db:selected')));
    await tester.pump();
    expect(state.loadedEmotionStory, same(selected));
    await tester.ensureVisible(find.byKey(const Key('psych-generate')));
    await tester.tap(find.byKey(const Key('psych-generate')));
    await tester.pump();
    expect(state.requestedStory, same(selected));
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  testWidgets('엔딩 전에도 한 번 선택한 동화는 분석할 수 있다', (tester) async {
    final story = StorySession(
      storyId: 'in-progress',
      dbStoryId: 'in-progress',
      genre: '모험',
      age: '',
      initialPrompt: '진행 중인 동화',
      chapters: [
        StoryChapter(chapter: 1, text: '첫 장면'),
        StoryChapter(chapter: 2, text: '두 번째 장면', choiceMade: '친구에게 길을 물어본다'),
      ],
      choices: const ['계속 읽기'],
      choiceOptions: const [],
      vocab: const [],
      allChoicesMade: const ['친구에게 길을 물어본다'],
      currentChapter: 2,
    );
    final state = _TestAppState()
      ..currentUserId = 'user-1'
      ..currentStory = story;

    await tester.pumpWidget(
      ChangeNotifierProvider<AppState>.value(
        value: state,
        child: const MaterialApp(home: PsychPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('psych-story-db:in-progress')));
    await tester.pump();

    expect(find.textContaining('진행 중 동화 · 지금까지 1번 선택했어요.'), findsOneWidget);
    expect(find.byKey(const Key('psych-generate')), findsOneWidget);
    expect(find.textContaining('엔딩을 본 뒤 분석할 수 있어요'), findsNothing);

    await tester.ensureVisible(find.byKey(const Key('psych-generate')));
    await tester.tap(find.byKey(const Key('psych-generate')));
    await tester.pump();
    expect(state.requestedStory, same(story));

    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  testWidgets('저장된 해설의 다시 생성 버튼은 강제로 새 해설을 요청한다', (tester) async {
    final selected = StorySession(
      storyId: 'story-psych',
      dbStoryId: 'db-psych',
      genre: '모험',
      age: '',
      initialPrompt: '선택의 숲',
      chapters: [
        StoryChapter(chapter: 1, text: '첫 장면'),
        StoryChapter(
          chapter: 2,
          text: '갈림길이 나타났어요.',
          choiceMade: '부엉이에게 길을 묻는다',
        ),
      ],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      allChoicesMade: const ['부엉이에게 길을 묻는다'],
      currentChapter: 2,
    );
    final state = _TestAppState()
      ..currentUserId = 'user-1'
      ..currentStory = selected
      ..showPsychResult = true;
    await tester.pumpWidget(
      ChangeNotifierProvider<AppState>.value(
        value: state,
        child: const MaterialApp(home: PsychPage()),
      ),
    );
    await tester.pump();
    await tester.tap(find.byKey(const Key('psych-story-db:db-psych')));
    await tester.pump();
    final regenerate = find.byKey(const Key('psych-regenerate'));
    await tester.ensureVisible(regenerate);
    await tester.tap(regenerate);
    await tester.pump();
    expect(state.requestedStory, same(selected));
    expect(state.requestedForceRegenerate, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  test('임시 동화의 감정 분석 후 LLM 해설도 요청한다', () async {
    final state = _TemporaryAnalysisAppState()..currentUserId = 'user-1';
    final started = await state.startTemporaryStory(
      genre: '모험',
      age: '',
      prompt: '별빛 숲 이야기',
      analyzeChoicesWithModel: true,
    );
    expect(started, isTrue);
    final story = state.currentStory!;
    await state.continueStory(story.choices.first);

    await state.analyzeStoryAndHistory(story);

    expect(state.loadedEmotionStory, same(story));
    expect(state.requestedPsychStory, same(story));

    await Future<void>.delayed(const Duration(milliseconds: 1));
    state.dispose();
  });
}
