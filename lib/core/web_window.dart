/// 브라우저 주소창·sessionStorage 다루기 (소셜 로그인용)
/// - 웹: dart:html 사용 (web_window_web.dart)
/// - 안드로이드 등: 아무것도 안 하는 대체 구현 (web_window_stub.dart)
export 'web_window_stub.dart' if (dart.library.html) 'web_window_web.dart';
