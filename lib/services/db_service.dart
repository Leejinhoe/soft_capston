import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

import '../models/admin_model.dart';
import '../models/story_model.dart';

class DbService {
  static const String _definedBaseUrl =
      String.fromEnvironment('DB_API_BASE_URL');
  static const String _definedTtsBaseUrl =
      String.fromEnvironment('TTS_API_BASE_URL');

  static String get baseUrl {
    final defined = _definedBaseUrl.trim();
    if (defined.isNotEmpty) return defined;

    final configured =
        dotenv.isInitialized ? dotenv.env['DB_API_BASE_URL']?.trim() ?? '' : '';
    if (configured.isNotEmpty) return configured;

    return 'http://127.0.0.1:8000';
  }

  static String get ttsBaseUrl {
    final defined = _definedTtsBaseUrl.trim();
    if (defined.isNotEmpty) return defined;

    final configured = dotenv.isInitialized
        ? dotenv.env['TTS_API_BASE_URL']?.trim() ?? ''
        : '';
    if (configured.isNotEmpty) return configured;

    return baseUrl;
  }

  static Uri _apiUri(String pathOrUrl) {
    final trimmed = pathOrUrl.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      return Uri.parse(trimmed);
    }

    final root = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final path = trimmed.startsWith('/') ? trimmed.substring(1) : trimmed;
    return Uri.parse('$root/$path');
  }

  static Uri _ttsUri(String path) {
    final root = ttsBaseUrl.endsWith('/')
        ? ttsBaseUrl.substring(0, ttsBaseUrl.length - 1)
        : ttsBaseUrl;
    final normalizedPath = path.startsWith('/') ? path.substring(1) : path;
    return Uri.parse('$root/$normalizedPath');
  }

  static String? _absoluteMediaUrl(String? pathOrUrl) {
    final trimmed = pathOrUrl?.trim();
    if (trimmed == null || trimmed.isEmpty) return null;
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      return trimmed;
    }
    if (trimmed.startsWith('file://') || trimmed.startsWith('mock://')) {
      return trimmed;
    }
    return _apiUri(trimmed).toString();
  }

  static SceneMediaResult _withAbsoluteMediaUrls(SceneMediaResult result) {
    return SceneMediaResult(
      imageUrl: _absoluteMediaUrl(result.imageUrl),
      videoUrl: _absoluteMediaUrl(result.videoUrl),
      provider: result.provider,
      elapsedSeconds: result.elapsedSeconds,
      saved: result.saved,
      jobId: result.jobId,
      status: result.status,
      statusUrl: result.statusUrl,
    );
  }

  static StorySession _withAbsoluteStoryMedia(StorySession story) {
    for (final chapter in story.chapters) {
      chapter.imageUrl = _absoluteMediaUrl(chapter.imageUrl);
      chapter.videoUrl = _absoluteMediaUrl(chapter.videoUrl);
    }
    return story;
  }

  static Future<bool> checkHealth() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  static Future<Uint8List> synthesizeNarration(
    String text, {
    Uint8List? speakerWav,
  }) async {
    late http.Response response;

    if (speakerWav == null || speakerWav.isEmpty) {
      response = await http
          .post(
            _ttsUri('/api/tts'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(const Duration(seconds: 180));
    } else {
      final request = http.MultipartRequest('POST', _ttsUri('/api/tts'))
        ..fields['text'] = text
        ..files.add(
          http.MultipartFile.fromBytes(
            'speaker_wav',
            speakerWav,
            filename: 'my_fairytale_voice.wav',
          ),
        );
      final streamed =
          await request.send().timeout(const Duration(seconds: 180));
      response = await http.Response.fromStream(streamed);
    }

    if (response.statusCode == 200) return response.bodyBytes;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '낭독 음성 생성 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>?> findUserByAccount(
    String accountId,
  ) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/users/by-account/$accountId'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  static Future<Map<String, dynamic>> registerUser({
    required String accountId,
    String? password,
    required String nickname,
    String? email,
    String? phone,
    String? address,
    String provider = 'local',
    String? providerId,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/users/register'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'account_id': accountId,
            'password': password,
            'nickname': nickname,
            'email': email,
            'phone': phone,
            'address': address,
            'provider': provider,
            'provider_id': providerId,
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '회원 저장 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>> loginUser({
    required String accountId,
    required String password,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/users/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'account_id': accountId, 'password': password}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(
      _extractDetailMessage(response.body) ?? '로그인 실패: ${response.statusCode}',
    );
  }

  static Future<AdminDashboard> fetchAdminDashboard({
    required String accountId,
  }) async {
    final response = await http.get(
      Uri.parse(
        '$baseUrl/api/admin/dashboard',
      ).replace(queryParameters: {'account_id': accountId}),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 20));

    if (response.statusCode == 200) {
      return AdminDashboard.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '관리자 데이터 조회 실패: ${response.statusCode}',
    );
  }

  static Future<bool> deleteAdminUser({
    required String adminAccountId,
    required String userId,
  }) async {
    final response = await http.delete(
      Uri.parse(
        '$baseUrl/api/admin/users/$userId',
      ).replace(queryParameters: {'account_id': adminAccountId}),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) return true;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '회원 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<bool> deleteAdminStory({
    required String adminAccountId,
    required String storyId,
  }) async {
    final response = await http.delete(
      Uri.parse(
        '$baseUrl/api/admin/stories/$storyId',
      ).replace(queryParameters: {'account_id': adminAccountId}),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) return true;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '동화 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<bool> deleteAdminVocabulary({
    required String adminAccountId,
    required String vocabId,
  }) async {
    final response = await http.delete(
      Uri.parse(
        '$baseUrl/api/admin/vocabularies/$vocabId',
      ).replace(queryParameters: {'account_id': adminAccountId}),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) return true;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '단어 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<bool> deleteAdminCommunityPost({
    required String adminAccountId,
    required String postId,
  }) async {
    final response = await http.delete(
      Uri.parse(
        '$baseUrl/api/admin/community/posts/$postId',
      ).replace(queryParameters: {'account_id': adminAccountId}),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) return true;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '게시글 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<AdminCommunityPost> updateAdminPostVisibility({
    required String adminAccountId,
    required String postId,
    required bool isHidden,
  }) async {
    final response = await http
        .patch(
          Uri.parse('$baseUrl/api/admin/community/posts/$postId/visibility'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'account_id': adminAccountId,
            'is_hidden': isHidden,
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return AdminCommunityPost.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '게시글 상태 변경 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>> updateUserProfile({
    required String accountId,
    String? nickname,
    String? email,
    String? phone,
    String? address,
  }) async {
    final response = await http
        .put(
          Uri.parse('$baseUrl/api/users/$accountId/profile'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'nickname': nickname?.trim(),
            'email': email?.trim(),
            'phone': phone?.trim(),
            'address': address?.trim(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '프로필 저장 실패: ${response.statusCode}',
    );
  }

  static Future<bool> changePassword({
    required String accountId,
    required String currentPassword,
    required String newPassword,
  }) async {
    final response = await http
        .patch(
          Uri.parse('$baseUrl/api/users/$accountId/password'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'current_password': currentPassword,
            'new_password': newPassword,
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) return true;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '비밀번호 변경 실패: ${response.statusCode}',
    );
  }

  static Future<String?> createStorySession({
    required String userId,
    required String title,
    required String genre,
    required String age,
    required String prompt,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/stories/create'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'user_id': userId,
              'title': title,
              'genre': genre,
              'age': age,
              'prompt': prompt,
              'created_at': DateTime.now().toUtc().toIso8601String(),
            }),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return data['story_id']?.toString();
      }
    } catch (_) {}
    return null;
  }

  static Future<bool> pushScene({
    required String storyId,
    required int stepNumber,
    required String storyText,
    String? choiceMade,
    String? imageUrl,
    String? videoUrl,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/stories/$storyId/scenes'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'step_number': stepNumber,
              'story_text': storyText,
              'choice_made': choiceMade,
              'image_url': imageUrl,
              'video_url': videoUrl,
              'created_at': DateTime.now().toUtc().toIso8601String(),
            }),
          )
          .timeout(const Duration(seconds: 15));
      return response.statusCode == 200 || response.statusCode == 201;
    } catch (_) {
      return false;
    }
  }

  static Future<SceneMediaResult?> generateSceneMedia({
    required String storyId,
    required int stepNumber,
    required String storyText,
    required String genre,
    required String age,
    bool includeVideo = false,
  }) async {
    try {
      final response = await http
          .post(
            _apiUri('/api/stories/$storyId/scenes/$stepNumber/media/jobs'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'story_text': storyText,
              'genre': genre,
              'age': age,
              'include_video': includeVideo,
            }),
          )
          .timeout(const Duration(seconds: 20));

      if (response.statusCode == 200 ||
          response.statusCode == 201 ||
          response.statusCode == 202) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final media = await _pollSceneMediaJob(data);
        return media == null ? null : _withAbsoluteMediaUrls(media);
      }

      if (response.statusCode == 404) {
        return _generateSceneMediaSync(
          storyId: storyId,
          stepNumber: stepNumber,
          storyText: storyText,
          genre: genre,
          age: age,
          includeVideo: includeVideo,
        );
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  static Future<SceneMediaResult?> _pollSceneMediaJob(
    Map<String, dynamic> initialJob,
  ) async {
    var latest = _withAbsoluteMediaUrls(SceneMediaResult.fromJson(initialJob));
    if (latest.hasMedia) return latest;

    final pollPathOrUrl = _sceneMediaJobStatusPath(latest);
    if (pollPathOrUrl == null) return null;

    final deadline = DateTime.now().add(const Duration(minutes: 20));
    while (DateTime.now().isBefore(deadline)) {
      final status = latest.status?.toLowerCase();
      if (status == 'completed') return latest.hasMedia ? latest : null;
      if (status == 'failed') return null;

      await Future.delayed(const Duration(seconds: 3));
      try {
        final response = await http.get(
          _apiUri(pollPathOrUrl),
          headers: {'Content-Type': 'application/json'},
        ).timeout(const Duration(seconds: 20));
        if (response.statusCode == 404) return null;
        if (response.statusCode >= 500) continue;
        if (response.statusCode >= 400) return null;

        latest = _withAbsoluteMediaUrls(
          SceneMediaResult.fromJson(
            jsonDecode(response.body) as Map<String, dynamic>,
          ),
        );
        if (latest.hasMedia) return latest;
      } catch (_) {}
    }

    return null;
  }

  static String? _sceneMediaJobStatusPath(SceneMediaResult job) {
    final statusUrl = job.statusUrl?.trim();
    if (statusUrl != null && statusUrl.isNotEmpty) {
      return statusUrl;
    }

    final jobId = job.jobId?.trim();
    if (jobId != null && jobId.isNotEmpty) {
      return '/api/media/jobs/$jobId';
    }

    return null;
  }

  static Future<SceneMediaResult?> _generateSceneMediaSync({
    required String storyId,
    required int stepNumber,
    required String storyText,
    required String genre,
    required String age,
    required bool includeVideo,
  }) async {
    try {
      final response = await http
          .post(
            _apiUri('/api/stories/$storyId/scenes/$stepNumber/media/generate'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'story_text': storyText,
              'genre': genre,
              'age': age,
              'include_video': includeVideo,
            }),
          )
          .timeout(const Duration(minutes: 10));

      if (response.statusCode == 200 ||
          response.statusCode == 201 ||
          response.statusCode == 202) {
        return _withAbsoluteMediaUrls(
          SceneMediaResult.fromJson(
            jsonDecode(response.body) as Map<String, dynamic>,
          ),
        );
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  static Future<String?> addVocabulary({
    required String userId,
    required String storyId,
    required VocabWord word,
    String? sourceStoryTitle,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/vocabularies/add'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'user_id': userId,
              'origin_story_id': storyId,
              'hard': word.hard,
              'easy': word.easy,
              'definition': word.definition,
              'source_story_title': sourceStoryTitle,
              'created_at': DateTime.now().toUtc().toIso8601String(),
            }),
          )
          .timeout(const Duration(seconds: 15));
      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return data['id']?.toString();
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  static Future<bool> deleteStory({
    required String storyId,
    String? userId,
  }) async {
    final response = await http
        .delete(
          Uri.parse('$baseUrl/api/stories/$storyId'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'user_id': userId}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) {
      return true;
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '동화 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<StorySession> updateStoryTitle({
    required String storyId,
    required String title,
    String? userId,
  }) async {
    final response = await http
        .patch(
          Uri.parse('$baseUrl/api/stories/$storyId'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'user_id': userId, 'title': title}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return _withAbsoluteStoryMedia(
        StorySession.fromDatabaseJson(
          jsonDecode(response.body) as Map<String, dynamic>,
        ),
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '동화 제목 수정 실패: ${response.statusCode}',
    );
  }

  static Future<bool> deleteVocabulary({
    required String vocabId,
    String? userId,
  }) async {
    final response = await http
        .delete(
          Uri.parse('$baseUrl/api/vocabularies/$vocabId'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'user_id': userId}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) {
      return true;
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '단어 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<List<StorySession>> fetchUserStories(String userId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/users/$userId/stories'),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final stories = data['stories'] as List? ?? const [];
      return stories
          .map(
            (e) => _withAbsoluteStoryMedia(
              StorySession.fromDatabaseJson(e as Map<String, dynamic>),
            ),
          )
          .where((story) => story.chapters.isNotEmpty)
          .toList();
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '동화 기록 불러오기 실패: ${response.statusCode}',
    );
  }

  static Future<List<VocabWord>> fetchUserVocabularies(String userId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/users/$userId/vocabularies'),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final vocabularies = data['vocabularies'] as List? ?? const [];
      return vocabularies
          .map((e) => VocabWord.fromJson(e as Map<String, dynamic>))
          .where((word) => word.hard.trim().isNotEmpty)
          .toList();
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '단어장 불러오기 실패: ${response.statusCode}',
    );
  }

  static Future<List<CommunityPost>> fetchCommunityPosts({
    String sort = 'latest',
  }) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/community/posts?sort=$sort'),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final posts = data['posts'] as List? ?? const [];
      return posts
          .map((e) => CommunityPost.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    throw Exception('게시글 불러오기 실패: ${response.statusCode}');
  }

  static Future<CommunityPost> createCommunityPost({
    required String authorName,
    String? authorAccountId,
    String? storyId,
    required String genre,
    required String title,
    required String preview,
    required String fullText,
    required String storyEmoji,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/community/posts'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'author_name': authorName,
            'author_account_id': authorAccountId,
            'story_id': storyId,
            'genre': genre,
            'title': title,
            'preview': preview,
            'full_text': fullText,
            'story_emoji': storyEmoji,
            'created_at': DateTime.now().toUtc().toIso8601String(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      return CommunityPost.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception('게시글 공유 실패: ${response.statusCode}');
  }

  static Future<CommunityPost> fetchCommunityPostDetail(String postId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/community/posts/$postId'),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return CommunityPost.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception('게시글 조회 실패: ${response.statusCode}');
  }

  static Future<CommunityPost> likeCommunityPost({
    required String postId,
    String? accountId,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/community/posts/$postId/like'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'account_id': accountId}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      return CommunityPost.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '좋아요 저장 실패: ${response.statusCode}',
    );
  }

  static Future<bool> deleteCommunityPost({
    required String postId,
    String? accountId,
  }) async {
    final response = await http
        .delete(
          Uri.parse('$baseUrl/api/community/posts/$postId'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'account_id': accountId}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 204) {
      return true;
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '게시글 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<CommunityPost> deleteCommunityComment({
    required String postId,
    required String commentId,
    String? accountId,
  }) async {
    final response = await http
        .delete(
          Uri.parse('$baseUrl/api/community/posts/$postId/comments/$commentId'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'account_id': accountId}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      return CommunityPost.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '댓글 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<CommunityPost> addCommunityComment({
    required String postId,
    required String authorName,
    String? authorAccountId,
    required String content,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/community/posts/$postId/comments'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'author_name': authorName,
            'author_account_id': authorAccountId,
            'content': content,
            'created_at': DateTime.now().toUtc().toIso8601String(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      return CommunityPost.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception('댓글 저장 실패: ${response.statusCode}');
  }

  static String? _extractDetailMessage(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        final detail = decoded['detail'];
        if (detail is String && detail.trim().isNotEmpty) return detail;
        final message = decoded['message'];
        if (message is String && message.trim().isNotEmpty) return message;
      }
    } catch (_) {}
    return null;
  }
}
