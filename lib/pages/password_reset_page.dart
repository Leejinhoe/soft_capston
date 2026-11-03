import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api_client.dart';
import '../core/password_rules.dart';

const _bg = Color(0xFF070018);
const _card = Color(0xFF140028);
const _field = Color(0xFF1A0B3A);
const _purple = Color(0xFF8B5CF6);

/// 비밀번호 찾기: 아이디 + 가입 이메일 → 6자리 인증번호 → 새 비밀번호 → 로그인 화면
/// (서버: POST /api/auth/password-reset/request · verify · confirm)
class PasswordResetPage extends StatefulWidget {
  const PasswordResetPage({super.key});

  @override
  State<PasswordResetPage> createState() => _PasswordResetPageState();
}

enum _Step { info, code, password }

class _PasswordResetPageState extends State<PasswordResetPage> {
  final idController = TextEditingController();
  final emailController = TextEditingController();
  final codeController = TextEditingController();
  final pwController = TextEditingController();
  final pwConfirmController = TextEditingController();

  _Step step = _Step.info;
  bool busy = false;
  String notice = ''; // 서버 안내 문구 (인증번호 보냄 등)
  String error = '';
  String resetToken = '';

  Timer? _timer;
  int resendLeft = 0; // 재발송까지 남은 초
  int expireLeft = 0; // 인증번호 만료까지 남은 초

  @override
  void dispose() {
    _timer?.cancel();
    for (final c in [idController, emailController, codeController, pwController, pwConfirmController]) {
      c.dispose();
    }
    super.dispose();
  }

  void _startTimers(int resendAfter, int expiresIn) {
    _timer?.cancel();
    setState(() {
      resendLeft = resendAfter;
      expireLeft = expiresIn;
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return t.cancel();
      setState(() {
        if (resendLeft > 0) resendLeft--;
        if (expireLeft > 0) expireLeft--;
      });
      if (resendLeft == 0 && expireLeft == 0) t.cancel();
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      busy = true;
      error = '';
    });
    try {
      await action();
    } catch (e) {
      debugPrint('비밀번호 찾기 오류: $e');
      if (mounted) setState(() => error = '서버에 연결할 수 없어요. 잠시 후 다시 해 주세요.');
    }
    if (mounted) setState(() => busy = false);
  }

  // 1단계 / 재발송: 인증번호 받기
  Future<void> requestCode() async {
    final id = idController.text.trim();
    final email = emailController.text.trim();
    if (id.isEmpty || email.isEmpty) {
      setState(() => error = '아이디와 가입한 이메일을 모두 입력해 주세요.');
      return;
    }
    await _run(() async {
      final response = await ApiClient.post('/api/auth/password-reset/request',
          body: {'id': id, 'email': email});
      if (!mounted) return;
      if (response.statusCode != 200) {
        setState(() => error = ApiClient.errorMessage(response));
        return;
      }
      final data = ApiClient.decode(response);
      codeController.clear();
      setState(() {
        notice = (data['message'] ?? '').toString();
        step = _Step.code;
      });
      _startTimers(data['resend_after_seconds'] ?? 60, data['expires_in_seconds'] ?? 600);
    });
  }

  // 2단계: 인증번호 확인
  Future<void> verifyCode() async {
    final code = codeController.text.trim();
    if (code.length != 6) {
      setState(() => error = '메일로 받은 6자리 숫자를 넣어 주세요.');
      return;
    }
    await _run(() async {
      final response = await ApiClient.post('/api/auth/password-reset/verify', body: {
        'id': idController.text.trim(),
        'email': emailController.text.trim(),
        'code': code,
      });
      if (!mounted) return;
      if (response.statusCode != 200) {
        setState(() => error = ApiClient.errorMessage(response));
        return;
      }
      _timer?.cancel();
      setState(() {
        resetToken = (ApiClient.decode(response)['reset_token'] ?? '').toString();
        step = _Step.password;
        notice = '';
      });
    });
  }

