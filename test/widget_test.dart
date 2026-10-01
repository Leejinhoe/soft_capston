import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fairytale_hyeonlim_merged/login_page.dart';
import 'package:fairytale_hyeonlim_merged/main.dart';

void main() {
  testWidgets('login screen renders title', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: LoginPage()));

    expect(find.text('동화 AI'), findsOneWidget);
  });

  testWidgets('dark app bar titles remain readable', (tester) async {
    await tester.pumpWidget(const FairyTaleApp());
    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.theme!.appBarTheme.titleTextStyle!.color, Colors.white);
  });
}
