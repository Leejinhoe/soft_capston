import 'dart:html' as html;

class NaverOAuthCallback {
  final String? code;
  final String? state;
  final String? error;

  const NaverOAuthCallback({this.code, this.state, this.error});
}

Future<void> beginNaverOAuth(String authorizationUrl) async {
  html.window.location.assign(authorizationUrl);
}

NaverOAuthCallback? consumeNaverOAuthCallback() {
  final uri = Uri.parse(html.window.location.href);
  final code = uri.queryParameters['code'];
  final state = uri.queryParameters['state'];
  final error = uri.queryParameters['error'];
  if (code == null && error == null) return null;
  html.window.history.replaceState(
    null,
    '',
    '${uri.origin}${uri.path}${uri.hasFragment ? '#${uri.fragment}' : ''}',
  );
  return NaverOAuthCallback(code: code, state: state, error: error);
}
