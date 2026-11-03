/// 응답을 받는 대로 읽을 수 있는 http.Client (동화 스트리밍용)
/// - 웹: 기본 http(BrowserClient)는 응답을 끝까지 모았다가 한 번에 줘서, fetch를 쓰는 FetchClient로
/// - 안드로이드 등: 기본 http.Client가 그대로 스트리밍됨
export 'stream_client_io.dart' if (dart.library.js_interop) 'stream_client_web.dart';
