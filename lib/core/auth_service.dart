import 'package:flutter/material.dart';

import '../pages/admin_page.dart';
import '../pages/home_page.dart';
import '../pages/login_page.dart';
import 'api_client.dart';

/// 로그인 성공 처리 / 자동 로그인 / 로그아웃을 한 곳에서 관리합니다.
class AuthService {
  static void init() {
    ApiClient.onSessionExpired = (message) async => goToLogin(message: message);
  }

  /// 로그인한 사용자가 처음 볼 화면 (관리자는 관리자 화면, 나머지는 홈)
  static Widget homeFor(Map user) {
    if (user['role'] == 'admin') return const AdminPage();
    final name = (user['name'] ?? user['nickname'] ?? '').toString();
    return HomePage(displayName: name.trim().isEmpty ? '사용자' : name);
  }

  /// 로그인 API 응답({access_token, user})을 받아 토큰 저장 후 화면 이동
  static Future<void> completeLogin(Map data) async {
    final token = data['access_token'];
    final user = data['user'];
    if (token is! String || token.isEmpty || user is! Map) {
      throw Exception('로그인 응답에 토큰이 없어요.');
    }
    await TokenStorage.save(token);
    _replaceAll(homeFor(user));
  }

  /// 저장된 토큰으로 내 정보 조회. 토큰이 없거나 만료되면 null.
  /// 서버에 연결할 수 없으면 예외를 던집니다.
  static Future<Map<String, dynamic>?> fetchMe() async {
    if (await TokenStorage.read() == null) return null;
    final response = await ApiClient.get('/api/users/me');
    if (response.statusCode != 200) return null;
    final data = ApiClient.decode(response);
    return data is Map<String, dynamic> ? data : null;
  }

  static Future<void> logout() async {
    await TokenStorage.clear();
    goToLogin();
  }

  static void goToLogin({String? message}) {
    _replaceAll(const LoginPage());
    if (message != null && message.isNotEmpty) {
      appMessengerKey.currentState
        ?..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(message)));
    }
  }

  static void _replaceAll(Widget page) {
    appNavigatorKey.currentState?.pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => page),
      (route) => false,
    );
  }
}

/// 앱 첫 화면: 저장된 토큰이 있으면 자동 로그인, 없으면 로그인 화면
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _decide());
  }

  Future<void> _decide() async {
    // 소셜 로그인에서 돌아온 경우(?code=...)는 로그인 화면이 처리합니다.
    if (Uri.base.queryParameters.containsKey('code')) {
      AuthService.goToLogin();
      return;
    }

    try {
      final me = await AuthService.fetchMe();
      if (me != null) {
        AuthService._replaceAll(AuthService.homeFor(me));
      } else {
        AuthService.goToLogin();
      }
    } catch (e) {
      debugPrint('자동 로그인 실패: $e');
      AuthService.goToLogin(message: '서버에 연결할 수 없어요. 잠시 후 다시 해 주세요.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF070018),
      body: Center(
        child: CircularProgressIndicator(color: Colors.purpleAccent),
      ),
    );
  }
}
