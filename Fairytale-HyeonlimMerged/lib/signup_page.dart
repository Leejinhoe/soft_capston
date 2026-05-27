import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'main_screen.dart';
import 'models/app_state.dart';
import 'services/db_service.dart';

class SignupPage extends StatefulWidget {
  const SignupPage({super.key});

  @override
  State<SignupPage> createState() => _SignupPageState();
}

class _SignupPageState extends State<SignupPage> {
  final TextEditingController _idController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _nicknameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _addressController = TextEditingController();

  String _passwordMessage = '';
  Color _passwordMessageColor = Colors.grey;
  bool _isPasswordSafe = false;
  bool _isLoading = false; // 🔥 서버와 통신 중임을 알리는 변수 추가

  @override
  void dispose() {
    _idController.dispose();
    _passwordController.dispose();
    _nicknameController.dispose();
    _emailController.dispose();
    _codeController.dispose();
    _phoneController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  void _checkPasswordSafety() {
    String password = _passwordController.text;
    RegExp regex = RegExp(
      r'^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[!@#\$%^&*(),.?":{}|<>]).{9,16}$',
    );

    setState(() {
      if (password.isEmpty) {
        _passwordMessage = '비밀번호를 입력해주세요.';
        _passwordMessageColor = Colors.redAccent;
        _isPasswordSafe = false;
      } else if (password.length < 9 || password.length > 16) {
        _passwordMessage = '비밀번호는 9자 이상, 16자 이하여야 합니다.';
        _passwordMessageColor = Colors.redAccent;
        _isPasswordSafe = false;
      } else if (!regex.hasMatch(password)) {
        _passwordMessage = '영문, 숫자, 특수문자를 모두 포함해야 합니다.';
        _passwordMessageColor = Colors.redAccent;
        _isPasswordSafe = false;
      } else {
        _passwordMessage = '안전한 비밀번호입니다! ✅';
        _passwordMessageColor = const Color(0xFF14B8A6);
        _isPasswordSafe = true;
      }
    });
  }

  // FastAPI 백엔드로 가입 요청을 보내는 통신 함수
  Future<void> _registerUser() async {
    // 1. 버튼을 누르면 자동으로 비밀번호 검사 실행
    _checkPasswordSafety();

    if (!_isPasswordSafe) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('비밀번호 안전 확인을 진행해주세요! (영문, 숫자, 특수문자 포함 9~16자)'),
        ),
      );
      return;
    }

    // 2. 통신 시작 전 로딩 상태를 true로 변경 (원이 돌아가게 함)
    setState(() {
      _isLoading = true;
    });

    try {
      final nickname =
          _nicknameController.text.isEmpty ? "이름없음" : _nicknameController.text;
      final data = await DbService.registerUser(
        accountId: _idController.text,
        password: _passwordController.text,
        nickname: nickname,
        email: _emailController.text,
        phone: _phoneController.text,
        address: _addressController.text,
        provider: "local",
      );

      if (!mounted) return;
      context.read<AppState>().setSignedInUser(
            userId: data['id']?.toString(),
            accountId: _idController.text,
            nickname: nickname,
            provider: 'local',
            email: _emailController.text,
            phone: _phoneController.text,
            address: _addressController.text,
          );
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('$nickname님 회원가입 성공!'),
        ),
      );
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const MainScreen()),
      );
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('통신 에러 원인: $e')));
    } finally {
      // 3. 성공하든 실패하든 통신이 끝나면 로딩 상태를 다시 해제
      setState(() {
        _isLoading = false;
      });
    }
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String hintText,
    required IconData icon,
    bool isPassword = false,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return TextField(
      controller: controller,
      obscureText: isPassword,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hintText,
        hintStyle: const TextStyle(color: Colors.grey, fontSize: 13),
        prefixIcon: Icon(icon, color: Colors.grey, size: 20),
        filled: true,
        fillColor: const Color(0xFF160F38),
        contentPadding: const EdgeInsets.symmetric(vertical: 16),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0x338B5CF6)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF7C3AED), width: 2),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF06041A),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        foregroundColor: Colors.white,
        title: const Text(
          '회원가입',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
        ),
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '아이디',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            _buildTextField(
              controller: _idController,
              hintText: '아이디를 입력하세요',
              icon: Icons.person_outline,
            ),
            const SizedBox(height: 24),
            const Text(
              '비밀번호',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _buildTextField(
                    controller: _passwordController,
                    hintText: '영문, 숫자, 특수문자 포함 9~16자',
                    icon: Icons.lock_outline,
                    isPassword: true,
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton(
                  onPressed: _checkPasswordSafety,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1E1645),
                    foregroundColor: const Color(0xFFA78BFA),
                    padding: const EdgeInsets.symmetric(
                      vertical: 16,
                      horizontal: 16,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: const BorderSide(color: Color(0xFF7C3AED)),
                    ),
                  ),
                  child: const Text(
                    '안전 확인',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            if (_passwordMessage.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8, left: 4),
                child: Text(
                  _passwordMessage,
                  style: TextStyle(color: _passwordMessageColor, fontSize: 12),
                ),
              ),
            const SizedBox(height: 24),
            const Text(
              '닉네임',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            _buildTextField(
              controller: _nicknameController,
              hintText: '사용할 닉네임을 입력하세요 (ex: 꼬마토끼)',
              icon: Icons.face_retouching_natural,
            ),
            const SizedBox(height: 24),
            const Text(
              '이메일',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _buildTextField(
                    controller: _emailController,
                    hintText: 'example@email.com',
                    icon: Icons.email_outlined,
                    keyboardType: TextInputType.emailAddress,
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('인증번호가 발송되었습니다.')),
                    );
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFEC4899),
                    padding: const EdgeInsets.symmetric(
                      vertical: 16,
                      horizontal: 16,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text(
                    '인증 발송',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _buildTextField(
              controller: _codeController,
              hintText: '인증번호 6자리 입력',
              icon: Icons.verified_user_outlined,
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: 24),
            const Text(
              '전화번호',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            _buildTextField(
              controller: _phoneController,
              hintText: '010-0000-0000',
              icon: Icons.phone_android_outlined,
              keyboardType: TextInputType.phone,
            ),
            const SizedBox(height: 24),
            const Text(
              '주소',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _buildTextField(
                    controller: _addressController,
                    hintText: '주소 검색 버튼을 눌러주세요',
                    icon: Icons.location_on_outlined,
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton(
                  onPressed: () {},
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1E1645),
                    foregroundColor: const Color(0xFFA78BFA),
                    padding: const EdgeInsets.symmetric(
                      vertical: 16,
                      horizontal: 16,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: const BorderSide(color: Color(0xFF7C3AED)),
                    ),
                  ),
                  child: const Text(
                    '주소 검색',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 48),
            SizedBox(
              width: double.infinity,
              height: 56, // 버튼 크기 고정
              child: ElevatedButton(
                onPressed:
                    _isLoading ? null : _registerUser, // 🔥 로딩 중일 때는 버튼 클릭 방지
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF7C3AED),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  elevation: 5,
                ),
                // 🔥 로딩 중이면 원형 프로그레스 바를 띄우고, 아니면 텍스트를 띄움
                child: _isLoading
                    ? const SizedBox(
                        height: 24,
                        width: 24,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 3,
                        ),
                      )
                    : const Text(
                        '동화 AI 시작하기',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}
