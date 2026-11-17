import 'package:flutter/material.dart';

import 'app_theme.dart';
import 'services/db_service.dart';

class PasswordResetPage extends StatefulWidget {
  const PasswordResetPage({super.key, this.initialAccountId = ''});

  final String initialAccountId;

  @override
  State<PasswordResetPage> createState() => _PasswordResetPageState();
}

class _PasswordResetPageState extends State<PasswordResetPage> {
  static const _background = AppColors.pageBackground;
  static const _surface = AppColors.pageSurface;
  static const _accent = AppColors.p500;

  final _accountController = TextEditingController();
  final _emailController = TextEditingController();
  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmController = TextEditingController();

  int _step = 0;
  bool _busy = false;
  String? _resetToken;

  @override
  void initState() {
    super.initState();
    _accountController.text = widget.initialAccountId;
  }

  @override
  void dispose() {
    _accountController.dispose();
    _emailController.dispose();
    _codeController.dispose();
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _sendCode() async {
    final accountId = _accountController.text.trim();
    final email = _emailController.text.trim();
    if (accountId.isEmpty || email.isEmpty) {
      _showMessage('아이디와 가입 이메일을 입력해 주세요.');
      return;
    }
    setState(() => _busy = true);
    try {
      await DbService.requestPasswordResetCode(
        accountId: accountId,
        email: email,
      );
      if (!mounted) return;
      setState(() => _step = 1);
      _showMessage('가입 정보가 일치하면 이메일로 인증번호가 도착해요.');
    } catch (error) {
      _showMessage(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _verifyCode() async {
    final code = _codeController.text.trim();
    if (code.length != 6 || !RegExp(r'^\d{6}$').hasMatch(code)) {
      _showMessage('이메일로 받은 6자리 인증번호를 입력해 주세요.');
      return;
    }
    setState(() => _busy = true);
    try {
      final token = await DbService.verifyPasswordResetCode(
        accountId: _accountController.text,
        email: _emailController.text,
        code: code,
      );
      if (!mounted) return;
      setState(() {
        _resetToken = token;
        _step = 2;
      });
    } catch (error) {
      _showMessage(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  bool _isStrongPassword(String value) {
    return value.length >= 9 &&
        value.length <= 16 &&
        RegExp(r'[A-Za-z]').hasMatch(value) &&
        RegExp(r'\d').hasMatch(value) &&
        RegExp(r'[!@#$%^&*(),.?":{}|<>]').hasMatch(value);
  }

  Future<void> _savePassword() async {
    final password = _passwordController.text;
    if (!_isStrongPassword(password)) {
      _showMessage('영문·숫자·특수문자를 포함한 9~16자로 설정해 주세요.');
      return;
    }
    if (password != _confirmController.text) {
      _showMessage('새 비밀번호가 서로 일치하지 않아요.');
      return;
    }
    final token = _resetToken;
    if (token == null || token.isEmpty) {
      _showMessage('이메일 인증을 먼저 완료해 주세요.');
      return;
    }

    setState(() => _busy = true);
    try {
      await DbService.confirmPasswordReset(
        resetToken: token,
        newPassword: password,
      );
      if (!mounted) return;
      _showMessage('비밀번호를 변경했어요. 새 비밀번호로 로그인해 주세요.');
      Navigator.pop(context);
    } catch (error) {
      _showMessage(error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  InputDecoration _decoration(String label, IconData icon) => InputDecoration(
    labelText: label,
    labelStyle: const TextStyle(color: Colors.white60),
    prefixIcon: Icon(icon, color: AppColors.p300),
    filled: true,
    fillColor: AppColors.pageInput,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(18),
      borderSide: const BorderSide(color: AppColors.border),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(18),
      borderSide: const BorderSide(color: AppColors.border),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(18),
      borderSide: const BorderSide(color: _accent, width: 1.5),
    ),
  );

  Widget _stepMarker(int index, String label) {
    final active = _step >= index;
    return Expanded(
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: active ? _accent : Colors.white10,
              shape: BoxShape.circle,
            ),
            child: Text(
              '${index + 1}',
              style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
            ),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: active ? Colors.white : Colors.white38,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _primaryButton(String label, VoidCallback onPressed) {
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        onPressed: _busy ? null : onPressed,
        style: FilledButton.styleFrom(
          backgroundColor: _accent,
          disabledBackgroundColor: _accent.withValues(alpha: 0.45),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 17),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
        child: _busy
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: AppBar(
        backgroundColor: _background,
        title: const Text('비밀번호 재설정'),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(22, 20, 22, 36),
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: _surface,
                  borderRadius: BorderRadius.circular(30),
                  border: Border.all(
                    color: AppColors.p600.withValues(alpha: 0.5),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: _accent.withValues(alpha: 0.12),
                      blurRadius: 38,
                      offset: const Offset(0, 16),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(
                      Icons.lock_reset_rounded,
                      color: _accent,
                      size: 38,
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      '계정으로 돌아갈게요',
                      style: TextStyle(
                        fontSize: 25,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      '가입 아이디와 이메일을 확인한 뒤 새 비밀번호를 설정할 수 있어요.',
                      style: TextStyle(color: Colors.white60, height: 1.55),
                    ),
                    const SizedBox(height: 24),
                    Row(
                      children: [
                        _stepMarker(0, '계정 확인'),
                        _stepMarker(1, '이메일 인증'),
                        _stepMarker(2, '새 비밀번호'),
                      ],
                    ),
                    const SizedBox(height: 24),
                    if (_step == 0) ...[
                      TextField(
                        controller: _accountController,
                        textInputAction: TextInputAction.next,
                        style: const TextStyle(color: Colors.white),
                        decoration: _decoration('아이디', Icons.person_outline),
                      ),
                      const SizedBox(height: 14),
                      TextField(
                        controller: _emailController,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.done,
                        style: const TextStyle(color: Colors.white),
                        decoration: _decoration('가입 이메일', Icons.mail_outline),
                      ),
                      const SizedBox(height: 20),
                      _primaryButton('인증번호 받기', _sendCode),
                    ] else if (_step == 1) ...[
                      TextField(
                        controller: _codeController,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        style: const TextStyle(
                          color: Colors.white,
                          letterSpacing: 5,
                        ),
                        decoration: _decoration('6자리 인증번호', Icons.pin_outlined),
                      ),
                      const SizedBox(height: 8),
                      _primaryButton('이메일 인증하기', _verifyCode),
                      Align(
                        alignment: Alignment.center,
                        child: TextButton(
                          onPressed: _busy ? null : _sendCode,
                          child: const Text('인증번호 다시 받기'),
                        ),
                      ),
                    ] else ...[
                      TextField(
                        controller: _passwordController,
                        obscureText: true,
                        style: const TextStyle(color: Colors.white),
                        decoration: _decoration('새 비밀번호', Icons.lock_outline),
                      ),
                      const SizedBox(height: 14),
                      TextField(
                        controller: _confirmController,
                        obscureText: true,
                        style: const TextStyle(color: Colors.white),
                        decoration: _decoration('새 비밀번호 확인', Icons.lock_reset),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        '영문·숫자·특수문자를 포함해 9~16자로 입력해 주세요.',
                        style: TextStyle(color: Colors.white54, fontSize: 12),
                      ),
                      const SizedBox(height: 20),
                      _primaryButton('비밀번호 변경하기', _savePassword),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
