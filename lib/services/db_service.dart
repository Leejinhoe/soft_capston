import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../models/admin_model.dart';
import '../models/character_profile.dart';
import '../models/media_readiness.dart';
import '../models/moderation_model.dart';
import '../models/notice_model.dart';
import '../models/story_model.dart';

class DbService {
  static String? _accessToken;
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  static const String _accessTokenKey = 'fairytale.access_token';
  static const String _sessionUserKey = 'fairytale.session_user';

  static Future<void> setAccessToken(String? token) async {
    final normalized = token?.trim();
    _accessToken = normalized == null || normalized.isEmpty ? null : normalized;
    try {
      if (_accessToken == null) {
        await _secureStorage.delete(key: _accessTokenKey);
      } else {
        await _secureStorage.write(key: _accessTokenKey, value: _accessToken);
      }
    } catch (error) {
      debugPrint('Could not persist login token: $error');
    }
  }

  static void clearAccessToken() {
    _accessToken = null;
    unawaited(_deletePersistedSession());
  }

  static Future<void> _deletePersistedSession() async {
    try {
      await _secureStorage.delete(key: _accessTokenKey);
      await _secureStorage.delete(key: _sessionUserKey);
    } catch (error) {
      debugPrint('Could not clear saved login session: $error');
    }
  }

