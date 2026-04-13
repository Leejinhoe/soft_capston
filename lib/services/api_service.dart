import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // 서버 주소 - 실제 서버 IP로 변경하세요
  static const String baseUrl = 'https://racemose-stenohaline-braelynn.ngrok-free.dev';

  static Future<Map<String, dynamic>> startStory({
    required String genre,
    required String age,
    required String prompt,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/story/start'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'genre': genre, 'age': age, 'prompt': prompt}),
    ).timeout(const Duration(seconds: 600));

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
    final response = await http.post(
      Uri.parse('$baseUrl/story/continue'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'story_id': storyId,
        'story_so_far': storySoFar,
        'choice': choice,
        'genre': genre,
        'age': age,
      }),
    ).timeout(const Duration(seconds: 600));

    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes));
    }
    throw Exception('이어쓰기 실패: ${response.statusCode}');
  }

  static Future<Map<String, dynamic>> analyzePsychology({
    required String storyId,
    required List<String> choicesMade,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/story/psych'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'story_id': storyId, 'choices_made': choicesMade}),
    ).timeout(const Duration(seconds: 300));

    if (response.statusCode == 200) {
      return json.decode(utf8.decode(response.bodyBytes));
    }
    throw Exception('심리 분석 실패: ${response.statusCode}');
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
