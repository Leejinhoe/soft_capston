import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

import '../models/story_model.dart';
import '../utils/korean_word_normalizer.dart';

/// A single newline-delimited event sent while the story model is generating.
class StoryStreamEvent {
  const StoryStreamEvent({required this.type, required this.data});

  final String type;
  final Map<String, dynamic> data;

  String get text => data['text']?.toString() ?? '';
}

/// Thrown only when the deployed AI server does not expose the stream routes.
/// The app can safely retry the existing JSON endpoint in this case.
class StoryStreamUnavailableException implements Exception {
  const StoryStreamUnavailableException(this.statusCode);

  final int statusCode;

  @override
  String toString() => '스트리밍 동화 서버를 찾을 수 없어요. ($statusCode)';
}

class ApiService {
  static String _newStoryTraceId() {
    Random random;
    try {
      random = Random.secure();
    } on UnsupportedError {
      random = Random();
    }
    return List.generate(
      16,
      (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
    ).join();
  }

  static String newRequestId() => _newStoryTraceId();

  static void _storyLog(
    String event,
    String traceId,
    Map<String, Object?> fields,
  ) {
    debugPrint(
      '[story] ${jsonEncode({'event': event, 'trace_id': traceId, ...fields})}',
    );
  }

  static void _sttLog(
    String event,
    String requestId,
    Map<String, Object?> fields,
  ) {
    debugPrint(
      '[stt] ${jsonEncode({'event': event, 'request_id': requestId, ...fields})}',
    );
  }

  static Future<T> _traceStory<T>(
    String operation,
    Future<T> Function(String traceId) run,
  ) async {
    final traceId = _newStoryTraceId();
    final timer = Stopwatch()..start();
    _storyLog('request_start', traceId, {'operation': operation});
    try {
      final result = await run(traceId);
      _storyLog('request_complete', traceId, {
        'operation': operation,
        'duration_ms': timer.elapsedMilliseconds,
      });
      return result;
    } catch (error) {
      _storyLog('request_error', traceId, {
        'operation': operation,
        'duration_ms': timer.elapsedMilliseconds,
        'error_type': error.runtimeType.toString(),
      });
      rethrow;
    }
  }

  static const String _definedBaseUrl = String.fromEnvironment(
    'AI_API_BASE_URL',
  );
  static const String _legacyDefinedBaseUrl = String.fromEnvironment(
    'STORY_API_BASE_URL',
  );
  static String get _localBaseUrl {
    if (kIsWeb) return 'http://127.0.0.1:8000';
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  static String get baseUrl {
    final defined = _definedBaseUrl.trim();
    if (defined.isNotEmpty) return _withoutTrailingSlash(defined);

    final legacyDefined = _legacyDefinedBaseUrl.trim();
    if (legacyDefined.isNotEmpty) return _withoutTrailingSlash(legacyDefined);

    final configured = dotenv.isInitialized
        ? dotenv.env['AI_API_BASE_URL']?.trim() ??
              dotenv.env['STORY_API_BASE_URL']?.trim() ??
              dotenv.env['LLM_API_BASE_URL']?.trim() ??
              ''
        : '';
    if (configured.isNotEmpty) return _withoutTrailingSlash(configured);

    return _localBaseUrl;
  }

  static String _withoutTrailingSlash(String value) =>
      value.endsWith('/') ? value.substring(0, value.length - 1) : value;

  static String _storyContext(String text, {int maxCharacters = 12000}) {
    final normalized = text.trim();
    if (normalized.length <= maxCharacters) return normalized;
    final side = maxCharacters ~/ 2;
    return '${normalized.substring(0, side)}\n\n[중간 장면 생략]\n\n'
        '${normalized.substring(normalized.length - side)}';
  }

  static String _responseError(http.Response response, String fallback) {
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded['detail'] != null) {
        return decoded['detail'].toString();
      }
    } catch (_) {}
    return '$fallback (${response.statusCode})';
  }