  // 3단계: 새 비밀번호
  Future<void> savePassword() async {
    final pw = pwController.text;
    if (!isStrongPassword(pw)) {
      setState(() => error = '비밀번호 규칙을 확인해 주세요. ($kPasswordGuide)');
      return;
    }
    if (pw != pwConfirmController.text) {
      setState(() => error = '비밀번호 확인이 일치하지 않아요.');
      return;
    }
    await _run(() async {
      final response = await ApiClient.post('/api/auth/password-reset/confirm',
          body: {'reset_token': resetToken, 'new_password': pw});
      if (!mounted) return;
      if (response.statusCode != 200) {
        setState(() => error = ApiClient.errorMessage(response));
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(ApiClient.errorMessage(response, '비밀번호를 새로 만들었어요.'))));
      Navigator.pop(context); // 로그인 화면으로
    });
  }

  // ---------- 화면 ----------
  String _mmss(int seconds) =>
      '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';

  InputDecoration _decoration(String hint, IconData icon) => InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white38),
        prefixIcon: Icon(icon, color: Colors.white54),
        filled: true,
        fillColor: _field,
        counterText: '',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: BorderSide.none,
        ),
      );

  Widget _button(String label, VoidCallback? onTap) => SizedBox(
        width: double.infinity,
        height: 56,
        child: ElevatedButton(
          onPressed: busy ? null : onTap,
          style: ElevatedButton.styleFrom(
            backgroundColor: _purple,
            foregroundColor: Colors.white,
            disabledBackgroundColor: _purple.withOpacity(0.4),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          ),
          child: busy
              ? const SizedBox(
                  width: 22, height: 22,
                  child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
              : Text(label, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
        ),
      );

  Widget _guide(String text, {IconData icon = Icons.info_outline, Color color = Colors.white54}) =>
      Padding(
        padding: const EdgeInsets.only(top: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 6),
            Expanded(child: Text(text, style: TextStyle(color: color, fontSize: 13, height: 1.45))),
          ],
        ),
      );

  List<Widget> _infoStep() => [
        const Text('가입할 때 쓴 아이디와 이메일을 넣어 주세요.\n이메일로 6자리 인증번호를 보내 드릴게요.',
            style: TextStyle(color: Colors.white70, height: 1.6)),
        const SizedBox(height: 24),
        TextField(
          controller: idController,
          style: const TextStyle(color: Colors.white),
          textInputAction: TextInputAction.next,
          decoration: _decoration('아이디', Icons.person),
        ),
        const SizedBox(height: 14),
        TextField(
          controller: emailController,
          style: const TextStyle(color: Colors.white),
          keyboardType: TextInputType.emailAddress,
          onSubmitted: (_) => requestCode(),
          decoration: _decoration('가입한 이메일', Icons.mail_outline),
        ),
        const SizedBox(height: 22),
        _button('인증번호 받기', requestCode),
        const SizedBox(height: 6),
        _guide('카카오/네이버/구글로 가입했다면 비밀번호는 카카오/네이버/구글에서 관리해요. 로그인 화면에서 간편 로그인을 눌러 주세요.'),
        _guide('이용이 정지된 계정은 비밀번호를 다시 만들 수 없어요.'),
      ];

  List<Widget> _codeStep() => [
        if (notice.isNotEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _purple.withOpacity(0.12),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(notice, style: const TextStyle(color: Colors.white, height: 1.5)),
          ),
        const SizedBox(height: 20),
        TextField(
          controller: codeController,
          autofocus: true,
          maxLength: 6,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          onSubmitted: (_) => verifyCode(),
          style: const TextStyle(color: Colors.white, fontSize: 22, letterSpacing: 8),
          decoration: _decoration('인증번호 6자리', Icons.pin),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 8, left: 4),
          child: Text(
            expireLeft > 0 ? '남은 시간 ${_mmss(expireLeft)}' : '인증번호 시간이 지났어요. 다시 받아 주세요.',
            style: TextStyle(color: expireLeft > 0 ? Colors.white54 : Colors.orangeAccent, fontSize: 13),
          ),
        ),
        const SizedBox(height: 18),
        _button('확인', expireLeft > 0 ? verifyCode : null),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            TextButton(
              onPressed: busy ? null : () => setState(() {
                    step = _Step.info;
                    error = '';
                  }),
              child: const Text('아이디/이메일 다시 쓰기', style: TextStyle(color: Colors.white54)),
            ),
            TextButton(
              onPressed: busy || resendLeft > 0 ? null : requestCode,
              child: Text(
                resendLeft > 0 ? '다시 받기 ($resendLeft초)' : '인증번호 다시 받기',
                style: TextStyle(color: resendLeft > 0 ? Colors.white24 : Colors.purpleAccent),
              ),
            ),
          ],
        ),
        _guide('메일이 안 보이면 스팸함도 확인해 주세요. 5번 틀리면 인증번호를 다시 받아야 해요.'),
      ];

  List<Widget> _passwordStep() {
    final pw = pwController.text;
    final strong = isStrongPassword(pw);
    final same = pw.isNotEmpty && pw == pwConfirmController.text;
    return [
      const Text('새로 쓸 비밀번호를 만들어 주세요.',
          style: TextStyle(color: Colors.white70, height: 1.6)),
      const SizedBox(height: 20),
      TextField(
        controller: pwController,
        obscureText: true,
        autofocus: true,
        onChanged: (_) => setState(() {}),
        style: const TextStyle(color: Colors.white),
        decoration: _decoration('새 비밀번호', Icons.lock),
      ),
      _guide(kPasswordGuide,
          icon: strong ? Icons.check_circle : Icons.info_outline,
          color: pw.isEmpty ? Colors.white54 : (strong ? Colors.greenAccent : Colors.orangeAccent)),
      const SizedBox(height: 14),
      TextField(
        controller: pwConfirmController,
        obscureText: true,
        onChanged: (_) => setState(() {}),
        onSubmitted: (_) => savePassword(),
        style: const TextStyle(color: Colors.white),
        decoration: _decoration('새 비밀번호 확인', Icons.lock_outline),
      ),
      if (pwConfirmController.text.isNotEmpty)
        _guide(same ? '비밀번호가 일치해요.' : '비밀번호가 일치하지 않아요.',
            icon: same ? Icons.check_circle : Icons.error_outline,
            color: same ? Colors.greenAccent : Colors.orangeAccent),
      const SizedBox(height: 22),
      _button('비밀번호 바꾸기', savePassword),
    ];
  }

  @override
  Widget build(BuildContext context) {
    const titles = {_Step.info: '1. 계정 확인', _Step.code: '2. 인증번호 확인', _Step.password: '3. 새 비밀번호'};
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: Colors.white,
        title: const Text('비밀번호 찾기', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Container(
            width: 420,
            padding: const EdgeInsets.all(28),
            decoration: BoxDecoration(
              color: _card,
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(titles[step]!,
                    style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
                const SizedBox(height: 14),
                ...switch (step) {
                  _Step.info => _infoStep(),
                  _Step.code => _codeStep(),
                  _Step.password => _passwordStep(),
                },
                if (error.isNotEmpty) _guide(error, icon: Icons.error_outline, color: Colors.redAccent),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