  static Future<Map<String, dynamic>?> restoreSession() async {
    String? token;
    Map<String, dynamic>? cachedUser;
    try {
      token = await _secureStorage.read(key: _accessTokenKey);
      final cachedJson = await _secureStorage.read(key: _sessionUserKey);
      if (cachedJson != null) {
        final decoded = jsonDecode(cachedJson);
        if (decoded is Map<String, dynamic>) cachedUser = decoded;
      }
    } catch (error) {
      debugPrint('Could not read saved login session: $error');
      return null;
    }

    if (token == null || token.trim().isEmpty) return null;
    _accessToken = token;

    try {
      final response = await http
          .get(_apiUri('/api/auth/session'), headers: _jsonHeaders)
          .timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final user = jsonDecode(response.body) as Map<String, dynamic>;
        await persistSessionUser(user);
        return user;
      }
      if (response.statusCode == 401 || response.statusCode == 403) {
        clearAccessToken();
        return null;
      }
      return cachedUser;
    } catch (error) {
      debugPrint('Session validation unavailable; using saved profile: $error');
      return cachedUser;
    }
  }

  static Future<void> persistSessionUser(Map<String, dynamic> user) async {
    final snapshot = <String, dynamic>{
      for (final key in const [
        'id',
        'account_id',
        'nickname',
        'provider',
        'email',
        'phone',
        'address',
      ])
        if (user[key] != null) key: user[key],
    };
    try {
      await _secureStorage.write(
        key: _sessionUserKey,
        value: jsonEncode(snapshot),
      );
    } catch (error) {
      debugPrint('Could not persist saved profile: $error');
    }
  }

  static Map<String, String> get _jsonHeaders {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (_accessToken != null) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    return headers;
  }

  static Map<String, String> get mediaHeaders {
    if (_accessToken == null) return const <String, String>{};
    return <String, String>{'Authorization': 'Bearer $_accessToken'};
  }

  static const String _definedBaseUrl = String.fromEnvironment(
    'DB_API_BASE_URL',
  );
  static const String _definedTtsBaseUrl = String.fromEnvironment(
    'TTS_API_BASE_URL',
  );

  static String get baseUrl {
    final defined = _definedBaseUrl.trim();
    if (defined.isNotEmpty) return _withoutTrailingSlash(defined);

    final configured = dotenv.isInitialized
        ? dotenv.env['DB_API_BASE_URL']?.trim() ?? ''
        : '';
    if (configured.isNotEmpty) return _withoutTrailingSlash(configured);

    if (kIsWeb) return 'http://127.0.0.1:8000';
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  static String _withoutTrailingSlash(String value) =>
      value.endsWith('/') ? value.substring(0, value.length - 1) : value;

  static String get ttsBaseUrl {
    final defined = _definedTtsBaseUrl.trim();
    if (defined.isNotEmpty) return _withoutTrailingSlash(defined);

    final configured = dotenv.isInitialized
        ? dotenv.env['TTS_API_BASE_URL']?.trim() ?? ''
        : '';
    if (configured.isNotEmpty) return _withoutTrailingSlash(configured);

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

  static String? resolveMediaUrl(String? pathOrUrl) =>
      _absoluteMediaUrl(pathOrUrl);

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
      error: result.error,
      includeVideoRequested: result.includeVideoRequested,
      videoStatus: result.videoStatus,
    );
  }

  static StorySession _withAbsoluteStoryMedia(StorySession story) {
    story.assembledVideoUrl = _absoluteMediaUrl(story.assembledVideoUrl);
    for (final chapter in story.chapters) {
      chapter.imageUrl = _absoluteMediaUrl(chapter.imageUrl);
      chapter.videoUrl = _absoluteMediaUrl(chapter.videoUrl);
    }
    return story;
  }

  static Future<String> assembleStoryVideo(String storyId) async {
    final response = await http
        .post(
          _apiUri('/api/stories/$storyId/journey-video'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(minutes: 5));
    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(response.body) ?? '동화 영상을 만들지 못했어요.',
      );
    }
    final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map;
    final url = _absoluteMediaUrl(data['video_url']?.toString());
    if (url == null) throw Exception('동화 영상 주소가 없습니다.');
    return url;
  }

  static Future<List<Map<String, dynamic>>> fetchJourneyVideoStatuses(
    String userId,
  ) async {
    final response = await http
        .get(
          _apiUri('/api/users/$userId/journey-videos'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
            '동화 영상 상태를 불러오지 못했어요: ${response.statusCode}',
      );
    }
    final data = jsonDecode(utf8.decode(response.bodyBytes));
    final items = data is Map ? data['videos'] : null;
    if (items is! List) return const [];
    return items
        .whereType<Map>()
        .map(
          (item) => <String, dynamic>{
            ...Map<String, dynamic>.from(item),
            'video_url': _absoluteMediaUrl(item['video_url']?.toString()),
          },
        )
        .toList();
  }

  static Future<Map<String, dynamic>> fetchJourneyVideoStatus(
    String storyId,
  ) async {
    final response = await http
        .get(
          _apiUri('/api/stories/$storyId/journey-video/status'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));
    final body = utf8.decode(response.bodyBytes);
    if (response.statusCode != 200) {
      throw Exception(_extractDetailMessage(body) ?? '동화 영상 상태를 불러오지 못했어요.');
    }
    final decoded = jsonDecode(body);
    if (decoded is! Map) {
      throw const FormatException('Invalid video status response');
    }
    return <String, dynamic>{
      ...Map<String, dynamic>.from(decoded),
      'video_url': _absoluteMediaUrl(decoded['video_url']?.toString()),
    };
  }

  static Future<Map<String, dynamic>> retryJourneyVideo(String storyId) async {
    final response = await http
        .post(
          _apiUri('/api/stories/$storyId/journey-video/retry'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));
    final body = utf8.decode(response.bodyBytes);
    if (response.statusCode != 200 && response.statusCode != 202) {
      throw Exception(_extractDetailMessage(body) ?? '동화 영상 작업을 시작하지 못했어요.');
    }
    final decoded = jsonDecode(body);
    if (decoded is! Map) {
      throw const FormatException('Invalid video job response');
    }
    return <String, dynamic>{
      ...Map<String, dynamic>.from(decoded),
      'video_url': _absoluteMediaUrl(decoded['video_url']?.toString()),
    };
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

  static Future<Uint8List?> loadVoiceSample() async {
    final response = await http
        .get(_apiUri('/api/users/me/voice-sample'), headers: mediaHeaders)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode == 404) return null;
    if (response.statusCode != 200) throw Exception('저장된 목소리를 불러오지 못했어요.');
    return response.bodyBytes;
  }

  static Future<void> saveVoiceSample(Uint8List wav) async {
    final response = await http
        .put(
          _apiUri('/api/users/me/voice-sample'),
          headers: {...mediaHeaders, 'Content-Type': 'audio/wav'},
          body: wav,
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) throw Exception('목소리를 계정에 저장하지 못했어요.');
  }

  static Future<void> deleteVoiceSample() async {
    final response = await http
        .delete(_apiUri('/api/users/me/voice-sample'), headers: mediaHeaders)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) throw Exception('저장된 목소리를 삭제하지 못했어요.');
  }

  static Future<Map<String, dynamic>> listVoiceSamples() async {
    final response = await http
        .get(_apiUri('/api/users/me/voice-samples'), headers: mediaHeaders)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) throw Exception('목소리 목록을 불러오지 못했어요.');
    return Map<String, dynamic>.from(
      jsonDecode(utf8.decode(response.bodyBytes)) as Map,
    );
  }

  static Future<Uint8List?> loadSelectedVoiceSample() async {
    final data = await listVoiceSamples();
    final selected = data['selected_id']?.toString() ?? 'default';
    if (selected == 'default') return null;
    return loadVoiceSampleById(selected);
  }

  static Future<Uint8List> loadVoiceSampleById(String id) async {
    final response = await http
        .get(
          _apiUri(
            '/api/users/me/voice-samples/${Uri.encodeComponent(id)}/audio',
          ),
          headers: mediaHeaders,
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) throw Exception('목소리를 불러오지 못했어요.');
    return response.bodyBytes;
  }

  static Future<String> addVoiceSample(Uint8List wav, String name) async {
    final request =
        http.MultipartRequest(
            'POST',
            _apiUri(
              '/api/users/me/voice-samples',
            ).replace(queryParameters: {'name': name}),
          )
          ..headers.addAll(mediaHeaders)
          ..files.add(
            http.MultipartFile.fromBytes(
              'audio',
              wav,
              filename: 'voice.wav',
              contentType: MediaType('audio', 'wav'),
            ),
          );
    final response = await http.Response.fromStream(
      await request.send().timeout(const Duration(seconds: 20)),
    ).timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) throw Exception('목소리를 저장하지 못했어요.');
    return (jsonDecode(utf8.decode(response.bodyBytes)) as Map)['id']
        .toString();
  }

  static Future<void> selectVoiceSample(String id) async {
    final response = await http
        .put(
          _apiUri('/api/users/me/voice-samples/selection'),
          headers: _jsonHeaders,
          body: jsonEncode({'id': id}),
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) throw Exception('목소리를 선택하지 못했어요.');
  }

  static Future<void> deleteVoiceSampleById(String id) async {
    final response = await http
        .delete(
          _apiUri('/api/users/me/voice-samples/${Uri.encodeComponent(id)}'),
          headers: mediaHeaders,
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) throw Exception('목소리를 삭제하지 못했어요.');
  }

  static Future<Uint8List> synthesizeNarration(
    String text, {
    Uint8List? speakerWav,
    String? voiceGender,
  }) async {
    late http.Response response;

    if (speakerWav == null || speakerWav.isEmpty) {
      response = await http
          .post(
            _ttsUri('/api/tts'),
            headers: _jsonHeaders,
            body: jsonEncode({
              'text': text,
              if (voiceGender != null && voiceGender.isNotEmpty)
                'voice_gender': voiceGender,
            }),
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
      final streamed = await request.send().timeout(
        const Duration(seconds: 180),
      );
      // send() only waits for the response headers. Bound the body read too,
      // otherwise a stalled tunnel can leave narration showing as "generating"
      // forever after XTTS has already finished.
      response = await http.Response.fromStream(
        streamed,
      ).timeout(const Duration(seconds: 180));
    }

    if (response.statusCode == 200) return response.bodyBytes;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '낭독 음성 생성 실패: ${response.statusCode}',
    );
  }

  /// Prepares XTTS while the voice conversation is listening to its first turn.
  static Future<void> warmUpNarration() async {
    final response = await http
        .post(_ttsUri('/api/tts/warm-up'), headers: _jsonHeaders)
        .timeout(const Duration(seconds: 120));
    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(response.body) ?? '음성 합성 준비에 실패했어요.',
      );
    }
  }

  static Future<Map<String, dynamic>?> findUserByAccount(
    String accountId,
  ) async {
    try {
      final response = await http
          .get(
            Uri.parse('$baseUrl/api/users/by-account/$accountId'),
            headers: _jsonHeaders,
          )
          .timeout(const Duration(seconds: 10));

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
    String? birth,
    String? phone,
    String? address,
    String provider = 'local',
    String? providerId,
    String? emailVerificationToken,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/users/register'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'account_id': accountId,
            'password': password,
            'nickname': nickname,
            'email': email,
            'birth': birth,
            'phone': phone,
            'address': address,
            'provider': provider,
            'provider_id': providerId,
            'email_verification_token': emailVerificationToken,
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      await setAccessToken(data['access_token']?.toString());
      return data;
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '회원 저장 실패: ${response.statusCode}',
    );
  }

  static Future<bool> isSignupIdAvailable(String accountId) async {
    final response = await http
        .post(
          _apiUri('/api/users/check-id'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'account_id': accountId.trim()}),
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(response.body) ?? '아이디를 확인하지 못했어요.',
      );
    }
    return (jsonDecode(response.body) as Map<String, dynamic>)['available'] ==
        true;
  }

  static Future<Map<String, dynamic>> loginWithSocialToken({
    required String provider,
    required String token,
    String? tokenType,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/auth/social/$provider'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'token': token,
            if (tokenType != null) 'token_type': tokenType,
          }),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception(_extractDetailMessage(response.body) ?? '소셜 로그인에 실패했어요.');
    }
    final data =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    await setAccessToken(data['access_token']?.toString());
    return data;
  }

  static Future<void> sendEmailVerificationCode({required String email}) async {
    final response = await http
        .post(
          _apiUri('/api/auth/email-verifications/send'),
          headers: _jsonHeaders,
          body: jsonEncode({'email': email.trim()}),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200 || response.statusCode == 201) return;
    throw Exception(_extractDetailMessage(response.body) ?? '인증번호 발송에 실패했어요.');
  }

  static Future<String> confirmEmailVerificationCode({
    required String email,
    required String code,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/auth/email-verifications/verify'),
          headers: _jsonHeaders,
          body: jsonEncode({'email': email.trim(), 'code': code.trim()}),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['verification_token']?.toString().trim() ?? '';
      if (token.isNotEmpty) return token;
    }
    throw Exception(_extractDetailMessage(response.body) ?? '인증번호 확인에 실패했어요.');
  }

  static Future<void> requestPasswordResetCode({
    required String accountId,
    required String email,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/auth/password-reset/request'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'account_id': accountId.trim(),
            'email': email.trim(),
          }),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) return;
    throw Exception(_extractDetailMessage(response.body) ?? '인증번호 발송에 실패했어요.');
  }

  static Future<String> verifyPasswordResetCode({
    required String accountId,
    required String email,
    required String code,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/auth/password-reset/verify'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'account_id': accountId.trim(),
            'email': email.trim(),
            'code': code.trim(),
          }),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = data['reset_token']?.toString().trim() ?? '';
      if (token.isNotEmpty) return token;
    }
    throw Exception(_extractDetailMessage(response.body) ?? '인증번호 확인에 실패했어요.');
  }

  static Future<void> confirmPasswordReset({
    required String resetToken,
    required String newPassword,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/auth/password-reset/confirm'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'reset_token': resetToken,
            'new_password': newPassword,
          }),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) return;
    throw Exception(_extractDetailMessage(response.body) ?? '비밀번호 변경에 실패했어요.');
  }

  static Future<Map<String, dynamic>> loginUser({
    required String accountId,
    required String password,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/users/login'),
          headers: _jsonHeaders,
          body: jsonEncode({'account_id': accountId, 'password': password}),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      await setAccessToken(data['access_token']?.toString());
      return data;
    }
    throw Exception(
      _extractDetailMessage(response.body) ?? '로그인 실패: ${response.statusCode}',
    );
  }

  static Future<AdminDashboard> fetchAdminDashboard({
    required String accountId,
  }) async {
    final response = await http
        .get(
          Uri.parse(
            '$baseUrl/api/admin/dashboard',
          ).replace(queryParameters: {'account_id': accountId}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));

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

  static Future<List<Notice>> fetchNotices({int limit = 500}) async {
    final response = await http
        .get(
          _apiUri('/api/notices').replace(queryParameters: {'limit': '$limit'}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode == 200) {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      return (body['notices'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Notice.fromJson(Map<String, dynamic>.from(item)))
          .toList(growable: false);
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '공지사항 조회 실패: ${response.statusCode}',
    );
  }

  static Future<Notice> createAdminNotice({
    required String adminAccountId,
    required String title,
    required String content,
    required bool isPinned,
    required bool sendEmail,
    String target = 'all',
    List<String> userIds = const [],
  }) async {
    final response = await http
        .post(
          _apiUri('/api/admin/notices'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'account_id': adminAccountId,
            'title': title,
            'content': content,
            'is_pinned': isPinned,
            'send_email': sendEmail,
            'target': target,
            'user_ids': userIds,
          }),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Notice.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '공지사항 등록 실패: ${response.statusCode}',
    );
  }

  static Future<Notice> updateAdminNotice({
    required String adminAccountId,
    required String noticeId,
    required String title,
    required String content,
    required bool isPinned,
    String? target,
    List<String>? userIds,
  }) async {
    final response = await http
        .patch(
          _apiUri('/api/admin/notices/$noticeId'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'account_id': adminAccountId,
            'title': title,
            'content': content,
            'is_pinned': isPinned,
            if (target != null) 'target': target,
            if (userIds != null) 'user_ids': userIds,
          }),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) {
      return Notice.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '공지사항 수정 실패: ${response.statusCode}',
    );
  }

  static Future<Notice> sendAdminNoticeEmail({
    required String adminAccountId,
    required String noticeId,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/admin/notices/$noticeId/email'),
          headers: _jsonHeaders,
          body: jsonEncode({'account_id': adminAccountId}),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) {
      return Notice.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '공지 메일 발송 요청 실패: ${response.statusCode}',
    );
  }

  static Future<void> deleteAdminNotice({
    required String adminAccountId,
    required String noticeId,
  }) async {
    final response = await http
        .delete(
          _apiUri(
            '/api/admin/notices/$noticeId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode == 200 || response.statusCode == 204) return;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '공지사항 삭제 실패: ${response.statusCode}',
    );
  }

  static Future<MediaReadiness> fetchMediaReadiness() async {
    final response = await http
        .get(_apiUri('/api/media/readiness'), headers: _jsonHeaders)
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return MediaReadiness.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '미디어 준비 현황 조회 실패: ${response.statusCode}',
    );
  }

  static Future<List<CharacterProfile>> fetchCharacterProfiles() async {
    final response = await http
        .get(
          _apiUri('/api/media/characters?active_only=true'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(response.body) ??
            '캐릭터 프로필을 불러오지 못했습니다: ${response.statusCode}',
      );
    }

    final decoded = jsonDecode(response.body);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map>()
        .map(
          (item) => CharacterProfile.fromJson(Map<String, dynamic>.from(item)),
        )
        .where((profile) => profile.characterKey.isNotEmpty)
        .toList(growable: false);
  }

  static Future<bool> deleteAdminUser({
    required String adminAccountId,
    required String userId,
  }) async {
    final response = await http
        .delete(
          Uri.parse(
            '$baseUrl/api/admin/users/$userId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
    final response = await http
        .delete(
          Uri.parse(
            '$baseUrl/api/admin/stories/$storyId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
    final response = await http
        .delete(
          Uri.parse(
            '$baseUrl/api/admin/vocabularies/$vocabId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
    final response = await http
        .delete(
          Uri.parse(
            '$baseUrl/api/admin/community/posts/$postId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
          headers: _jsonHeaders,
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
    String? emailVerificationToken,
    String? phone,
    String? address,
  }) async {
    final response = await http
        .put(
          Uri.parse('$baseUrl/api/users/$accountId/profile'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'nickname': nickname?.trim(),
            'email': email?.trim(),
            'email_verification_token': emailVerificationToken?.trim(),
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
          headers: _jsonHeaders,
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

  static Future<Map<String, dynamic>> fetchAdminStoryDetail(
    String storyId,
  ) async {
    final response = await http
        .get(
          _apiUri('/api/admin/stories/${Uri.encodeComponent(storyId)}'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception(_extractDetailMessage(response.body) ?? '동화를 불러오지 못했어요.');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  static Future<void> updateAdminUserStatus({
    required String userId,
    required String status,
    String reason = '',
  }) async {
    final response = await http
        .patch(
          _apiUri('/api/admin/users/${Uri.encodeComponent(userId)}/status'),
          headers: _jsonHeaders,
          body: jsonEncode({'status': status, 'reason': reason}),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(response.body) ?? '계정 상태 변경에 실패했어요.',
      );
    }
  }

  static Future<ReportSubmissionResult> createCommunityReport({
    required String targetType,
    required String targetId,
    required String reason,
    String? reporterAccountId,
    String? postId,
    String? details,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/community/reports'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'reporter_account_id': reporterAccountId?.trim(),
            'target_type': targetType,
            'target_id': targetId,
            'post_id': postId,
            'reason': reason.trim(),
            'details': details?.trim(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      return ReportSubmissionResult.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>,
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '신고 접수에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<List<ModerationReport>> fetchAdminReports({
    required String adminAccountId,
    String? status,
  }) async {
    final query = <String, String>{'account_id': adminAccountId};
    if (status != null && status.isNotEmpty) query['status'] = status;
    final response = await http
        .get(
          _apiUri('/api/admin/reports').replace(queryParameters: query),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return (data['reports'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ModerationReport.fromJson)
          .toList();
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '신고 목록 조회에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<List<UserWarning>> fetchAdminWarnings({
    required String adminAccountId,
    String? userId,
  }) async {
    final query = <String, String>{'account_id': adminAccountId};
    if (userId != null && userId.isNotEmpty) query['user_id'] = userId;
    final response = await http
        .get(
          _apiUri('/api/admin/warnings').replace(queryParameters: query),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return (data['warnings'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(UserWarning.fromJson)
          .toList();
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '경고 목록 조회에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<UserWarning> createAdminWarning({
    required String adminAccountId,
    required String userId,
    required String reason,
    String severity = 'notice',
    DateTime? expiresAt,
  }) async {
    final response = await http
        .post(
          _apiUri(
            '/api/admin/users/$userId/warnings',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
          body: jsonEncode({
            'reason': reason.trim(),
            'severity': severity,
            'expires_at': expiresAt?.toUtc().toIso8601String(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return UserWarning.fromJson(
        data['warning'] as Map<String, dynamic>? ?? const {},
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '경고 등록에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<UserWarning> resolveAdminWarning({
    required String adminAccountId,
    required String warningId,
    required String status,
    String? resolutionNote,
  }) async {
    final response = await http
        .patch(
          _apiUri(
            '/api/admin/warnings/$warningId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
          body: jsonEncode({
            'status': status,
            'resolution_note': resolutionNote?.trim(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return UserWarning.fromJson(
        data['warning'] as Map<String, dynamic>? ?? const {},
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '경고 처리에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<ModerationReport> resolveAdminReport({
    required String adminAccountId,
    required String reportId,
    required String status,
    String? actionTaken,
    String? resolutionNote,
  }) async {
    final response = await http
        .patch(
          _apiUri(
            '/api/admin/reports/$reportId',
          ).replace(queryParameters: {'account_id': adminAccountId}),
          headers: _jsonHeaders,
          body: jsonEncode({
            'status': status,
            'action_taken': actionTaken,
            'resolution_note': resolutionNote?.trim(),
          }),
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return ModerationReport.fromJson(
        data['report'] as Map<String, dynamic>? ?? const {},
      );
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '신고 처리에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<void> withdrawAccount({
    required String accountId,
    String? password,
    String? reason,
  }) async {
    final request = http.Request('DELETE', _apiUri('/api/users/$accountId'))
      ..headers.addAll(_jsonHeaders)
      ..body = jsonEncode({'password': password, 'reason': reason?.trim()});
    final streamed = await request.send().timeout(const Duration(seconds: 20));
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 200 || response.statusCode == 204) return;
    throw Exception(
      _extractDetailMessage(response.body) ??
          '회원 탈퇴에 실패했습니다: ${response.statusCode}',
    );
  }

  static Future<String?> createStorySession({
    required String userId,
    required String title,
    required String genre,
    required String age,
    required String prompt,
    Map<String, String> characters = const {},
    Map<String, String> characterOverrides = const {},
    required String aiStoryId,
    String? runtimeState,
    List<String> pendingChoices = const [],
    List<Map<String, dynamic>> pendingChoiceEmotions = const [],
    int readProgress = 1,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/stories/create'),
            headers: _jsonHeaders,
            body: jsonEncode({
              'user_id': userId,
              'title': title,
              'genre': genre,
              'age': age,
              'prompt': prompt,
              'characters': characters,
              'character_overrides': characterOverrides,
              'ai_story_id': aiStoryId,
              'runtime_state': runtimeState,
              'pending_choices': pendingChoices,
              'pending_choice_emotions': pendingChoiceEmotions,
              'read_progress': readProgress,
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

  static Future<bool> saveStoryReadingState({
    required String storyId,
    required String aiStoryId,
    String? runtimeState,
    required List<String> pendingChoices,
    required List<Map<String, dynamic>> pendingChoiceEmotions,
    required int readProgress,
    required bool completed,
  }) async {
    try {
      final response = await http
          .put(
            _apiUri('/api/stories/$storyId/reading-state'),
            headers: _jsonHeaders,
            body: jsonEncode({
              'ai_story_id': aiStoryId,
              'runtime_state': runtimeState,
              'pending_choices': pendingChoices,
              'pending_choice_emotions': pendingChoiceEmotions,
              'read_progress': readProgress,
              'completed': completed,
            }),
          )
          .timeout(const Duration(seconds: 20));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  static Future<bool> saveStoryCharacters({
    required String storyId,
    required Map<String, String> characters,
    Map<String, String>? characterOverrides,
    String? userId,
  }) async {
    final body = <String, dynamic>{'characters': characters, 'user_id': userId};
    if (characterOverrides != null) {
      body['character_overrides'] = characterOverrides;
    }
    final response = await http
        .put(
          Uri.parse('$baseUrl/api/stories/$storyId/characters'),
          headers: _jsonHeaders,
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 20));
    return response.statusCode == 200;
  }

  static Future<bool> pushScene({
    required String storyId,
    required int stepNumber,
    required String storyText,
    String? choiceMade,
    List<String> offeredChoices = const [],
    Map<String, dynamic>? sceneContract,
    Map<String, dynamic>? selectedChoiceEmotion,
    Map<String, dynamic>? storyEmotion,
    String? imageUrl,
    String? videoUrl,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/api/stories/$storyId/scenes'),
            headers: _jsonHeaders,
            body: jsonEncode({
              'step_number': stepNumber,
              'story_text': storyText,
              'choice_made': choiceMade,
              'offered_choices': offeredChoices,
              'scene_contract': sceneContract,
              'selected_choice_emotion': selectedChoiceEmotion,
              'story_emotion': storyEmotion,
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

  static SceneMediaResult _mediaFailure(
    String message, {
    String? jobId,
    String context = 'request',
  }) {
    debugPrint('[scene-media][$context] $message');
    return SceneMediaResult(jobId: jobId, status: 'failed', error: message);
  }

  static String _mediaHttpError(http.Response response, String operation) {
    final detail = _extractDetailMessage(response.body);
    final suffix = detail == null ? '' : ': $detail';
    return '$operation 실패 (HTTP ${response.statusCode})$suffix';
  }

  static Future<SceneMediaResult?> generateSceneMedia({
    required String storyId,
    required int stepNumber,
    required String storyText,
    required String genre,
    required String age,
    String? characterKey,
    Map<String, dynamic>? sceneContract,
    bool includeVideo = false,
    String? resumeJobId,
  }) async {
    if (resumeJobId != null && resumeJobId.isNotEmpty) {
      return await _pollSceneMediaJob({
            'job_id': resumeJobId,
            'status': 'pending',
          }) ??
          _mediaFailure(
            '저장된 미디어 작업 상태를 확인하지 못했습니다.',
            jobId: resumeJobId,
            context: '$storyId/$stepNumber',
          );
    }

    final endpoint = _apiUri(
      '/api/stories/$storyId/scenes/$stepNumber/media/jobs',
    );
    http.Response response;
    for (var attempt = 0; ; attempt++) {
      try {
        response = await http
            .post(
              endpoint,
              headers: _jsonHeaders,
              body: jsonEncode({
                'story_text': storyText,
                'genre': genre,
                'age': age,
                if (characterKey?.trim().isNotEmpty == true)
                  'character_key': characterKey!.trim(),
                'scene_contract': ?sceneContract,
                'include_video': includeVideo,
              }),
            )
            .timeout(const Duration(seconds: 20));
      } catch (error) {
        return _mediaFailure(
          '미디어 API 연결 실패: $error',
          context: '$storyId/$stepNumber',
        );
      }

      if (response.statusCode != 429 || attempt >= 5) break;
      final delaySeconds = attempt < 4 ? (2 << attempt) : 30;
      debugPrint(
        '[scene-media][$storyId/$stepNumber] queue busy (HTTP 429); '
        'retry ${attempt + 1}/5 in ${delaySeconds}s',
      );
      await Future<void>.delayed(Duration(seconds: delaySeconds));
    }

    if (response.statusCode == 200 ||
        response.statusCode == 201 ||
        response.statusCode == 202) {
      try {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final media = await _pollSceneMediaJob(data);
        return media == null
            ? _mediaFailure(
                '작업이 접수됐지만 상태 주소나 결과를 받지 못했습니다.',
                jobId: data['job_id']?.toString(),
                context: '$storyId/$stepNumber',
              )
            : _withAbsoluteMediaUrls(media);
      } catch (error) {
        return _mediaFailure(
          '미디어 작업 응답을 읽지 못했습니다: $error',
          context: '$storyId/$stepNumber',
        );
      }
    }

    if (response.statusCode == 404) {
      return await _generateSceneMediaSync(
            storyId: storyId,
            stepNumber: stepNumber,
            storyText: storyText,
            genre: genre,
            age: age,
            characterKey: characterKey,
            sceneContract: sceneContract,
            includeVideo: includeVideo,
          ) ??
          _mediaFailure(
            '동화 장면 미디어 API를 찾지 못했습니다.',
            context: '$storyId/$stepNumber',
          );
    }

    return _mediaFailure(
      _mediaHttpError(response, '미디어 작업 접수'),
      context: '$storyId/$stepNumber',
    );
  }

  static Future<SceneMediaResult?> _pollSceneMediaJob(
    Map<String, dynamic> initialJob,
  ) async {
    var latest = _withAbsoluteMediaUrls(SceneMediaResult.fromJson(initialJob));
    final initialStatus = latest.status?.toLowerCase();
    if (initialStatus == 'completed' ||
        initialStatus == 'partial' ||
        initialStatus == 'failed') {
      if (initialStatus == 'completed' && !latest.hasMedia) {
        return _mediaFailure(
          '작업은 완료됐지만 이미지 결과가 비어 있습니다.',
          jobId: latest.jobId,
          context: 'poll',
        );
      }
      return latest;
    }

    final pollPathOrUrl = _sceneMediaJobStatusPath(latest);
    if (pollPathOrUrl == null) {
      return _mediaFailure(
        '미디어 작업 ID 또는 상태 주소가 응답에 없습니다.',
        jobId: latest.jobId,
        context: 'poll',
      );
    }

    final deadline = DateTime.now().add(const Duration(minutes: 20));
    var pollCount = 0;
    String? lastPollError;
    while (DateTime.now().isBefore(deadline)) {
      final status = latest.status?.toLowerCase();
      if (status == 'completed') {
        return latest.hasMedia
            ? latest
            : _mediaFailure(
                '작업은 완료됐지만 이미지 결과가 비어 있습니다.',
                jobId: latest.jobId,
                context: 'poll',
              );
      }
      if (status == 'partial' || status == 'failed') return latest;

      final delaySeconds = pollCount < 3
          ? 1
          : pollCount < 6
          ? 2
          : 3;
      pollCount += 1;
      await Future.delayed(Duration(seconds: delaySeconds));
      try {
        final response = await http
            .get(_apiUri(pollPathOrUrl), headers: _jsonHeaders)
            .timeout(const Duration(seconds: 20));
        if (response.statusCode == 404) {
          return _mediaFailure(
            '미디어 작업을 서버에서 찾지 못했습니다 (HTTP 404).',
            jobId: latest.jobId,
            context: 'poll',
          );
        }
        if (response.statusCode >= 500) {
          lastPollError = _mediaHttpError(response, '미디어 작업 상태 조회');
          if (pollCount == 1 || pollCount % 10 == 0) {
            debugPrint(
              '[scene-media][${latest.jobId ?? 'unknown'}] $lastPollError',
            );
          }
          continue;
        }
        if (response.statusCode >= 400) {
          return _mediaFailure(
            _mediaHttpError(response, '미디어 작업 상태 조회'),
            jobId: latest.jobId,
            context: 'poll',
          );
        }

        latest = _withAbsoluteMediaUrls(
          SceneMediaResult.fromJson(
            jsonDecode(response.body) as Map<String, dynamic>,
          ),
        );
        final refreshedStatus = latest.status?.toLowerCase();
        if (refreshedStatus == 'completed' ||
            refreshedStatus == 'partial' ||
            refreshedStatus == 'failed') {
          return latest;
        }
      } catch (error) {
        lastPollError = error.toString();
        if (pollCount == 1 || pollCount % 10 == 0) {
          debugPrint(
            '[scene-media][${latest.jobId ?? 'unknown'}] status poll failed: $error',
          );
        }
      }
    }

    return _mediaFailure(
      lastPollError == null
          ? '미디어 작업 상태 조회가 20분 안에 끝나지 않았습니다.'
          : '미디어 작업 상태 조회가 20분 안에 끝나지 않았습니다. 마지막 오류: $lastPollError',
      jobId: latest.jobId,
      context: 'poll',
    );
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
    String? characterKey,
    Map<String, dynamic>? sceneContract,
    required bool includeVideo,
  }) async {
    try {
      final response = await http
          .post(
            _apiUri('/api/stories/$storyId/scenes/$stepNumber/media/generate'),
            headers: _jsonHeaders,
            body: jsonEncode({
              'story_text': storyText,
              'genre': genre,
              'age': age,
              if (characterKey?.trim().isNotEmpty == true)
                'character_key': characterKey!.trim(),
              'scene_contract': ?sceneContract,
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
      return _mediaFailure(
        _mediaHttpError(response, '동기 미디어 생성'),
        context: '$storyId/$stepNumber',
      );
    } catch (error) {
      return _mediaFailure(
        '동기 미디어 생성 연결 실패: $error',
        context: '$storyId/$stepNumber',
      );
    }
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
            headers: _jsonHeaders,
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
          headers: _jsonHeaders,
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
          headers: _jsonHeaders,
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
          headers: _jsonHeaders,
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

  static Future<Map<String, dynamic>> fetchStoryEmotionAnalysis(
    String storyId,
  ) async {
    final response = await http
        .get(
          _apiUri('/api/stories/$storyId/emotion-analysis'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map,
      );
    }
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          '감정 분류 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>> fetchStoryPsychAnalysis(
    String storyId,
  ) async {
    final response = await http
        .get(
          _apiUri('/api/stories/$storyId/psych-analysis'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map,
      );
    }
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          '저장된 AI 해설 조회 실패: ${response.statusCode}',
    );
  }

  static Future<void> saveStoryPsychAnalysis({
    required String storyId,
    required Map<String, dynamic> psychResult,
    required String analysisKey,
  }) async {
    final response = await http
        .put(
          _apiUri('/api/stories/$storyId/psych-analysis'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'psych_result': psychResult,
            'analysis_key': analysisKey,
          }),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) return;
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          'AI 해설 저장 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>> fetchEmotionSummary(String userId) async {
    final response = await http
        .get(
          _apiUri('/api/users/$userId/emotion-summary'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map,
      );
    }
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          '누적 감정 분류 조회 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>> fetchTemporaryEmotionAnalysis({
    required String userId,
    required String temporaryStoryId,
  }) async {
    final response = await http
        .get(
          _apiUri(
            '/api/users/$userId/temporary-emotion-analyses/$temporaryStoryId',
          ),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map,
      );
    }
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          '임시 동화 분석 기록 조회 실패: ${response.statusCode}',
    );
  }

  static Future<Map<String, dynamic>> saveTemporaryEmotionAnalysis({
    required String userId,
    required String temporaryStoryId,
    required String title,
    required List<Map<String, dynamic>> scenes,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/users/$userId/temporary-emotion-analyses'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'temporary_story_id': temporaryStoryId,
            'title': title,
            'scenes': scenes,
          }),
        )
        .timeout(const Duration(seconds: 210));
    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map,
      );
    }
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          '임시 동화 감정 분석 결과 저장 실패: ${response.statusCode}',
    );
  }

  static Future<void> saveTemporaryEmotionExplanation({
    required String userId,
    required String temporaryStoryId,
    required Map<String, dynamic> psychResult,
  }) async {
    final response = await http
        .put(
          _apiUri(
            '/api/users/$userId/temporary-emotion-analyses/$temporaryStoryId',
          ),
          headers: _jsonHeaders,
          body: jsonEncode({'psych_result': psychResult}),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200) return;
    throw Exception(
      _extractDetailMessage(utf8.decode(response.bodyBytes)) ??
          '임시 동화 AI 해설 저장 실패: ${response.statusCode}',
    );
  }

  static Future<List<StorySession>> fetchUserStories(String userId) async {
    final response = await http
        .get(
          Uri.parse('$baseUrl/api/users/$userId/stories'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      try {
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
      } catch (error) {
        debugPrint(
          '[db-sync] story response parse failed; '
          'status=${response.statusCode}, bytes=${response.bodyBytes.length}: $error',
        );
        rethrow;
      }
    }
    throw Exception(
      _extractDetailMessage(response.body) ??
          '동화 기록 불러오기 실패: ${response.statusCode}',
    );
  }

  static Future<List<VocabWord>> fetchUserVocabularies(String userId) async {
    final response = await http
        .get(
          Uri.parse('$baseUrl/api/users/$userId/vocabularies'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
    final response = await http
        .get(
          Uri.parse('$baseUrl/api/community/posts?sort=$sort'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
          headers: _jsonHeaders,
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
    final response = await http
        .get(
          Uri.parse('$baseUrl/api/community/posts/$postId'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));

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
          headers: _jsonHeaders,
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
    bool deleteStory = false,
  }) async {
    final response = await http
        .delete(
          Uri.parse('$baseUrl/api/community/posts/$postId'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'account_id': accountId,
            'delete_story': deleteStory,
          }),
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
          headers: _jsonHeaders,
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
          headers: _jsonHeaders,
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

  static Future<Map<String, dynamic>> fetchMyProfile() async =>
      _getSocialMap('/api/users/me', '내 프로필 조회에 실패했어요.');

  static Future<Map<String, dynamic>> fetchPublicProfile(String userId) async =>
      _getSocialMap(
        '/api/users/${Uri.encodeComponent(userId)}/profile',
        '프로필을 불러오지 못했어요.',
      );

  static Future<Map<String, dynamic>> updateSocialProfile({
    String? nickname,
    String? bio,
  }) async {
    final response = await http
        .patch(
          _apiUri('/api/users/me'),
          headers: _jsonHeaders,
          body: jsonEncode({
            if (nickname != null) 'nickname': nickname.trim(),
            if (bio != null) 'bio': bio.trim(),
          }),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200)
      return jsonDecode(response.body) as Map<String, dynamic>;
    throw Exception(_extractDetailMessage(response.body) ?? '프로필 저장에 실패했어요.');
  }

  static Future<String> uploadProfileImage({
    required Uint8List bytes,
    required String filename,
    required String mimeType,
  }) async {
    final request =
        http.MultipartRequest('POST', _apiUri('/api/users/me/image'))
          ..headers.addAll(mediaHeaders)
          ..files.add(
            http.MultipartFile.fromBytes(
              'profile_image',
              bytes,
              filename: filename,
              contentType: MediaType.parse(mimeType),
            ),
          );
    final streamed = await request.send().timeout(const Duration(seconds: 40));
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final url = resolveMediaUrl(data['profile_image_url']?.toString());
      if (url == null || url.isEmpty) {
        throw Exception('서버에서 저장된 프로필 사진 주소를 받지 못했어요.');
      }
      return url;
    }
    throw Exception(
      _extractDetailMessage(response.body) ?? '프로필 사진 업로드에 실패했어요.',
    );
  }

  static Future<Map<String, dynamic>> toggleCommunityScrap(
    String postId,
  ) async {
    final response = await http
        .post(
          _apiUri('/api/community/posts/$postId/scrap'),
          headers: _jsonHeaders,
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode == 200)
      return jsonDecode(response.body) as Map<String, dynamic>;
    throw Exception(_extractDetailMessage(response.body) ?? '스크랩을 저장하지 못했어요.');
  }

  static Future<List<CommunityPost>> fetchMyScraps() async {
    final data = await _getSocialMap(
      '/api/users/me/scraps',
      '스크랩 목록을 불러오지 못했어요.',
    );
    return (data['posts'] as List? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(CommunityPost.fromJson)
        .toList();
  }

  static Future<Map<String, dynamic>> fetchMyInbox({int limit = 100}) =>
      _getSocialMap('/api/users/me/inbox?limit=$limit', '알림함을 불러오지 못했어요.');

  static Future<void> markInboxRead() async {
    final response = await http
        .post(_apiUri('/api/users/me/inbox/read'), headers: _jsonHeaders)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(
        _extractDetailMessage(response.body) ?? '알림 읽음 표시를 저장하지 못했어요.',
      );
    }
  }

  static Future<int> fetchUnreadMessageCount() async {
    final data = await _getSocialMap(
      '/api/messages/unread-count',
      '쪽지 알림을 불러오지 못했어요.',
    );
    return (data['unread_count'] as num?)?.toInt() ?? 0;
  }

  static Future<List<Map<String, dynamic>>> fetchMessages({
    required String box,
  }) async {
    final data = await _getSocialMap(
      '/api/messages?box=$box&page=1&size=100',
      '쪽지를 불러오지 못했어요.',
    );
    return (data['items'] as List? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();
  }

  static Future<Map<String, dynamic>> fetchMessage(String id) =>
      _getSocialMap('/api/messages/$id', '쪽지를 불러오지 못했어요.');

  static Future<Map<String, dynamic>> sendMessage({
    required String receiverId,
    required String content,
    String? replyTo,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/messages'),
          headers: _jsonHeaders,
          body: jsonEncode({
            'receiver_id': receiverId,
            'content': content.trim(),
            if (replyTo != null) 'reply_to': replyTo,
          }),
        )
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200 || response.statusCode == 201) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(_extractDetailMessage(response.body) ?? '쪽지를 보내지 못했어요.');
  }

  static Future<void> deleteMessage(String id) async {
    final response = await http
        .delete(_apiUri('/api/messages/$id'), headers: _jsonHeaders)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode != 200) {
      throw Exception(_extractDetailMessage(response.body) ?? '쪽지를 삭제하지 못했어요.');
    }
  }

  static Future<String> fetchNaverAuthorizationUrl() async {
    final data = await _getSocialMap(
      '/api/auth/naver/config',
      '네이버 로그인을 준비하지 못했어요.',
    );
    final url = data['authorization_url']?.toString() ?? '';
    if (url.isEmpty) throw Exception('네이버 로그인 주소가 비어 있어요.');
    return url;
  }

  static Future<Map<String, dynamic>> loginWithNaver({
    required String code,
    required String state,
  }) async {
    final response = await http
        .post(
          _apiUri('/api/auth/naver'),
          headers: _jsonHeaders,
          body: jsonEncode({'code': code, 'state': state}),
        )
        .timeout(const Duration(seconds: 30));
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      await setAccessToken(data['access_token']?.toString());
      return data;
    }
    throw Exception(_extractDetailMessage(response.body) ?? '네이버 로그인에 실패했어요.');
  }

  static Future<Map<String, dynamic>> _getSocialMap(
    String path,
    String fallback,
  ) async {
    final response = await http
        .get(_apiUri(path), headers: _jsonHeaders)
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 200)
      return jsonDecode(response.body) as Map<String, dynamic>;
    throw Exception(_extractDetailMessage(response.body) ?? fallback);
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
