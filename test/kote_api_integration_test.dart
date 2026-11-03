import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:fairytale_hyeonlim_merged/services/api_service.dart';

void main() {
  test('continuation new_text is sent to the emotion model', () async {
    await http.runWithClient(
      () => ApiService.attachKoteEmotions({
        'new_text': '이어지는 새 본문',
        'choices': <String>[],
      }),
      () => MockClient((request) async {
        expect((jsonDecode(request.body) as Map)['story_text'], '이어지는 새 본문');
        return http.Response('{"emotion_scoring_enabled":false}', 200);
      }),
    );
  });
  final analysis = <String, dynamic>{
    'emotion_label_source': 'kote_checkpoint_v1',
    'emotion_scoring_enabled': true,
    'abstained': false,
    'top_emotions': [
      {'label': '기쁨', 'score': .9},
    ],
  };
  test('oversized story does not block choice analysis', () async {
    final storyText = List.filled(20001, '가').join();
    final result = await http.runWithClient(
      () => ApiService.attachKoteEmotions({
        'story_text': storyText,
        'choices': ['선택 하나'],
      }),
      () => MockClient((request) async {
        final body = jsonDecode(request.body) as Map;
        expect(body['story_text'], '');
        expect(body['choices'], ['선택 하나']);
        return http.Response(
          jsonEncode({
            'emotion_scoring_enabled': true,
            'choice_emotions': [analysis],
          }),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      }),
    );
    expect(result['story_text'], storyText);
    expect((result['choice_emotions'] as List).single, isNotNull);
  });
  test(
    'KOTE is requested for normalized choices and the selected choice',
    () async {
      final client = MockClient((request) async {
        expect(request.url.path, '/api/emotions/analyze');
        final body = jsonDecode(request.body) as Map;
        expect(body['choices'], ['선택 하나']);
        expect(body['selected_choice'], '지난 선택');
        return http.Response(
          jsonEncode({
            'emotion_scoring_enabled': true,
            'story_emotion': analysis,
            'choice_emotions': [analysis],
            'selected_choice_emotion': analysis,
          }),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        );
      });
      final result = await http.runWithClient(
        () => ApiService.attachKoteEmotions({
          'story_text': '본문',
          'choices': ['선택 하나'],
        }, selectedChoice: '지난 선택'),
        () => client,
      );
      expect(result['emotion_scoring_enabled'], true);
      expect((result['choice_emotions'] as List).single, isNotNull);
    },
  );
  test('analysis failure preserves story and removes old LLM scores', () async {
    final result = await http.runWithClient(
      () => ApiService.attachKoteEmotions({
        'story_text': '본문',
        'choices': ['선택 하나'],
        'story_emotion': analysis,
      }),
      () => MockClient((_) async => http.Response('', 503)),
    );
    expect(result['story_text'], '본문');
    expect(result['story_emotion'], isNull);
    expect(result['emotion_scoring_enabled'], false);
  });
  test('ambiguous scores never become displayed emotions', () async {
    final result = await http.runWithClient(
      () => ApiService.attachKoteEmotions({
        'choices': ['선택 하나'],
      }),
      () => MockClient(
        (_) async => http.Response(
          jsonEncode({
            'emotion_scoring_enabled': true,
            'choice_emotions': [
              {...analysis, 'requires_review': true},
            ],
          }),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        ),
      ),
    );
    expect((result['choice_emotions'] as List).single, isNull);
  });
}