  static Future<String> explainWord({
    required String word,
    required String sentence,
    required String age,
  }) async {
    final lookupWord = KoreanWordNormalizer.lookupWord(word);
    if (lookupWord.isEmpty) {
      throw const FormatException('뜻을 찾을 단어가 비어 있어요.');
    }
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/word-meaning'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'word': lookupWord,
            'sentence': sentence,
            'age': age,
          }),
        )
        .timeout(const Duration(seconds: 120));
    if (response.statusCode != 200) {
      throw Exception(_responseError(response, '단어 뜻을 불러오지 못했어요'));
    }
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    final meaning = decoded is Map
        ? decoded['definition']?.toString().trim()
        : null;
    if (meaning == null || meaning.isEmpty) {
      throw const FormatException('단어 뜻이 비어 있어요.');
    }
    return meaning;
  }

  static String? _characterLockInstruction(
    Map<String, dynamic>? characterContext,
  ) {
    if (characterContext == null) return null;
    return '[CHARACTER LOCK] Use the selected protagonist throughout the story. '
        'Do not replace this character. '
        'character_key=${characterContext['character_key']}; '
        'name=${characterContext['name']}; '
        'appearance=${characterContext['description']}.';
  }

  static const List<String> _safeFallbackChoices = [
    '주변의 단서를 자세히 살펴본다',
    '숲속 친구에게 도움을 청한다',
    '빛나는 길을 따라 조심스럽게 나아간다',
  ];

  static bool _isUsableChoice(dynamic value) {
    final text = value?.toString().trim() ?? '';
    final lower = text.toLowerCase();
    const blocked = [
      'javascript',
      'typescript',
      'python',
      'codeblock',
      'description',
      'language',
      'choices',
      'undefined',
      'null',
    ];
    return text.length >= 4 &&
        text.length <= 40 &&
        RegExp(r'[가-힣]').hasMatch(text) &&
        !blocked.any(lower.contains) &&
        !RegExp(r'[{}\[\]`:]').hasMatch(text);
  }

  static Map<String, dynamic> _normalizeStoryResponse(
    dynamic decoded,
    String traceId,
  ) {
    final result = Map<String, dynamic>.from(decoded as Map);
    // Ignore scoring payloads from both current and older LLM servers.
    result['emotion_scoring_enabled'] = false;
    result['choice_emotions'] = const <dynamic>[];
    result['story_emotion'] = null;
    result['selected_choice_emotion'] = null;
    final chapter = int.tryParse(result['chapter']?.toString() ?? '');
    final completed =
        result['completed'] == true || (chapter != null && chapter >= 8);
    if (completed) {
      // An eight-stage server ends with no next choices. Do not replace that
      // intentional empty list with offline fallback choices.
      result['choices'] = const <String>[];
      result['choice_emotions'] = const <dynamic>[];
      return result;
    }
    final rawChoices = result['choices'] as List? ?? const [];
    final choices = <String>[];

    for (var index = 0; index < rawChoices.length; index++) {
      final choice = rawChoices[index];
      if (!_isUsableChoice(choice)) continue;
      final text = choice.toString().trim();
      if (choices.contains(text)) continue;
      choices.add(text);
      if (choices.length == 3) break;
    }

    if (choices.length < 3) {
      _storyLog('choices_fallback', traceId, {
        'usable_choices': choices.length,
      });
      result['choices'] = _safeFallbackChoices;
      result['choice_emotions'] = const [];
    } else {
      result['choices'] = choices;
    }
    return result;
  }

  static Future<Map<String, dynamic>> startStory({
    required String genre,
    required String age,
    required String prompt,
    Map<String, dynamic>? characterContext,
    List<Map<String, dynamic>>? storyCast,
    Map<String, String>? characterOverrides,
  }) => _traceStory(
    'start',
    (traceId) => _startStory(
      genre: genre,
      age: age,
      prompt: prompt,
      characterContext: characterContext,
      storyCast: storyCast,
      characterOverrides: characterOverrides,
      traceId: traceId,
    ),
  );

  static Future<Map<String, dynamic>> _startStory({
    required String genre,
    required String age,
    required String prompt,
    Map<String, dynamic>? characterContext,
    List<Map<String, dynamic>>? storyCast,
    Map<String, String>? characterOverrides,
    required String traceId,
  }) async {
    final normalizedCharacterContext = characterContext == null
        ? null
        : Map<String, dynamic>.from(characterContext);
    final characterInstruction = _characterLockInstruction(
      normalizedCharacterContext,
    );
    var response = await http
        .post(
          Uri.parse('$baseUrl/story/start'),
          headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': traceId,
          },
          body: json.encode({
            'genre': genre,
            'age': age,
            'prompt': characterInstruction == null
                ? prompt
                : '$prompt\n\n$characterInstruction',
            if (normalizedCharacterContext != null)
              'character_key': normalizedCharacterContext['character_key'],
            'character_context': ?normalizedCharacterContext,
            if (storyCast != null && storyCast.isNotEmpty)
              'story_cast': storyCast,
            if (characterOverrides != null && characterOverrides.isNotEmpty)
              'character_overrides': characterOverrides,
            'include_image': false,
          }),
        )
        .timeout(const Duration(seconds: 30));

    _storyLog('http_response', traceId, {
      'operation': 'start',
      'status': response.statusCode,
    });

    if (response.statusCode == 202) {
      final startJob = json.decode(utf8.decode(response.bodyBytes)) as Map;
      final jobId = startJob['job_id']?.toString();
      if (jobId == null || jobId.isEmpty) {
        throw Exception('동화 생성 작업 ID를 받지 못했습니다.');
      }

      final deadline = DateTime.now().add(const Duration(minutes: 15));
      while (DateTime.now().isBefore(deadline)) {
        await Future<void>.delayed(const Duration(seconds: 2));
        response = await http
            .get(
              Uri.parse(
                '$baseUrl/story/start/jobs/${Uri.encodeComponent(jobId)}',
              ),
              headers: {'X-Request-ID': traceId},
            )
            .timeout(const Duration(seconds: 30));
        if (response.statusCode != 200) {
          _storyLog('http_response', traceId, {
            'operation': 'start_poll',
            'status': response.statusCode,
          });
          throw Exception(_responseError(response, '동화 생성 상태 확인 실패'));
        }

        final job = json.decode(utf8.decode(response.bodyBytes)) as Map;
        switch (job['status']) {
          case 'completed':
            final result = Map<String, dynamic>.from(job['result'] as Map);
            return _normalizeStoryResponse(result, traceId);
          case 'failed':
            throw Exception(job['error']?.toString() ?? '동화 생성에 실패했습니다.');
        }
      }
      throw Exception('동화 생성이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요.');
    }

    if (response.statusCode == 200) {
      return _normalizeStoryResponse(
        json.decode(utf8.decode(response.bodyBytes)),
        traceId,
      );
    }
    throw Exception(_responseError(response, '동화 생성 실패'));
  }

  static Future<Map<String, dynamic>> continueStory({
    required String storyId,
    required String storySoFar,
    required String choice,
    required String genre,
    required String age,
    Map<String, dynamic>? characterContext,
    Map<String, dynamic>? previousSceneContract,
    List<Map<String, dynamic>>? storyCast,
    Map<String, String>? characterOverrides,
    String? runtimeState,
    Map<String, dynamic>? recoveryContext,
  }) => _traceStory(
    'continue',
    (traceId) => _continueStory(
      storyId: storyId,
      storySoFar: storySoFar,
      choice: choice,
      genre: genre,
      age: age,
      characterContext: characterContext,
      previousSceneContract: previousSceneContract,
      storyCast: storyCast,
      characterOverrides: characterOverrides,
      runtimeState: runtimeState,
      recoveryContext: recoveryContext,
      traceId: traceId,
    ),
  );

  static Future<Map<String, dynamic>> _continueStory({
    required String storyId,
    required String storySoFar,
    required String choice,
    required String genre,
    required String age,
    Map<String, dynamic>? characterContext,
    Map<String, dynamic>? previousSceneContract,
    List<Map<String, dynamic>>? storyCast,
    Map<String, String>? characterOverrides,
    String? runtimeState,
    Map<String, dynamic>? recoveryContext,
    required String traceId,
  }) async {
    final normalizedCharacterContext = characterContext == null
        ? null
        : Map<String, dynamic>.from(characterContext);
    final characterInstruction = _characterLockInstruction(
      normalizedCharacterContext,
    );
    final normalizedRuntimeState = runtimeState?.trim() ?? '';
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/continue'),
          headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': traceId,
          },
          body: json.encode({
            'story_id': storyId,
            'choice': choice,
            'genre': genre,
            'age': age,
            'character_instruction': ?characterInstruction,
            'previous_scene_contract': ?previousSceneContract,
            if (normalizedCharacterContext != null)
              'character_key': normalizedCharacterContext['character_key'],
            'character_context': ?normalizedCharacterContext,
            if (storyCast != null && storyCast.isNotEmpty)
              'story_cast': storyCast,
            if (characterOverrides != null && characterOverrides.isNotEmpty)
              'character_overrides': characterOverrides,
            // The integrated 8-stage server restores its plan from runtime_state.
            // Older servers still receive the full story when no state is available.
            if (normalizedRuntimeState.isNotEmpty)
              'runtime_state': normalizedRuntimeState
            else
              'story_so_far': storySoFar,
            if (recoveryContext != null) 'recovery_context': recoveryContext,
            'include_image': false,
          }),
        )
        .timeout(const Duration(seconds: 600));

    _storyLog('http_response', traceId, {
      'operation': 'continue',
      'status': response.statusCode,
    });

    if (response.statusCode == 200) {
      return _normalizeStoryResponse(
        json.decode(utf8.decode(response.bodyBytes)),
        traceId,
      );
    }
    throw Exception('이어쓰기 실패: ${response.statusCode}');
  }

  static Future<Map<String, dynamic>?> classifySelectedChoice({
    required int selectedStep,
    required String previousScene,
    required String choice,
  }) async {
    final traceId = _newStoryTraceId();
    final timer = Stopwatch()..start();
    _storyLog('choice_emotion_start', traceId, {'step': selectedStep});
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/story/emotion-analysis'),
            headers: {
              'Content-Type': 'application/json',
              'X-Request-ID': traceId,
            },
            body: json.encode({
              'scenes': [
                {
                  'step_number': selectedStep - 1,
                  'content': previousScene.length > 12000
                      ? previousScene.substring(previousScene.length - 12000)
                      : previousScene,
                },
                {
                  'step_number': selectedStep,
                  'content': '',
                  'user_choice': choice,
                },
              ],
            }),
          )
          .timeout(const Duration(seconds: 30));
      _storyLog('choice_emotion_response', traceId, {
        'status': response.statusCode,
        'duration_ms': timer.elapsedMilliseconds,
      });
      if (response.statusCode != 200) {
        throw Exception(_responseError(response, '선택 문장 감정 분류 실패'));
      }
      final report = json.decode(utf8.decode(response.bodyBytes));
      if (report is! Map || report['items'] is! List) {
        throw const FormatException('감정 분류 응답 형식이 올바르지 않습니다.');
      }
      final reportItems = (report['items'] as List).whereType<Map>().toList();
      final matching = reportItems
          .where((item) => item['step'] == selectedStep - 1)
          .toList();
      final item = matching.isNotEmpty
          ? matching.first
          : reportItems.isNotEmpty
          ? reportItems.first
          : null;
      if (item == null || item['scores'] is! Map) return null;

      final scores = <String, double>{};
      for (final entry in (item['scores'] as Map).entries) {
        final value = entry.value;
        if (value is num && value.isFinite && value >= 0 && value <= 1) {
          scores[entry.key.toString()] = value.toDouble();
        }
      }
      if (scores.isEmpty) return null;
      final sorted = scores.entries.toList()
        ..sort((a, b) => b.value.compareTo(a.value));
      final label = item['label']?.toString() ?? '';
      final topEmotions = sorted
          .map(
            (entry) => {
              'label': entry.key,
              'label_display': entry.key,
              'score': entry.value,
            },
          )
          .toList();
      return {
        'emotion_label_source': 'korean_dialogue_emotion_v1',
        'emotion_labels_are_generic': false,
        'primary_emotion_index': null,
        'primary_emotion': label,
        'primary_emotion_display': label,
        'primary_score': sorted.first.value,
        'top_emotions': topEmotions,
        'active_emotions': topEmotions,
        'scores': scores,
        'scores_by_index': const <String, double>{},
        'classification_status': item['status']?.toString() ?? 'uncertain',
      };
    } catch (error) {
      _storyLog('choice_emotion_error', traceId, {
        'duration_ms': timer.elapsedMilliseconds,
        'error_type': error.runtimeType.toString(),
      });
      rethrow;
    }
  }

  /// Converts a Flutter-recorded WAV to Korean text on the Colab GPU.
  static Future<String> transcribeKoreanSpeech(
    Uint8List wavBytes, {
    String? requestId,
    int? recordingDurationMs,
  }) async {
    final id = requestId ?? newRequestId();
    final timer = Stopwatch()..start();
    _sttLog('client_request_start', id, {
      'audio_bytes': wavBytes.length,
      'recording_duration_ms': recordingDurationMs,
    });
    if (wavBytes.length < 800) {
      _sttLog('client_request_rejected', id, {
        'reason': 'audio_too_small',
        'audio_bytes': wavBytes.length,
      });
      throw const FormatException('녹음이 너무 짧아요. 다시 말씀해 주세요.');
    }
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/stt'))
      ..headers['X-Request-ID'] = id
      ..headers['X-Recording-Duration-Ms'] = (recordingDurationMs ?? 0)
          .toString()
      ..fields['language'] = 'ko'
      ..files.add(
        http.MultipartFile.fromBytes(
          'audio',
          wavBytes,
          filename: 'character-chat.wav',
        ),
      );
    try {
      final streamed = await request.send().timeout(
        const Duration(seconds: 120),
      );
      final response = await http.Response.fromStream(streamed);
      final responseRequestId = response.headers['x-request-id'];
      _sttLog('client_http_response', id, {
        'status': response.statusCode,
        'response_request_id': responseRequestId,
        'duration_ms': timer.elapsedMilliseconds,
      });
      if (response.statusCode != 200) {
        throw Exception(_responseError(response, '음성을 글자로 바꾸지 못했어요'));
      }
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      final text = decoded is Map
          ? decoded['text']?.toString().trim() ?? ''
          : '';
      _sttLog('client_transcript_result', id, {
        'transcript_present': text.isNotEmpty,
        'transcript_chars': text.length,
        'recording_duration_ms': recordingDurationMs,
        'duration_ms': timer.elapsedMilliseconds,
      });
      if (text.isEmpty) {
        throw const FormatException('말한 내용을 알아듣지 못했어요. 조금 더 또렷하게 말씀해 주세요.');
      }
      return text;
    } catch (error) {
      _sttLog('client_request_error', id, {
        'duration_ms': timer.elapsedMilliseconds,
        'error_type': error.runtimeType.toString(),
      });
      rethrow;
    }
  }

  /// Starts the GPU speech model before the child finishes their first turn.
  static Future<void> warmUpKoreanSpeech() async {
    final response = await http
        .post(Uri.parse('$baseUrl/api/stt/warm-up'))
        .timeout(const Duration(seconds: 120));
    if (response.statusCode != 200) {
      throw Exception(_responseError(response, '음성 인식 준비에 실패했어요'));
    }
  }

  static Future<Map<String, dynamic>> analyzePsychology({
    required String storyId,
    required String storyTitle,
    required List<String> choicesMade,
    required bool completed,
    String? runtimeState,
    Map<String, dynamic>? storyContext,
    required Map<String, dynamic> emotionReport,
  }) async {
    final classifierItems = (emotionReport['items'] as List? ?? const [])
        .whereType<Map>()
        .map(
          (item) => {
            'step': item['step'],
            'status': item['status'],
            'label': item['label'],
            'scores': item['scores'],
          },
        )
        .toList();
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/psych'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({
            'story_id': storyId,
            'story_title': storyTitle,
            'choices_made': choicesMade,
            if (runtimeState?.trim().isNotEmpty == true)
              'runtime_state': runtimeState,
            'story_context': ?storyContext,
            'emotion_scoring_enabled': false,
            'classifier_report': {
              'model': emotionReport['model'],
              'items': classifierItems,
            },
            'completed': completed,
          }),
        )
        .timeout(const Duration(seconds: 300));

    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes));
    }
    throw Exception(
      '감정 분석 실패: ${response.statusCode} '
      '${utf8.decode(response.bodyBytes)}',
    );
  }

  static Future<List<StoryCharacter>> discoverStoryCharacters({
    required String storyId,
    required String storyTitle,
    required String storyText,
    required String age,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/characters'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'story_id': storyId,
            'story_title': storyTitle,
            'story_text': _storyContext(storyText),
            'age': age,
          }),
        )
        .timeout(const Duration(seconds: 180));

    if (response.statusCode != 200) {
      throw Exception(_responseError(response, '등장인물을 불러오지 못했어요'));
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map) {
      throw const FormatException('등장인물 응답 형식이 올바르지 않아요.');
    }
    final characters = (decoded['characters'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => StoryCharacter.fromJson(Map<String, dynamic>.from(item)))
        .where((character) => character.name.isNotEmpty)
        .take(5)
        .toList();
    if (characters.isEmpty) {
      throw const FormatException('대화할 수 있는 등장인물을 찾지 못했어요.');
    }
    return characters;
  }

  static Future<CharacterChatReply> chatWithStoryCharacter({
    required String storyId,
    required String storyTitle,
    required String storyText,
    required String age,
    required String userName,
    required StoryCharacter character,
    required List<CharacterChatMessage> messages,
    required String userMessage,
  }) async {
    final recentMessages = messages.length > 12
        ? messages.sublist(messages.length - 12)
        : messages;
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/character-chat'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'story_id': storyId,
            'story_title': storyTitle,
            'story_text': _storyContext(storyText),
            'age': age,
            'user_name': userName,
            'character': character.toJson(),
            'messages': recentMessages
                .map((message) => message.toJson())
                .toList(),
            'user_message': userMessage,
          }),
        )
        .timeout(const Duration(seconds: 180));

    if (response.statusCode != 200) {
      throw Exception(_responseError(response, '캐릭터의 답장을 받지 못했어요'));
    }

    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map) {
      throw const FormatException('캐릭터 답장 형식이 올바르지 않아요.');
    }
    final result = CharacterChatReply.fromJson(
      Map<String, dynamic>.from(decoded),
    );
    if (result.reply.isEmpty) {
      throw const FormatException('캐릭터의 답장이 비어 있어요.');
    }
    return result;
  }

  static Future<String?> generateImage({
    required String storyText,
    required String genre,
    required String age,
    Map<String, dynamic>? characterContext,
    List<Map<String, dynamic>>? storyCast,
    Map<String, String>? characterOverrides,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/story/image'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({
              'story_text': storyText,
              'genre': genre,
              'age': age,
              if (characterContext != null)
                'character_key': characterContext['character_key'],
              'character_context': ?characterContext,
              if (storyCast != null && storyCast.isNotEmpty)
                'story_cast': storyCast,
              if (characterOverrides != null && characterOverrides.isNotEmpty)
                'character_overrides': characterOverrides,
            }),
          )
          .timeout(const Duration(seconds: 120));

      if (response.statusCode == 200) {
        final data = json.decode(utf8.decode(response.bodyBytes));
        return data['image_b64'] as String?;
      }
    } catch (_) {}
    return null;
  }

  static Future<bool> checkHealth() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
