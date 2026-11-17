import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:flutter_test/flutter_test.dart';

EmotionAnalysis _emotion(String label, double score) {
  return EmotionAnalysis(
    emotionLabelSource: 'builtin_kote',
    emotionLabelsAreGeneric: false,
    primaryEmotionIndex: 42,
    primaryEmotion: label,
    primaryEmotionDisplay: label,
    primaryScore: score,
    topEmotions: [
      EmotionScoreItem(
        labelIndex: 42,
        label: label,
        labelDisplay: label,
        score: score,
      ),
    ],
    activeEmotions: const [],
    scores: {label: score},
    scoresByIndex: {42: score},
  );
}

StorySession _story({required List<String> nextChoices}) {
  return StorySession(
    storyId: 'story-1',
    genre: '판타지',
    age: '초등_저학년',
    initialPrompt: '별이를 구하는 모험',
    chapters: [
      StoryChapter(chapter: 1, text: '모험이 시작되었어요.'),
      StoryChapter(
        chapter: 2,
        text: '별이가 빛을 따라갔어요.',
        choiceMade: '빛나는 길을 따라간다',
        selectedChoiceEmotion: _emotion('기대감', 0.91),
      ),
    ],
    choices: nextChoices,
    choiceOptions: const [],
    vocab: const [],
    allChoicesMade: const ['빛나는 길을 따라간다'],
    currentChapter: 2,
  );
}

class _MissingEmotionReportState extends AppState {
  StorySession? requestedStory;

  @override
  Future<void> loadStoryEmotionAnalysis(StorySession story) async {
    emotionAnalysisNotice = '저장된 감정 분류 점수를 찾지 못했어요.';
    notifyListeners();
  }

  @override
  Map<String, dynamic>? emotionReportFor(StorySession story) => null;

  @override
  Future<void> loadPsychAnalysis({StorySession? selectedStory}) async {
    requestedStory = selectedStory;
  }
}

