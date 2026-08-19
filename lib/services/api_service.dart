import 'dart:convert';

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
  static const String _fallbackBaseUrl =
      'https://restaurant-reward-himself-vbulletin.trycloudflare.com';

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

    return _fallbackBaseUrl;
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

  static Future<Map<String, dynamic>> startStory({
    required String genre,
    required String age,
    required String prompt,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/story/start'),
          headers: {'Content-Type': 'application/json'},
          body: json.encode({
            'genre': genre,
            'age': age,
            'prompt': prompt,
            'include_image': false,
          }),
        )
        .timeout(const Duration(seconds: 600));

    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes));
    }
    throw Exception('동화 생성 실패: ${response.statusCode}');
  }

  static Future<Map<String, dynamic>> continueStory({
    required String storyId,
    required String storySoFar,
    required String choice,
    required String genre,
    required String age,
  }) async {
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
            'include_image': false,
          }),
        )
        .timeout(const Duration(seconds: 600));

    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes));
    }
    throw Exception('이어쓰기 실패: ${response.statusCode}');
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
            'messages':
                recentMessages.map((message) => message.toJson()).toList(),
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
