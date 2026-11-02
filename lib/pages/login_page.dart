import 'dart:html' as html;
import 'dart:math';

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/auth_service.dart';
import 'admin_login_dialog.dart';
import 'signup_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController idController = TextEditingController();
  final TextEditingController pwController = TextEditingController();

  String? authCode;
  bool isProcessingLogin = false;

  @override
  void initState() {
    super.initState();

    final uri = Uri.parse(html.window.location.href);
    authCode = uri.queryParameters['code'];
    final state = uri.queryParameters['state'];
    final provider = html.window.sessionStorage['login_provider'];

    if (authCode != null) {
      isProcessingLogin = true;

      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (provider == 'kakao') {
          await sendSocialCodeToServer('/auth/kakao', {'code': authCode});
        } else if (provider == 'naver') {
          final savedState = html.window.sessionStorage['naver_oauth_state'];
          if (state != null && savedState == state) {
            await sendSocialCodeToServer(
                '/auth/naver', {'code': authCode, 'state': state});
          } else {
            _finishProcessing('네이버 로그인 확인에 실패했어요. 다시 시도해 주세요.');
          }
        } else if (provider == 'google') {
          await sendSocialCodeToServer('/auth/google', {'code': authCode});
        } else {
          _finishProcessing(null);
        }
      });
    }
  }

  void showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  /// 소셜 로그인 처리가 실패했을 때 주소창의 ?code=... 를 지우고 로그인 화면으로 돌아옵니다.
  void _finishProcessing(String? message) {
    html.window.history.replaceState(null, '', '/');
    html.window.sessionStorage.remove('login_provider');
    if (!mounted) return;
    setState(() => isProcessingLogin = false);
    if (message != null) showMessage(message);
  }

  /// 카카오/네이버/구글 공통: 인가 코드를 서버로 보내 JWT를 받고 홈으로 이동
  Future<void> sendSocialCodeToServer(
      String path, Map<String, dynamic> body) async {
    try {
      final response = await ApiClient.post(path, body: body);
      final data = ApiClient.decode(response);

      if (response.statusCode == 200 && data is Map && data['success'] == true) {
        html.window.history.replaceState(null, '', '/');
        html.window.sessionStorage.remove('login_provider');
        await AuthService.completeLogin(data);
      } else {
        _finishProcessing(ApiClient.errorMessage(response, '로그인에 실패했어요.'));
      }
    } catch (e) {
      debugPrint('소셜 로그인 오류: $e');
      _finishProcessing('서버 연결 실패');
    }
  }

  String generateState() {
    const chars =
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    final random = Random.secure();
    return List.generate(20, (_) => chars[random.nextInt(chars.length)]).join();
  }

  Future<void> login() async {
    final id = idController.text.trim();
    final pw = pwController.text.trim();

    if (id.isEmpty || pw.isEmpty) {
      showMessage('아이디와 비밀번호를 입력해주세요.');
      return;
    }

    try {
      final response =
          await ApiClient.post('/login', body: {'id': id, 'password': pw});
      final data = ApiClient.decode(response);

      if (data is Map && data['success'] == true) {
        await AuthService.completeLogin(data);
      } else {
        showMessage(ApiClient.errorMessage(response, '로그인에 실패했습니다.'));
      }
    } catch (e) {
      debugPrint('로그인 오류: $e');
      showMessage('서버 연결 실패');
    }
  }

  void loginWithKakao() {
    const restApiKey = '56748969c02c4df8c73911627fba1c1b';
    const redirectUri = 'http://localhost:53730/';

    html.window.sessionStorage['login_provider'] = 'kakao';

    final url = 'https://kauth.kakao.com/oauth/authorize'
        '?response_type=code'
        '&client_id=$restApiKey'
        '&redirect_uri=$redirectUri';

    html.window.location.href = url;
  }

  void loginWithNaver() {
    const clientId = 'B4YB9wjku1DPIHdgSPNg';
    const redirectUri = 'http://localhost:53730/';
    final state = generateState();

    html.window.sessionStorage['login_provider'] = 'naver';
    html.window.sessionStorage['naver_oauth_state'] = state;

    final url = 'https://nid.naver.com/oauth2.0/authorize'
        '?response_type=code'
        '&client_id=$clientId'
        '&redirect_uri=$redirectUri'
        '&state=$state';

    html.window.location.href = url;
  }

  void loginWithGoogle() {
    const clientId =
        '306054774600-o43jp420lgvfu16lhr1l8r2ta4ie59b7.apps.googleusercontent.com';
    const redirectUri = 'http://localhost:53730/';

    html.window.sessionStorage['login_provider'] = 'google';

    final url = 'https://accounts.google.com/o/oauth2/v2/auth'
        '?response_type=code'
        '&client_id=$clientId'
        '&redirect_uri=$redirectUri'
        '&scope=openid%20email%20profile';

    html.window.location.href = url;
  }

  Widget socialButton({
    required String text,
    required Color color,
    required VoidCallback onTap,
  }) {
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
        child: Text(
          text,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    idController.dispose();
    pwController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (isProcessingLogin) {
      return const Scaffold(
        backgroundColor: Color(0xFF070018),
        body: Center(
          child: CircularProgressIndicator(
            color: Colors.purpleAccent,
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Container(
            width: 420,
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: const Color(0xFF140028),
              borderRadius: BorderRadius.circular(32),
              border: Border.all(color: Colors.white10),
              boxShadow: [
                BoxShadow(
                  color: Colors.purple.withOpacity(0.25),
                  blurRadius: 30,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 100,
                  height: 100,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                    ),
                    borderRadius: BorderRadius.circular(30),
                  ),
                  child: const Icon(
                    Icons.auto_stories,
                    color: Colors.white,
                    size: 52,
                  ),
                ),
                const SizedBox(height: 24),
                const Text(
                  'AI Fairy Tale',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 34,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'AI와 함께\n나만의 동화를 만들어보세요 ✨',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 16,
                    height: 1.6,
                  ),
                ),
                const SizedBox(height: 36),
                TextField(
                  controller: idController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: '아이디',
                    hintStyle: const TextStyle(color: Colors.white38),
                    prefixIcon: const Icon(Icons.person, color: Colors.white54),
                    filled: true,
                    fillColor: const Color(0xFF1A0B3A),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(18),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                TextField(
                  controller: pwController,
                  obscureText: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: '비밀번호',
                    hintStyle: const TextStyle(color: Colors.white38),
                    prefixIcon: const Icon(Icons.lock, color: Colors.white54),
                    filled: true,
                    fillColor: const Color(0xFF1A0B3A),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(18),
                      borderSide: BorderSide.none,
                    ),
                  ),
                ),
                const SizedBox(height: 28),
                SizedBox(
                  width: double.infinity,
                  height: 60,
                  child: ElevatedButton(
                    onPressed: login,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF8B5CF6),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(20),
                      ),
                    ),
                    child: const Text(
                      '로그인',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 26),
                Row(
                  children: const [
                    Expanded(child: Divider(color: Colors.white24)),
                    Padding(
                      padding: EdgeInsets.symmetric(horizontal: 14),
                      child: Text(
                        '간편 로그인',
                        style: TextStyle(color: Colors.white54),
                      ),
                    ),
                    Expanded(child: Divider(color: Colors.white24)),
                  ],
                ),
                const SizedBox(height: 24),
                socialButton(
                  text: '카카오로 시작하기',
                  color: const Color(0xFFFEE500),
                  onTap: loginWithKakao,
                ),
                const SizedBox(height: 14),
                socialButton(
                  text: '네이버로 시작하기',
                  color: const Color(0xFF03C75A),
                  onTap: loginWithNaver,
                ),
                const SizedBox(height: 14),
                socialButton(
                  text: '구글로 시작하기',
                  color: const Color(0xFF4285F4),
                  onTap: loginWithGoogle,
                ),
                const SizedBox(height: 20),
                TextButton(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => const SignUpPage(),
                      ),
                    );
                  },
                  child: const Text(
                    '회원가입',
                    style: TextStyle(color: Colors.white70),
                  ),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (_) => const AdminLoginDialog(),
                    );
                  },
                  child: const Text(
                    '관리자 로그인',
                    style: TextStyle(
                      color: Colors.white38,
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}