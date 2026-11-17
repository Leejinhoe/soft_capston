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
  final _id = TextEditingController();
  final _password = TextEditingController();
  final _confirmation = TextEditingController();
  final _name = TextEditingController();
  final _birth = TextEditingController();
  final _email = TextEditingController();
  final _code = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();
  String? _availableId;
  String? _idMessage;
  String? _verifiedEmail;
  String? _emailToken;
  bool _checkingId = false;
  bool _sending = false;
  bool _verifying = false;
  bool _registering = false;
  bool _passwordValid = false;

  // Keep registration consistent with the existing password-reset policy.
  bool _validPassword(String value) => RegExp(
    r'^(?=.*[a-zA-Z])(?=.*[0-9])(?=.*[!@#\$%^&*(),.?":{}|<>]).{9,16}$',
  ).hasMatch(value);

  void _message(String text) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

  String _normalizedBirth(String value) {
    final input = value.trim();
    if (RegExp(r'^\d{8}$').hasMatch(input)) {
      return '${input.substring(0, 4)}-${input.substring(4, 6)}-${input.substring(6, 8)}';
    }
    return input;
  }

  Future<void> _checkId() async {
    final id = _id.text.trim();
    if (id.isEmpty) return _message('아이디를 입력해 주세요.');
    setState(() {
      _checkingId = true;
      _availableId = null;
      _idMessage = null;
    });
    try {
      final available = await DbService.isSignupIdAvailable(id);
      if (!mounted || _id.text.trim() != id) return;
      setState(() {
        _availableId = available ? id : null;
        _idMessage = available ? '사용 가능한 아이디입니다.' : '이미 사용 중인 아이디입니다.';
      });
    } catch (error) {
      if (mounted) _message(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _checkingId = false);
    }
  }

  Future<void> _sendCode() async {
    final email = _email.text.trim();
    if (email.isEmpty) return _message('먼저 이메일 주소를 입력해 주세요.');
    setState(() {
      _sending = true;
      _emailToken = null;
      _verifiedEmail = null;
    });
    try {
      await DbService.sendEmailVerificationCode(email: email);
      if (mounted) _message('인증번호를 이메일로 발송했습니다.');
    } catch (error) {
      if (mounted) _message(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _verifyCode() async {
    final email = _email.text.trim();
    final code = _code.text.trim();
    if (email.isEmpty || code.length != 6) {
      return _message('이메일과 6자리 인증번호를 확인해 주세요.');
    }
    setState(() => _verifying = true);
    try {
      final token = await DbService.confirmEmailVerificationCode(
        email: email,
        code: code,
      );
      if (!mounted || _email.text.trim() != email) return;
      setState(() {
        _emailToken = token;
        _verifiedEmail = email.toLowerCase();
      });
      _message('이메일 인증이 완료되었습니다.');
    } catch (error) {
      if (mounted) _message(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  Future<void> _signUp() async {
    final id = _id.text.trim();
    final password = _password.text;
    final name = _name.text.trim();
    final birth = _normalizedBirth(_birth.text);
    final email = _email.text.trim();
    if (id.isEmpty || password.isEmpty || name.isEmpty || birth.isEmpty) {
      return _message('필수 항목을 모두 입력해 주세요.');
    }
    if (_availableId != id) return _message('아이디 중복검사를 완료해 주세요.');
    if (!_validPassword(password)) return _message('비밀번호 규칙을 확인해 주세요.');
    if (password != _confirmation.text) return _message('비밀번호가 일치하지 않습니다.');
    final date = DateTime.tryParse(birth);
    final now = DateTime.now();
    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(birth) ||
        date == null ||
        '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}' !=
            birth ||
        date.isAfter(DateTime(now.year, now.month, now.day))) {
      return _message('생년월일을 YYYYMMDD 또는 YYYY-MM-DD 형식으로 확인해 주세요.');
    }
    if (email.isNotEmpty &&
        (_emailToken == null || _verifiedEmail != email.toLowerCase())) {
      return _message('이메일 인증을 완료해 주세요.');
    }
    setState(() => _registering = true);
    try {
      final data = await DbService.registerUser(
        accountId: id,
        password: password,
        nickname: name,
        birth: birth,
        email: email,
        phone: _phone.text.trim(),
        address: _address.text.trim(),
        provider: 'local',
        emailVerificationToken: _emailToken,
      );
      if (!mounted) return;
      context.read<AppState>().setSignedInUser(
        userId: data['id']?.toString(),
        accountId: id,
        nickname: name,
        provider: 'local',
        email: email,
        phone: _phone.text.trim(),
        address: _address.text.trim(),
      );
      _message('$name님 회원가입 성공!');
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const MainScreen()),
      );
    } catch (error) {
      if (mounted) _message(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _registering = false);
    }
  }

  @override
  void dispose() {
    for (final controller in [
      _id,
      _password,
      _confirmation,
      _name,
      _birth,
      _email,
      _code,
      _phone,
      _address,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Widget _field(
    TextEditingController controller,
    String hint,
    IconData icon, {
    bool obscure = false,
    TextInputType? keyboard,
    ValueChanged<String>? onChanged,
  }) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      keyboardType: keyboard,
      onChanged: onChanged,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white38),
        prefixIcon: Icon(icon, color: Colors.white54),
        filled: true,
        fillColor: const Color(0xFF1A0B3A),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF070018),
        foregroundColor: Colors.white,
        elevation: 0,
        title: const Text('회원가입', style: TextStyle(color: Colors.white)),
      ),
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
            ),
            child: Column(
              children: [
                const Text(
                  '회원가입',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 30,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 30),
                Row(
                  children: [
                    Expanded(
                      child: _field(
                        _id,
                        '아이디',
                        Icons.person,
                        onChanged: (_) {
                          if (_availableId != null || _idMessage != null) {
                            setState(() {
                              _availableId = null;
                              _idMessage = null;
                            });
                          }
                        },
                      ),
                    ),
                    const SizedBox(width: 10),
                    ElevatedButton(
                      onPressed: _checkingId ? null : _checkId,
                      child: Text(_checkingId ? '확인 중' : '중복검사'),
                    ),
                  ],
                ),
                if (_idMessage != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        _idMessage!,
                        style: TextStyle(
                          color: _availableId != null
                              ? Colors.greenAccent
                              : Colors.redAccent,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                _field(
                  _password,
                  '비밀번호',
                  Icons.lock,
                  obscure: true,
                  onChanged: (value) =>
                      setState(() => _passwordValid = _validPassword(value)),
                ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '영문, 숫자, 특수문자를 포함한 9~16자',
                    style: TextStyle(
                      color: _passwordValid ? Colors.white70 : Colors.grey,
                      fontSize: 12,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                _field(
                  _confirmation,
                  '비밀번호 확인',
                  Icons.lock_outline,
                  obscure: true,
                ),
                const SizedBox(height: 16),
                _field(_name, '이름', Icons.badge),
                const SizedBox(height: 16),
                _field(
                  _birth,
                  '생년월일 (예: 20000101 또는 2000-01-01)',
                  Icons.cake,
                  keyboard: TextInputType.number,
                ),
                const SizedBox(height: 16),
                _field(
                  _email,
                  '이메일 (선택)',
                  Icons.email,
                  keyboard: TextInputType.emailAddress,
                  onChanged: (_) {
                    setState(() {
                      _emailToken = null;
                      _verifiedEmail = null;
                    });
                  },
                ),
                if (_email.text.trim().isNotEmpty || _emailToken != null) ...[
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _sending ? null : _sendCode,
                      child: Text(_sending ? '발송 중...' : '인증 발송'),
                    ),
                  ),
                  _field(
                    _code,
                    '인증번호 6자리',
                    Icons.verified_user_outlined,
                    keyboard: TextInputType.number,
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _verifying ? null : _verifyCode,
                      child: Text(
                        _emailToken != null
                            ? '인증 완료'
                            : _verifying
                            ? '확인 중...'
                            : '인증번호 확인',
                      ),
                    ),
                  ),
                ],
                Material(
                  color: Colors.transparent,
                  child: ExpansionTile(
                    title: const Text(
                      '추가 정보 (선택)',
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                    iconColor: Colors.white70,
                    collapsedIconColor: Colors.white70,
                    children: [
                      _field(
                        _phone,
                        '전화번호 (선택)',
                        Icons.phone,
                        keyboard: TextInputType.phone,
                      ),
                      const SizedBox(height: 12),
                      _field(_address, '주소 (선택)', Icons.home_outlined),
                    ],
                  ),
                ),
                const SizedBox(height: 30),
                SizedBox(
                  width: double.infinity,
                  height: 60,
                  child: ElevatedButton(
                    onPressed: _registering ? null : _signUp,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF8B5CF6),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(20),
                      ),
                    ),
                    child: Text(
                      _registering ? '가입 중...' : '회원가입',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
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
