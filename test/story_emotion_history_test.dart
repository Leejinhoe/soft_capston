import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
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

void main() {
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
  });
}
