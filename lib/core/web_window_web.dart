// ignore: avoid_web_libraries_in_flutter, deprecated_member_use
import 'dart:html' as html;

String currentUrl() => html.window.location.href;

String? sessionGet(String key) => html.window.sessionStorage[key];

void sessionSet(String key, String value) =>
    html.window.sessionStorage[key] = value;

void sessionRemove(String key) => html.window.sessionStorage.remove(key);

void replaceUrl(String path) => html.window.history.replaceState(null, '', path);

void navigateTo(String url) => html.window.location.href = url;
