import 'package:flutter/material.dart';
import 'package:kakao_flutter_sdk_common/kakao_flutter_sdk_common.dart';
import 'package:media_kit/media_kit.dart';

import 'core/api_client.dart';
import 'core/auth_service.dart';
import 'pages/login_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();

  // Kakao SDK 초기화
  KakaoSdk.init(
    nativeAppKey: 'fa2f07355c5d24ed9b226ff59a91d57a',
  );

  // 토큰 만료/정지 시 로그인 화면으로 보내는 처리 등록
  AuthService.init();

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
      navigatorKey: appNavigatorKey,
      scaffoldMessengerKey: appMessengerKey,

      // 앱 시작: 저장된 토큰이 있으면 자동 로그인, 없으면 로그인 화면
      home: const AuthGate(),

      routes: {
        '/login': (context) => const LoginPage(),
      },
    );
  }
}
