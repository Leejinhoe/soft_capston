import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// 백엔드 주소 (한 곳에서만 관리)
const String kApiBaseUrl = 'http://127.0.0.1:8000';

/// 화면 어디서든 로그인 화면으로 보내거나 안내 문구를 띄우기 위한 전역 키
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();
final GlobalKey<ScaffoldMessengerState> appMessengerKey =
    GlobalKey<ScaffoldMessengerState>();

/// JWT 저장소 (shared_preferences, 웹에서는 localStorage)
class TokenStorage {
  static const String _key = 'access_token';
  static String? _cached;
  static bool _loaded = false;

  static Future<String?> read() async {
    if (_loaded) return _cached;
    final prefs = await SharedPreferences.getInstance();
    _cached = prefs.getString(_key);
    _loaded = true;
    return _cached;
  }

  static Future<void> save(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, token);
    _cached = token;
    _loaded = true;
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
    _cached = null;
    _loaded = true;
  }
}

/// 모든 API 호출은 여기를 거칩니다. 저장된 토큰을 Authorization 헤더에 자동으로 붙입니다.
class ApiClient {
  /// 토큰이 만료되었거나 정지된 계정일 때 호출 (AuthService가 등록)
  static Future<void> Function(String message)? onSessionExpired;

  static Uri uri(String path) => Uri.parse('$kApiBaseUrl$path');

  static Future<Map<String, String>> _headers({bool json = true}) async {
    final token = await TokenStorage.read();
    return {
      if (json) 'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  static String? _encode(Object? body) => body == null ? null : jsonEncode(body);

  static Future<http.Response> get(String path) async =>
      _check(await http.get(uri(path), headers: await _headers()));

  static Future<http.Response> post(String path, {Object? body}) async =>
      _check(await http.post(uri(path),
          headers: await _headers(), body: _encode(body)));

  static Future<http.Response> patch(String path, {Object? body}) async =>
      _check(await http.patch(uri(path),
          headers: await _headers(), body: _encode(body)));

  static Future<http.Response> put(String path, {Object? body}) async =>
      _check(await http.put(uri(path),
          headers: await _headers(), body: _encode(body)));

  static Future<http.Response> delete(String path) async =>
      _check(await http.delete(uri(path), headers: await _headers()));

  /// 파일 업로드 (multipart)
  static Future<http.Response> uploadFile(
    String path, {
    required String field,
    required List<int> bytes,
    required String filename,
  }) async {
    final request = http.MultipartRequest('POST', uri(path));
    request.headers.addAll(await _headers(json: false));
    request.files
        .add(http.MultipartFile.fromBytes(field, bytes, filename: filename));
    final streamed = await request.send();
    return _check(await http.Response.fromStream(streamed));
  }

  /// 한글이 깨지지 않게 UTF-8로 JSON을 읽습니다.
  static dynamic decode(http.Response response) {
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      return null;
    }
  }

  /// 서버가 보낸 안내 문구를 꺼냅니다. (detail / detail.message / message)
  static String errorMessage(http.Response response,
      [String fallback = '문제가 생겼어요. 잠시 후 다시 해 주세요.']) {
    final data = decode(response);
    if (data is Map) {
      final detail = data['detail'];
      if (detail is String) return detail;
      if (detail is Map && detail['message'] is String) return detail['message'];
      if (data['message'] is String) return data['message'];
    }
    return fallback;
  }

  static bool isBanned(http.Response response) {
    if (response.statusCode != 403) return false;
    final data = decode(response);
    return data is Map && data['detail'] is Map && data['detail']['code'] == 'banned';
  }

  static Future<http.Response> _check(http.Response response) async {
    final hadToken = (await TokenStorage.read()) != null;
    if (hadToken && (response.statusCode == 401 || isBanned(response))) {
      await TokenStorage.clear();
      await onSessionExpired?.call(
          errorMessage(response, '로그인이 만료되었어요. 다시 로그인해 주세요.'));
    }
    return response;
  }
}
