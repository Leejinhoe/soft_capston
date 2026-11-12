/// 웹이 아닌 플랫폼용: 주소창/세션 저장소가 없으므로 빈 동작
String currentUrl() => '';

String? sessionGet(String key) => null;

void sessionSet(String key, String value) {}

void sessionRemove(String key) {}

void replaceUrl(String path) {}

void navigateTo(String url) {}
