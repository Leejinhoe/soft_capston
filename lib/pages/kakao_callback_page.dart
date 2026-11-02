import 'dart:html' as html;
import 'package:flutter/material.dart';

class KakaoCallbackPage extends StatefulWidget {
  const KakaoCallbackPage({super.key});

  @override
  State<KakaoCallbackPage> createState() => _KakaoCallbackPageState();
}

class _KakaoCallbackPageState extends State<KakaoCallbackPage> {
  String? code;
  String? error;

  @override
  void initState() {
    super.initState();

    final uri = Uri.parse(html.window.location.href);

    code = uri.queryParameters['code'];
    error = uri.queryParameters['error'];

    print('인가 코드: $code');
    print('에러: $error');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: code != null
            ? Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              '카카오 로그인 성공 🎉',
              style: TextStyle(fontSize: 20),
            ),
            const SizedBox(height: 20),
            SelectableText('인가 코드:\n$code'),
          ],
        )
            : Text('로그인 실패: $error'),
      ),
    );
  }
}