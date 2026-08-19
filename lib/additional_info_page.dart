import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'main_screen.dart';
import 'models/app_state.dart';
import 'services/db_service.dart';

class AdditionalInfoPage extends StatefulWidget {
  final String accountId;
  final bool returnToPrevious;

  const AdditionalInfoPage({
    super.key,
    required this.accountId,
    this.returnToPrevious = false,
  });

  @override
  State<AdditionalInfoPage> createState() => _AdditionalInfoPageState();
}

class _AdditionalInfoPageState extends State<AdditionalInfoPage> {
  final TextEditingController _nicknameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _emailCodeController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _addressController = TextEditingController();
  bool _isLoading = false;
  bool _emailSending = false;
  bool _emailVerifying = false;
  bool _didPrefill = false;
  String? _originalEmail;
  String? _verifiedEmail;
  String? _emailVerificationToken;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_didPrefill) return;
    final state = context.read<AppState>();
    _nicknameController.text = state.currentNickname ?? '';
    _emailController.text = state.currentEmail ?? '';
    _originalEmail = _emailController.text.trim();
    _phoneController.text = state.currentPhone ?? '';
    _addressController.text = state.currentAddress ?? '';
    _didPrefill = true;
  }

  @override
  void dispose() {
    _nicknameController.dispose();
    _emailController.dispose();
    _emailCodeController.dispose();
    _phoneController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  Future<void> _submitExtraInfo() async {
    final email = _emailController.text.trim();
    final originalEmail = (_originalEmail ?? '').trim().toLowerCase();
    final emailChanged = email.toLowerCase() != originalEmail;
    final verifiedEmail = _verifiedEmail?.trim().toLowerCase();
    if (emailChanged &&
        email.isNotEmpty &&
        (verifiedEmail != email.toLowerCase() ||
            _emailVerificationToken == null)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('새 이메일 주소를 먼저 인증해 주세요.')),
      );
      return;
    }
    setState(() => _isLoading = true);

    try {
      final data = await DbService.updateUserProfile(
        accountId: widget.accountId,
        nickname: _nicknameController.text,
        email: email,
        emailVerificationToken: emailChanged ? _emailVerificationToken : null,
        phone: _phoneController.text,
        address: _addressController.text,
      );

      if (!mounted) return;
      context.read<AppState>().updateSignedInProfile(
            nickname: data['nickname']?.toString(),
            email: data['email']?.toString(),
            phone: data['phone']?.toString(),
            address: data['address']?.toString(),
          );
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('계정 정보를 저장했어요.')),
      );
      if (widget.returnToPrevious) {
        Navigator.pop(context);
      } else {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => const MainScreen()),
        );
      }
    } catch (e) {
      debugPrint("서버 연결 에러: $e");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('저장 실패: ${e.toString().replaceAll('Exception: ', '')}'),
        ),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _sendEmailCode() async {
    final email = _emailController.text.trim();
    if (email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('인증할 이메일 주소를 입력해 주세요.')),
      );
      return;
    }
    setState(() {
      _emailSending = true;
      _emailVerificationToken = null;
      _verifiedEmail = null;
    });
    try {
      await DbService.sendEmailVerificationCode(email: email);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('인증번호를 이메일로 보냈습니다.')),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString().replaceAll('Exception: ', ''))),
      );
    } finally {
      if (mounted) setState(() => _emailSending = false);
    }
  }

  Future<void> _verifyEmailCode() async {
    final email = _emailController.text.trim();
    final code = _emailCodeController.text.trim();
    if (email.isEmpty || code.length != 6) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('이메일과 6자리 인증번호를 확인해 주세요.')),
      );
      return;
    }
    setState(() => _emailVerifying = true);
    try {
      final token = await DbService.confirmEmailVerificationCode(
        email: email,
        code: code,
      );
      if (!mounted) return;
      setState(() {
        _emailVerificationToken = token;
        _verifiedEmail = email;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('이메일 인증이 완료되었습니다.')),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString().replaceAll('Exception: ', ''))),
      );
    } finally {
      if (mounted) setState(() => _emailVerifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF06041A),
      appBar: AppBar(
        title: const Text('계정 정보 수정'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 20),
              const Text(
                '동화 AI에서 사용할\n계정 정보를 관리해요',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 40),
              TextField(
                controller: _nicknameController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '닉네임',
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
                controller: _emailController,
                onChanged: (value) {
                  if (_verifiedEmail != null &&
                      _verifiedEmail!.trim().toLowerCase() !=
                          value.trim().toLowerCase()) {
                    setState(() {
                      _verifiedEmail = null;
                      _emailVerificationToken = null;
                    });
                  }
                },
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '이메일',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF160F38),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _emailCodeController,
                      style: const TextStyle(color: Colors.white),
                      keyboardType: TextInputType.number,
                      decoration: InputDecoration(
                        hintText: '인증번호 6자리',
                        hintStyle: const TextStyle(color: Colors.white38),
                        filled: true,
                        fillColor: const Color(0xFF160F38),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: _emailVerifying ? null : _verifyEmailCode,
                    child: _emailVerifying
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('확인'),
                  ),
                  TextButton(
                    onPressed: _emailSending ? null : _sendEmailCode,
                    child: _emailSending
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('인증 발송'),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _phoneController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '전화번호 (선택)',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF160F38),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
                keyboardType: TextInputType.phone,
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _addressController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: '주소 (선택)',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF160F38),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const Spacer(),
              ElevatedButton(
                onPressed: _isLoading ? null : _submitExtraInfo,
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
                    : Text(
                        widget.returnToPrevious ? '저장하기' : '저장하고 시작하기',
                        style: const TextStyle(
                          fontSize: 16,
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
