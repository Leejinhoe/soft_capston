import 'package:fairytale_hyeonlim_merged/main_screen.dart';
import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('home does not show hard-coded recommended stories', (
    tester,
  ) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AppState(),
        child: MaterialApp(home: HomePage(onSelectTab: (_) {})),
      ),
    );

    expect(find.text('추천 동화'), findsNothing);
    expect(find.text('용감한 꼬마 드래곤'), findsNothing);
    expect(find.text('우주로 간 토끼'), findsNothing);
    expect(find.text('여우 마법사의 비밀'), findsNothing);
  });
}
