import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:kakao_flutter_sdk/kakao_flutter_sdk.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'services/firebase_google_auth.dart';
import 'package:provider/provider.dart';
import 'admin_page.dart';
import 'app_theme.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'main_screen.dart';
import 'models/app_state.dart';
import 'services/db_service.dart';
import 'services/naver_oauth.dart';
import 'password_reset_page.dart';
import 'signup_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  bool _isLoading = false;
  bool _obscurePassword = true;
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  static const String _definedGoogleClientId = String.fromEnvironment(
    'GOOGLE_CLIENT_ID',
  );
  static const String _definedGoogleWebClientId = String.fromEnvironment(
    'GOOGLE_WEB_CLIENT_ID',
  );
  static const String _definedGoogleIosClientId = String.fromEnvironment(
    'GOOGLE_IOS_CLIENT_ID',
  );

  static String? get _webGoogleClientId {
    final explicitWebId = _definedGoogleWebClientId.trim();
    if (explicitWebId.isNotEmpty) return explicitWebId;
    final defined = _definedGoogleClientId.trim();
    if (defined.isNotEmpty) return defined;

    final configured = dotenv.isInitialized
        ? (dotenv.env['GOOGLE_WEB_CLIENT_ID'] ?? dotenv.env['GOOGLE_CLIENT_ID'])
                  ?.trim() ??
              ''
        : '';
    return configured.isEmpty ? null : configured;
  }

  static String? get _iosGoogleClientId {
    final defined = _definedGoogleIosClientId.trim();
    if (defined.isNotEmpty) return defined;
    final configured = dotenv.isInitialized
        ? dotenv.env['GOOGLE_IOS_CLIENT_ID']?.trim() ?? ''
        : '';
    return configured.isEmpty ? null : configured;
  }

  //  구글 클라이언트 ID
  late final GoogleSignIn _googleSignIn = GoogleSignIn(
    clientId: defaultTargetPlatform == TargetPlatform.iOS
        ? _iosGoogleClientId
        : null,
    serverClientId: _webGoogleClientId,
  );

  @override
  void initState() {
    super.initState();
    final naverCallback = consumeNaverOAuthCallback();
    if (naverCallback != null) {
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => _finishNaverLogin(naverCallback),
      );
    }
  }

  Future<void> _startNaverLogin() async {
    setState(() => _isLoading = true);
    try {
      final url = await DbService.fetchNaverAuthorizationUrl();
      await beginNaverOAuth(url);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', '')),
          ),
        );
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _finishNaverLogin(NaverOAuthCallback callback) async {
    if (callback.error != null) {
      if (mounted) {
        setState(() => _isLoading = false);
        final message = callback.error == 'access_denied'
            ? '네이버 로그인이 취소되었습니다.'
            : '네이버 인증에 실패했습니다. 다시 시도해 주세요.';
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(message)));
      }
      return;
    }
    final code = callback.code?.trim() ?? '';
    final state = callback.state?.trim() ?? '';
    if (code.isEmpty || state.isEmpty) {
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('네이버 인증 응답이 올바르지 않습니다. 다시 로그인해 주세요.')),
        );
      }
      return;
    }
    if (mounted) setState(() => _isLoading = true);
    try {
      final user = await DbService.loginWithNaver(code: code, state: state);
      if (!mounted) return;
      context.read<AppState>().setSignedInUser(
        userId: user['id']?.toString(),
        accountId: user['account_id']?.toString() ?? '',
        nickname: user['nickname']?.toString() ?? '네이버 사용자',
        provider: 'naver',
        email: user['email']?.toString(),
        phone: user['phone']?.toString(),
        address: user['address']?.toString(),
      );
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const MainScreen()),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.toString().replaceFirst('Exception: ', '')),
        ),
      );
      setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  //  서버(MongoDB)로 유저 정보 전송
  Future<void> _finishSocialLogin(
    String provider,
    String token, {
    String? tokenType,
  }) async {
    final data = await DbService.loginWithSocialToken(
      provider: provider,
      token: token,
      tokenType: tokenType,
    );
    _completeSocialLogin(data, provider);
  }

  void _showSocialLoginError(String provider, Object error) {
    if (!mounted) return;
    final message = error.toString().replaceFirst('Exception: ', '').trim();
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('$provider 로그인 실패: $message')));
  }

  void _completeSocialLogin(Map<String, dynamic> data, String provider) {
    final accountId = data['account_id']?.toString() ?? '';
    final nickname = data['nickname']?.toString() ?? '동화 친구';
    if (!mounted) return;
    context.read<AppState>().setSignedInUser(
      userId: data['id']?.toString(),
      accountId: accountId,
      nickname: nickname,
      provider: provider,
      email: data['email']?.toString(),
      phone: data['phone']?.toString(),
      address: data['address']?.toString(),
    );
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const MainScreen()),
    );
  }

  // 🟡 카카오 로그인
  Future<void> _loginWithKakao() async {
    setState(() => _isLoading = true);
    try {
      OAuthToken token;
      if (kIsWeb) {
        token = await UserApi.instance.loginWithKakaoAccount();
      } else {
        if (await isKakaoTalkInstalled()) {
          try {
            token = await UserApi.instance.loginWithKakaoTalk();
          } catch (e) {
            token = await UserApi.instance.loginWithKakaoAccount();
          }
        } else {
          token = await UserApi.instance.loginWithKakaoAccount();
        }
      }
      await _finishSocialLogin('kakao', token.accessToken);
    } catch (error) {
      debugPrint('카카오 로그인 실패: ${error.runtimeType}');
      _showSocialLoginError('카카오', error);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  // Google 로그인 결과를 같은 요청 흐름에서 검증해 중복/유실을 방지합니다.
  Future<void> _loginWithGoogle() async {
    setState(() => _isLoading = true);
    try {
      if (kIsWeb) {
        final firebaseToken = await FirebaseGoogleAuth.signInAndGetIdToken();
        if (firebaseToken == null) return;
        await _finishSocialLogin(
          'google',
          firebaseToken,
          tokenType: 'firebase',
        );
        return;
      }

      final account = await _googleSignIn.signIn();
      if (account == null) return;
      final token = (await account.authentication).idToken;
      if (token == null || token.isEmpty) {
        throw Exception('구글 인증 토큰을 받지 못했습니다. OAuth 클라이언트 설정을 확인해 주세요.');
      }
      await _finishSocialLogin('google', token);
    } catch (error) {
      debugPrint('구글 로그인 실패: ${error.runtimeType}');
      _showSocialLoginError('구글', error);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _loginWithEmail() async {
    final accountId = _emailController.text.trim();
    final password = _passwordController.text;

    if (accountId.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('아이디와 비밀번호를 모두 입력해주세요.')));
      return;
    }

    setState(() => _isLoading = true);
    try {
      final user = await DbService.loginUser(
        accountId: accountId,
        password: password,
      );
      if (!mounted) return;

      context.read<AppState>().setSignedInUser(
        userId: user['id']?.toString(),
        accountId: user['account_id']?.toString() ?? accountId,
        nickname: user['nickname']?.toString() ?? accountId,
        provider: user['provider']?.toString() ?? 'local',
        email: user['email']?.toString(),
        phone: user['phone']?.toString(),
        address: user['address']?.toString(),
      );

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${user['nickname'] ?? accountId}님 로그인되었습니다.')),
      );
      final isAdminLogin = accountId == '1111';
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => isAdminLogin
              ? AdminPage(adminAccountId: accountId)
              : const MainScreen(),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceAll('Exception: ', ''))),
      );
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.pageBackground,
      body: SafeArea(
        child: Stack(
          children: [
            Positioned(
              top: -130,
              right: -110,
              child: Container(
                width: 300,
                height: 300,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      const Color(0xFF8B5CF6).withValues(alpha: 0.22),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(22, 28, 22, 36),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(32),
                        decoration: BoxDecoration(
                          color: AppColors.pageSurface,
                          borderRadius: BorderRadius.circular(28),
                          border: Border.all(color: const Color(0x557C3AED)),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(
                                0xFF8B5CF6,
                              ).withValues(alpha: 0.1),
                              blurRadius: 28,
                              offset: const Offset(0, 12),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Center(
                              child: Container(
                                width: 100,
                                height: 100,
                                decoration: BoxDecoration(
                                  gradient: const LinearGradient(
                                    colors: [
                                      Color(0xFF8B5CF6),
                                      Color(0xFFEC4899),
                                    ],
                                  ),
                                  borderRadius: BorderRadius.circular(30),
                                ),
                                child: const Icon(
                                  Icons.auto_stories_rounded,
                                  color: Colors.white,
                                  size: 52,
                                ),
                              ),
                            ),
                            const SizedBox(height: 24),
                            const Text(
                              'AI Fairy Tale',
                              textAlign: TextAlign.center,
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
                            _authField(
                              controller: _emailController,
                              hint: '아이디',
                              icon: Icons.person_outline_rounded,
                              textInputAction: TextInputAction.next,
                            ),
                            const SizedBox(height: 13),
                            _authField(
                              controller: _passwordController,
                              hint: '비밀번호',
                              icon: Icons.lock_outline_rounded,
                              obscureText: _obscurePassword,
                              textInputAction: TextInputAction.done,
                              onSubmitted: (_) => _loginWithEmail(),
                              suffix: IconButton(
                                tooltip: _obscurePassword
                                    ? '비밀번호 보기'
                                    : '비밀번호 숨기기',
                                onPressed: () => setState(
                                  () => _obscurePassword = !_obscurePassword,
                                ),
                                icon: Icon(
                                  _obscurePassword
                                      ? Icons.visibility_outlined
                                      : Icons.visibility_off_outlined,
                                  color: Colors.white54,
                                  size: 20,
                                ),
                              ),
                            ),
                            Align(
                              alignment: Alignment.centerRight,
                              child: TextButton(
                                onPressed: _isLoading
                                    ? null
                                    : () => Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => PasswordResetPage(
                                            initialAccountId: _emailController
                                                .text
                                                .trim(),
                                          ),
                                        ),
                                      ),
                                child: const Text('비밀번호를 잊으셨나요?'),
                              ),
                            ),
                            const SizedBox(height: 2),
                            SizedBox(
                              height: 54,
                              child: FilledButton(
                                onPressed: _isLoading ? null : _loginWithEmail,
                                style: FilledButton.styleFrom(
                                  backgroundColor: const Color(0xFF8B5CF6),
                                  disabledBackgroundColor: const Color(
                                    0xFF583A8C,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(17),
                                  ),
                                ),
                                child: _isLoading
                                    ? const SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                          color: Colors.white,
                                          strokeWidth: 2,
                                        ),
                                      )
                                    : const Text(
                                        '로그인',
                                        style: TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w800,
                                        ),
                                      ),
                              ),
                            ),
                            const SizedBox(height: 6),
                            TextButton(
                              onPressed: _isLoading
                                  ? null
                                  : () => Navigator.push(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) => const SignupPage(),
                                      ),
                                    ),
                              child: const Text('처음 오셨나요? 회원가입'),
                            ),
                            const Padding(
                              padding: EdgeInsets.symmetric(vertical: 10),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Divider(color: Colors.white24),
                                  ),
                                  Padding(
                                    padding: EdgeInsets.symmetric(
                                      horizontal: 12,
                                    ),
                                    child: Text(
                                      '간편 로그인',
                                      style: TextStyle(
                                        color: Colors.white54,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ),
                                  Expanded(
                                    child: Divider(color: Colors.white24),
                                  ),
                                ],
                              ),
                            ),
                            if (_isLoading)
                              const Center(
                                child: Padding(
                                  padding: EdgeInsets.all(12),
                                  child: CircularProgressIndicator(
                                    color: Color(0xFFFEE500),
                                  ),
                                ),
                              )
                            else ...[
                              _buildSocialButton(
                                '카카오로 시작하기',
                                const Color(0xFFFEE500),
                                Colors.black,
                                _loginWithKakao,
                              ),
                              const SizedBox(height: 10),
                              _buildSocialButton(
                                '네이버로 시작하기',
                                const Color(0xFF03C75A),
                                Colors.white,
                                _startNaverLogin,
                              ),
                              const SizedBox(height: 10),
                              _buildSocialButton(
                                '구글로 시작하기',
                                Colors.white,
                                Colors.black,
                                _loginWithGoogle,
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _authField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
    bool obscureText = false,
    TextInputAction? textInputAction,
    ValueChanged<String>? onSubmitted,
    Widget? suffix,
  }) {
    final border = OutlineInputBorder(
      borderRadius: BorderRadius.circular(17),
      borderSide: const BorderSide(color: Color(0x337C3AED)),
    );
    return TextField(
      controller: controller,
      obscureText: obscureText,
      textInputAction: textInputAction,
      onSubmitted: onSubmitted,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white38),
        prefixIcon: Icon(icon, color: const Color(0xFFC4B5FD), size: 20),
        suffixIcon: suffix,
        filled: true,
        fillColor: AppColors.pageInput,
        border: border,
        enabledBorder: border,
        focusedBorder: border.copyWith(
          borderSide: const BorderSide(color: Color(0xFF9B5CFF), width: 1.4),
        ),
      ),
    );
  }

  Widget _buildSocialButton(
    String text,
    Color bgColor,
    Color textColor,
    VoidCallback onPressed,
  ) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: bgColor,
          foregroundColor: textColor,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: Text(
          text,
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}
