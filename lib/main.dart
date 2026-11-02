import 'package:flutter/material.dart';
import 'package:kakao_flutter_sdk_common/kakao_flutter_sdk_common.dart';

// 페이지 파일 import (프로젝트 구조에 맞게 경로 확인)
import 'pages/login_page.dart';
import 'pages/profile_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Kakao SDK 초기화
  KakaoSdk.init(
    nativeAppKey: 'fa2f07355c5d24ed9b226ff59a91d57a',
  );

  runApp(const FairyTaleApp());
}

class FairyTaleApp extends StatelessWidget {
  const FairyTaleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: '동화 생성 앱',
      theme: ThemeData(
        primarySwatch: Colors.purple,
      ),

      // 1. 앱 시작 시 로그인 페이지를 첫 화면으로 설정
      initialRoute: '/login',

      // 2. 라우트 이름 등록 (로그아웃 시 /login 이동을 위해 필요)
      routes: {
        '/login': (context) => const LoginPage(),
        '/profile': (context) => const ProfilePage(userName: ''),
      },
    );
  }
}