import 'package:fairytale_hyeonlim_merged/signup_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('회원가입 화면은 좁은 화면에서도 비밀번호 확인과 이메일 인증을 제공한다', (tester) async {
    tester.view.physicalSize = const Size(320, 700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const MaterialApp(home: SignupPage()));
    expect(find.text('회원가입'), findsWidgets);
    expect(find.text('비밀번호 확인'), findsOneWidget);
    final scrollable = find
        .descendant(
          of: find.byType(SingleChildScrollView),
          matching: find.byType(Scrollable),
        )
        .first;
    await tester.scrollUntilVisible(
      find.widgetWithText(TextField, '이메일 (선택)'),
      200,
      scrollable: scrollable,
    );
    await tester.enterText(
      find.widgetWithText(TextField, '이메일 (선택)'),
      'test@example.com',
    );
    await tester.pump();
    await tester.scrollUntilVisible(
      find.text('인증 발송'),
      200,
      scrollable: scrollable,
    );
    expect(find.text('인증 발송'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('중복검사 후 아이디를 수정하면 기존 검사 결과가 지워진다', (tester) async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/users/check-id');
      return http.Response('{"available":true}', 200);
    });
    await http.runWithClient(() async {
      await tester.pumpWidget(const MaterialApp(home: SignupPage()));
      await tester.enterText(find.byType(TextField).first, 'first-id');
      await tester.tap(find.text('중복검사'));
      await tester.pumpAndSettle();
      expect(find.text('사용 가능한 아이디입니다.'), findsOneWidget);
      await tester.enterText(find.byType(TextField).first, 'another-id');
      await tester.pump();
      expect(find.text('사용 가능한 아이디입니다.'), findsNothing);
    }, () => client);
  });
}
