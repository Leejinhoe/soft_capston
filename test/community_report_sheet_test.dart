import 'package:fairytale_hyeonlim_merged/community_report_sheet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('로그인하지 않은 사용자는 신고 접수 화면 대신 안내를 본다', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () => showCommunityReportSheet(
                context,
                targetType: 'post',
                targetId: 'post',
                accountId: null,
              ),
              child: const Text('열기'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('열기'));
    await tester.pumpAndSettle();
    expect(find.text('신고하려면 로그인해 주세요.'), findsOneWidget);
    expect(find.text('게시글 신고하기'), findsNothing);
  });

  testWidgets('신고 사유를 선택해야 접수할 수 있다', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => TextButton(
              onPressed: () => showCommunityReportSheet(
                context,
                targetType: 'comment',
                targetId: 'comment',
                postId: 'post',
                accountId: 'user',
              ),
              child: const Text('열기'),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('열기'));
    await tester.pumpAndSettle();
    expect(find.text('댓글 신고하기'), findsOneWidget);
    var button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '신고하기'),
    );
    expect(button.onPressed, isNull);
    await tester.tap(find.text('기타'));
    await tester.pump();
    button = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '신고하기'),
    );
    expect(button.onPressed, isNotNull);
    await tester.ensureVisible(find.text('신고하기'));
    await tester.tap(find.text('신고하기'));
    await tester.pump();
    expect(find.text('신고 내용을 입력해 주세요.'), findsOneWidget);
  });
}