void main() {
  test('이어 읽는 동화도 서재 목록에 한 번만 남는다', () async {
    final story = _story(nextChoices: const ['계속 읽기']);
    final state = AppState()..completedStories = [story];
    state.resumeStory(story);
    expect(state.currentStory, same(story));
    expect(state.completedStories, [story]);
    state.resetCurrentStory();
    expect(state.completedStories, [story]);
    await Future<void>.delayed(Duration.zero);
    state.dispose();
  });
  test('진행 중인 동화의 선택이 있으면 엔딩 전 분석 대상으로 우선 고른다', () {
    final incomplete = _story(nextChoices: const ['계속']);
    final complete = StorySession(
      storyId: 'finished',
      genre: '판타지',
      age: '',
      initialPrompt: '완결',
      chapters: [StoryChapter(chapter: 8, text: '끝')],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      currentChapter: 8,
      allChoicesMade: const ['마지막 선택'],
    );
    final state = AppState()
      ..currentStory = incomplete
      ..completedStories = [incomplete, complete];
    expect(state.activePsychStory, same(incomplete));
    expect(state.canAnalyzeStory(incomplete), isTrue);
    state.dispose();
  });

  test('아직 선택이 없는 동화는 감정분석 대상으로 허용하지 않는다', () {
    final story = StorySession(
      storyId: 'unselected',
      genre: '판타지',
      age: '',
      initialPrompt: '선택 전 동화',
      chapters: [StoryChapter(chapter: 1, text: '첫 장면')],
      choices: const ['친구에게 묻는다'],
      choiceOptions: const [],
      vocab: const [],
      currentChapter: 1,
    );
    final state = AppState();
    expect(state.canAnalyzeStory(story), isFalse);
    state.dispose();
  });

  test('분류 점수 조회에 실패해도 선택 기록 기반 LLM 해설을 요청한다', () async {
    final story = _story(nextChoices: const ['계속 읽기']);
    final state = _MissingEmotionReportState();

    await state.analyzeStoryAndHistory(story);

    expect(state.requestedStory, same(story));
    state.dispose();
  });

  test('임시 동화의 실모델 점수 조회는 계정 저장 오류 대신 안내한다', () async {
    final story = StorySession(
      storyId: 'mock_preview',
      genre: '판타지',
      age: '',
      initialPrompt: '임시 동화',
      chapters: [StoryChapter(chapter: 1, text: '미리 보기 장면')],
      choices: const ['친구에게 도움을 청한다'],
      choiceOptions: const [],
      vocab: const [],
      allChoicesMade: const ['친구에게 도움을 청한다'],
      currentChapter: 1,
    );
    final state = AppState();

    await state.loadStoryEmotionAnalysis(story);

    expect(state.emotionReportFor(story), isNull);
    expect(state.emotionAnalysisNotice, contains('임시 생성'));
    expect(state.emotionAnalysisNotice, contains('실제 감정 분류 모델'));
    state.dispose();
  });
  test('임시 감정분석 테스트 모드는 예시 감정점수를 선택지에 붙이지 않는다', () async {
    final state = AppState()..currentUserId = 'user-1';

    final started = await state.startTemporaryStory(
      genre: '모험',
      age: '',
      prompt: '별빛 숲의 비밀',
      analyzeChoicesWithModel: true,
    );

    expect(started, isTrue);
    final story = state.currentStory!;
    expect(state.isTemporaryEmotionTestStory(story), isTrue);
    expect(
      story.choiceOptions.every((option) => option.emotion == null),
      isTrue,
    );

    final continued = await state.continueStory(story.choices.first);
    expect(continued, isTrue);
    expect(story.chapters.last.selectedChoiceEmotion, isNull);
    expect(state.emotionAnalysisNotice, contains('분석 화면'));
    state.dispose();
  });
  test('DB 저장 동화의 읽기 위치와 선택지를 복원한다', () {
    final story = StorySession.fromDatabaseJson({
      'id': 'db-1',
      'ai_story_id': 'ai-1',
      'runtime_state': 'encoded-state',
      'title': '숲 이야기',
      'genre': '모험',
      'is_shared': true,
      'read_progress': 2,
      'pending_choices': ['나무를 살핀다', '친구에게 묻는다', '길을 따라간다'],
      'scenes': [
        {'step_number': 1, 'story_text': '시작'},
        {
          'step_number': 2,
          'story_text': '두 번째 장면',
          'choice_made': '함께 걷는다',
          'offered_choices': ['함께 걷는다', '나무를 살핀다', '친구에게 묻는다'],
        },
      ],
    });
    expect(story.storyId, 'ai-1');
    expect(story.runtimeState, 'encoded-state');
    expect(story.readProgress, 2);
    expect(story.currentChapter, 2);
    expect(story.choices, hasLength(3));
    expect(story.isCommunityShared, isTrue);
    expect(story.allChoicesMade, ['함께 걷는다']);
    expect(story.chapters.last.offeredChoices, [
      '함께 걷는다',
      '나무를 살핀다',
      '친구에게 묻는다',
    ]);
  });

  test('이전 저장 오류로 선택지가 빠진 미완성 동화를 엔딩으로 보지 않는다', () {
    final story = StorySession.fromDatabaseJson({
      'id': 'db-legacy',
      'title': '옛 동화',
      'genre': '모험',
      'scenes': [
        {'step_number': 1, 'story_text': '시작'},
        {'step_number': 2, 'story_text': '두 번째 장면', 'choice_made': '함께 걷는다'},
      ],
    });
    expect(story.hasReachedEnding, isFalse);
  });

  test('choices가 남아 있으면 엔딩으로 판단하지 않는다', () {
    final story = _story(nextChoices: const ['친구에게 도움을 청한다']);

    expect(story.hasReachedEnding, isFalse);
  });

  test('선택을 마치고 choices가 비면 엔딩과 감정 이력을 만든다', () {
    final story = _story(nextChoices: const []);

    expect(story.hasReachedEnding, isTrue);
    expect(story.choiceEmotionHistory, hasLength(1));

    final payload = story.choiceEmotionHistory.single.toJson();
    expect(payload['choice'], '빛나는 길을 따라간다');
    expect(payload['primary_emotion'], '기대감');
    expect(payload['primary_score'], 0.91);
    expect((payload['top_emotions'] as List).single['score'], 0.91);
    expect((payload['scores'] as Map)['기대감'], 0.91);
  });

  test('AI 분석 응답의 주요 감정과 선택별 해석을 읽는다', () {
    final result = PsychResult.fromJson({
      'type': '사려 깊은 길잡이',
      'description': '선택과 감정 점수를 함께 살핀 분석입니다.',
      'traits': {'모험적': 72, '친절함': 88},
      'dominant_emotions': ['기대감', '안심/신뢰'],
      'choice_insights': [
        {'analysis': '빛을 따라간 선택에서 탐색 성향이 보였어요.'},
      ],
    });

    expect(result.dominantEmotions, ['기대감', '안심/신뢰']);
    expect(result.choiceInsights.single, contains('탐색 성향'));
    expect(result.traits, isEmpty);
  });

  test('기존에 저장한 LLM 감정 점수는 앱에서 사용하지 않는다', () {
    final emotion = EmotionAnalysis.fromJson({
      'emotion_label_source': 'qwen_contextual_analysis_v3',
      'primary_emotion': '걱정',
      'primary_score': 0.9,
      'top_emotions': [
        {'label': '걱정', 'score': 0.9},
      ],
      'scores': {'걱정': 0.9},
    });

    expect(emotion.displayLabel, isEmpty);
    expect(emotion.topEmotions, isEmpty);
    expect(emotion.activeEmotions, isEmpty);
    expect(emotion.scores, isEmpty);
  });
}
