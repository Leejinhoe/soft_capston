class NaverOAuthCallback {
  final String? code;
  final String? state;
  final String? error;

  const NaverOAuthCallback({this.code, this.state, this.error});
}

Future<void> beginNaverOAuth(String authorizationUrl) async {
  throw UnsupportedError('네이버 웹 로그인은 Flutter Web에서 사용할 수 있습니다.');
}

NaverOAuthCallback? consumeNaverOAuthCallback() => null;
