import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

import '../models/story_model.dart';

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
  static const String _definedBaseUrl =
      String.fromEnvironment('AI_API_BASE_URL');
  static const String _legacyDefinedBaseUrl =
      String.fromEnvironment('STORY_API_BASE_URL');
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

  static Map<String, dynamic> _normalizeStoryResponse(dynamic decoded) {
    final result = Map<String, dynamic>.from(decoded as Map);
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
    final rawEmotions = result['choice_emotions'] as List? ?? const [];
    final choices = <String>[];
    final emotions = <dynamic>[];

    for (var index = 0; index < rawChoices.length; index++) {
      final choice = rawChoices[index];
      if (!_isUsableChoice(choice)) continue;
      final text = choice.toString().trim();
      if (choices.contains(text)) continue;
      choices.add(text);
      if (index < rawEmotions.length) emotions.add(rawEmotions[index]);
      if (choices.length == 3) break;
    }

    if (choices.length < 3) {
      result['choices'] = _safeFallbackChoices;
      result['choice_emotions'] = const [];
    } else {
      result['choices'] = choices;
      result['choice_emotions'] = emotions;
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
  }) async {
    final normalizedCharacterContext = characterContext == null
        ? null
        : Map<String, dynamic>.from(characterContext);
    final characterInstruction = _characterLockInstruction(
      normalizedCharacterContext,
    );
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/start'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({
            'genre': genre,
            'age': age,
            'prompt': characterInstruction == null
                ? prompt
                : '$prompt\n\n$characterInstruction',
            if (normalizedCharacterContext != null)
              'character_key': normalizedCharacterContext['character_key'],
            if (normalizedCharacterContext != null)
              'character_context': normalizedCharacterContext,
            if (storyCast != null && storyCast.isNotEmpty)
              'story_cast': storyCast,
            if (characterOverrides != null && characterOverrides.isNotEmpty)
              'character_overrides': characterOverrides,
            'include_image': false,
          }),
        )
        .timeout(const Duration(seconds: 600));

    if (response.statusCode == 200) {
      return _normalizeStoryResponse(
        json.decode(utf8.decode(response.bodyBytes)),
      );
    }
    throw Exception('동화 생성 실패: ${response.statusCode}');
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
  }) async {
    final normalizedCharacterContext = characterContext == null
        ? null
        : Map<String, dynamic>.from(characterContext);
    final characterInstruction = _characterLockInstruction(
      normalizedCharacterContext,
    );
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/continue'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({
            'story_id': storyId,
            'story_so_far': storySoFar,
            'choice': choice,
            'genre': genre,
            'age': age,
            if (characterInstruction != null)
              'character_instruction': characterInstruction,
            if (previousSceneContract != null)
              'previous_scene_contract': previousSceneContract,
            if (normalizedCharacterContext != null)
              'character_key': normalizedCharacterContext['character_key'],
            if (normalizedCharacterContext != null)
              'character_context': normalizedCharacterContext,
            if (storyCast != null && storyCast.isNotEmpty)
              'story_cast': storyCast,
            if (characterOverrides != null && characterOverrides.isNotEmpty)
              'character_overrides': characterOverrides,
            if (runtimeState != null && runtimeState.trim().isNotEmpty)
              'runtime_state': runtimeState,
            'include_image': false,
          }),
        )
        .timeout(const Duration(seconds: 600));

    if (response.statusCode == 200) {
      return _normalizeStoryResponse(
        json.decode(utf8.decode(response.bodyBytes)),
      );
    }
    throw Exception('이어쓰기 실패: ${response.statusCode}');
  }

  /// Converts a Flutter-recorded WAV to Korean text on the Colab GPU.
  static Future<String> transcribeKoreanSpeech(Uint8List wavBytes) async {
    if (wavBytes.length < 800) {
      throw const FormatException('녹음이 너무 짧아요. 다시 말씀해 주세요.');
    }
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/stt'))
      ..fields['language'] = 'ko'
      ..files.add(
        http.MultipartFile.fromBytes(
          'audio',
          wavBytes,
          filename: 'character-chat.wav',
        ),
      );
    final streamed = await request.send().timeout(const Duration(seconds: 120));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode != 200) {
      throw Exception(_responseError(response, '음성을 글자로 바꾸지 못했어요'));
    }
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    final text = decoded is Map ? decoded['text']?.toString().trim() ?? '' : '';
    if (text.isEmpty) {
      throw const FormatException('말한 내용을 알아듣지 못했어요. 조금 더 또렷하게 말씀해 주세요.');
    }
    return text;
  }

  static Future<Map<String, dynamic>> analyzePsychology({
    required String storyId,
    required String storyTitle,
    required List<String> choicesMade,
    required List<Map<String, dynamic>> choiceEmotions,
    required bool completed,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/psych'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({
            'story_id': storyId,
            'story_title': storyTitle,
            'choices_made': choicesMade,
            'choice_emotions': choiceEmotions,
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
              if (characterContext != null)
                'character_context': characterContext,
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
