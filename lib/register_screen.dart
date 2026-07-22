import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert'; // json 변환용

class RegisterScreen extends StatefulWidget {
  @override
  _RegisterScreenState createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  // 사용자가 입력할 텍스트 컨트롤러
  final TextEditingController idController = TextEditingController();
  final TextEditingController passwordController = TextEditingController();
  final TextEditingController nicknameController = TextEditingController();

  // FastAPI 백엔드로 가입 요청을 보내는 함수
  Future<void> registerUser() async {
    // 안드로이드 에뮬레이터용 로컬 주소 (10.0.2.2)
    final url = Uri.parse('http://192.168.55.233:8000/api/users/register');

    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        // DB 스키마에 맞춰서 JSON 데이터 전송
        body: jsonEncode({
          "account_id": idController.text,
          "password": passwordController.text,
          "nickname": nicknameController.text,
          "provider": "local", // 일단 일반 가입으로 테스트
        }),
      );

      if (response.statusCode == 200) {
        // 가입 성공!
        final responseData = jsonDecode(response.body);
        print("서버 응답: ${responseData['message']}");

        // 성공 팝업 띄우기
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${nicknameController.text}님 가입 성공! DB 확인해보세요!'),
          ),
        );
      } else {
        // 백엔드에는 도착했으나 처리 중 에러 발생
        print("가입 실패: 상태 코드 ${response.statusCode}");
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('가입 실패: 상태 코드 ${response.statusCode}')),
        );
      }
    } catch (e) {
      // 서버 연결 자체가 실패한 경우 (폰 화면에 에러 원인 출력)
      print("서버 연결 에러: $e");
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('통신 에러 원인: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('회원가입 테스트')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: idController,
              decoration: InputDecoration(labelText: '아이디'),
            ),
            TextField(
              controller: passwordController,
              decoration: InputDecoration(labelText: '비밀번호'),
              obscureText: true,
            ),
            TextField(
              controller: nicknameController,
              decoration: InputDecoration(labelText: '닉네임 (ex: 꼬마토끼)'),
            ),
            SizedBox(height: 30),
            ElevatedButton(
              onPressed: registerUser, // 버튼 누르면 통신 함수 실행
              child: Text('가입하기 (DB로 쏘기)'),
            ),
          ],
        ),
      ),
    );
  }
}
