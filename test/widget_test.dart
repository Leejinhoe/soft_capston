import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fairytale_hyeonlim_merged/login_page.dart';

void main() {
  testWidgets('login screen renders title', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginPage()));

    expect(find.text('동화 AI'), findsOneWidget);
  });
}
