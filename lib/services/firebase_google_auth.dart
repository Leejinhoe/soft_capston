import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class FirebaseGoogleAuth {
  static String _requiredConfig(String key) {
    final value = dotenv.isInitialized ? dotenv.env[key]?.trim() ?? '' : '';
    if (value.isEmpty) {
      throw StateError('Firebase Google 로그인 설정이 없습니다: $key');
    }
    return value;
  }

  static Future<String?> signInAndGetIdToken() async {
    final projectId = _requiredConfig('FIREBASE_PROJECT_ID');
    final options = FirebaseOptions(
      apiKey: _requiredConfig('FIREBASE_API_KEY'),
      appId: _requiredConfig('FIREBASE_WEB_APP_ID'),
      messagingSenderId: _requiredConfig('FIREBASE_MESSAGING_SENDER_ID'),
      projectId: projectId,
      authDomain: _requiredConfig('FIREBASE_AUTH_DOMAIN'),
    );

    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(options: options);
    }

    final provider = GoogleAuthProvider()
      ..setCustomParameters({'prompt': 'select_account'});
    final result = await FirebaseAuth.instance.signInWithPopup(provider);
    final user = result.user;
    if (user == null) return null;

    final token = await user.getIdToken(true);
    if (token == null || token.isEmpty) {
      throw StateError('Firebase에서 로그인 토큰을 받지 못했습니다.');
    }
    return token;
  }
}
