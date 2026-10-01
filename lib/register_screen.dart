import 'package:flutter/material.dart';

import 'services/db_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _idController = TextEditingController();
  final _passwordController = TextEditingController();
  final _nicknameController = TextEditingController();
  bool _isSubmitting = false;

  @override
  void dispose() {
    _idController.dispose();
    _passwordController.dispose();
    _nicknameController.dispose();
    super.dispose();
  }

  Future<void> _registerUser() async {
    if (_isSubmitting) return;

    final accountId = _idController.text.trim();
    final password = _passwordController.text;
    final nickname = _nicknameController.text.trim();
    if (accountId.isEmpty || password.isEmpty || nickname.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('아이디, 비밀번호, 닉네임을 모두 입력해주세요.')),
      );
      return;
    }

    setState(() => _isSubmitting = true);
    try {
      await DbService.registerUser(
        accountId: accountId,
        password: password,
        nickname: nickname,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('$nickname님, 회원가입이 완료됐어요.')));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.toString().replaceFirst('Exception: ', '')),
        ),
      );
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('회원가입')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _idController,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: '아이디'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _passwordController,
              obscureText: true,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(labelText: '비밀번호'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nicknameController,
              onSubmitted: (_) => _registerUser(),
              decoration: const InputDecoration(labelText: '닉네임'),
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _isSubmitting ? null : _registerUser,
              child: Text(_isSubmitting ? '가입 중...' : '회원가입'),
            ),
          ],
        ),
      ),
    );
  }
}
