import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:kakao_flutter_sdk/kakao_flutter_sdk.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:provider/provider.dart';
import 'additional_info_page.dart';
import 'admin_page.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'main_screen.dart';
import 'models/app_state.dart';
import 'services/db_service.dart';
import 'signup_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  bool _isLoading = false;
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  //  구글 클라이언트 ID
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    clientId: kIsWeb ? dotenv.env['GOOGLE_CLIENT_ID'] : null,
  );

  @override
  void initState() {
    super.initState();
    //  구글 웹 로그인 성공 감지
    _googleSignIn.onCurrentUserChanged.listen((
      GoogleSignInAccount? account,
    ) async {
      if (account != null) {
        String userId = account.id;
        String nickname = account.displayName ?? "구글유저";
        debugPrint("구글 로그인 성공: $nickname");
        await _saveUserToDB("Google", userId, nickname, account.email);
      }
    });
  }

  //  서버(MongoDB)로 유저 정보 전송
  Future<void> _saveUserToDB(
    String loginType,
    String userId,
    String nickname,
    String? email,
  ) async {
    debugPrint("서버로 유저 정보 전송 시작");

    try {
      final data = await DbService.registerUser(
        accountId: userId,
        nickname: nickname,
        email: email,
        provider: loginType.toLowerCase(),
        providerId: userId,
      );

      debugPrint("MongoDB 저장 성공");
      if (mounted) {
        context.read<AppState>().setSignedInUser(
              userId: data['id']?.toString(),
              accountId: userId,
              nickname: nickname,
              provider: loginType.toLowerCase(),
              email: email,
              phone: data['phone']?.toString(),
              address: data['address']?.toString(),
            );
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (context) => AdditionalInfoPage(accountId: userId),
          ),
        );
      }
    } catch (e) {
      debugPrint("서버 연결 에러: $e");
    }
  }

  // 🟡 카카오 로그인
  Future<void> _loginWithKakao() async {
    setState(() => _isLoading = true);
    try {
      if (kIsWeb) {
        await UserApi.instance.loginWithKakaoAccount();
      } else {
        if (await isKakaoTalkInstalled()) {
          try {
            await UserApi.instance.loginWithKakaoTalk();
          } catch (e) {
            await UserApi.instance.loginWithKakaoAccount();
          }
        } else {
          await UserApi.instance.loginWithKakaoAccount();
        }
      }

      User user = await UserApi.instance.me();
      String userId = user.id.toString();
      String nickname = user.kakaoAccount?.profile?.nickname ?? "이름없음";
      String? email = user.kakaoAccount?.email;

      debugPrint("카카오 로그인 성공: $nickname");
      await _saveUserToDB("Kakao", userId, nickname, email);
    } catch (error) {
      debugPrint("카카오 로그인 실패: $error");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('로그인 실패! 플러터 캐시를 삭제해야 할 수 있습니다.')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  // ⚪ 구글 로그인 (모바일 전용)
  Future<void> _loginWithGoogle() async {
    setState(() => _isLoading = true);
    try {
      await _googleSignIn.signIn();
    } catch (error) {
      debugPrint("구글 로그인 실패: $error");
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _loginWithEmail() async {
    final accountId = _emailController.text.trim();
    final password = _passwordController.text;

    if (accountId.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('아이디와 비밀번호를 모두 입력해주세요.')),
      );
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
        SnackBar(
          content: Text('${user['nickname'] ?? accountId}님 로그인되었습니다.'),
        ),
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
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(
          SnackBar(content: Text(e.toString().replaceAll('Exception: ', ''))));
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF06041A),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 40.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 40),
              const Center(child: Text('📖', style: TextStyle(fontSize: 60))),
              const SizedBox(height: 16),
              const Center(
                child: Text(
                  '동화 AI',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(height: 40),

              // 🎨 원래 있던 이메일/비밀번호 입력창 복구
              TextField(
                controller: _emailController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '아이디를 입력하세요',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF160F38),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passwordController,
                obscureText: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '비밀번호를 입력하세요',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF160F38),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _isLoading ? null : _loginWithEmail,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF7C3AED),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: _isLoading
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        ),
                      )
                    : const Text(
                        '로그인',
                        style: TextStyle(
                          fontSize: 16,
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
              const SizedBox(height: 10),
              TextButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const SignupPage()),
                  );
                },
                child: const Text(
                  '회원가입 하러가기',
                  style: TextStyle(
                    color: Color(0xFFC4B5FD),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // 🎨 구분선 복구
              Row(
                children: const [
                  Expanded(child: Divider(color: Colors.white24, thickness: 1)),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 16),
                    child: Text(
                      '또는 간편 로그인',
                      style: TextStyle(color: Colors.white54, fontSize: 12),
                    ),
                  ),
                  Expanded(child: Divider(color: Colors.white24, thickness: 1)),
                ],
              ),
              const SizedBox(height: 24),

              // 🎨 하단 소셜 로그인 버튼 복구
              _isLoading
                  ? const Center(
                      child: CircularProgressIndicator(
                        color: Color(0xFFFEE500),
                      ),
                    )
                  : Column(
                      children: [
                        _buildSocialButton(
                          '카카오로 시작하기',
                          const Color(0xFFFEE500),
                          Colors.black,
                          _loginWithKakao,
                        ),
                        const SizedBox(height: 12),

                        _buildSocialButton(
                          '구글로 시작하기',
                          Colors.white,
                          Colors.black,
                          _loginWithGoogle,
                        ),

                        // const SizedBox(height: 12),
                        // _buildSocialButton(
                        //  '네이버로 시작하기',
                        //  const Color(0xFF03C75A),
                        //  Colors.white,
                        //  () => _loginWithOther('네이버'),
                        //),
                      ],
                    ),
            ],
          ),
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
