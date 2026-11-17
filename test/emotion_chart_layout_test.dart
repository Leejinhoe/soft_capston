import 'package:fairytale_hyeonlim_merged/psych_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('동화별 추이 그래프의 범례로 각 선을 켜고 끌 수 있다', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: EmotionTrendChart(
            labels: const ['행복', '슬픔'],
            points: const [
              {
                'title': '비공개 동화 제목 하나',
                'averages': {'행복': 0.4, '슬픔': 0.6},
              },
              {
                'title': '비공개 동화 제목 둘',
                'averages': {'행복': 0.7, '슬픔': 0.3},
              },
            ],
          ),
        ),
      ),
    );
    expect(find.text('최근 선택 문장 분류 추이'), findsOneWidget);
    expect(find.textContaining('동화 제목은 표시하지 않아요'), findsOneWidget);
    expect(find.textContaining('비공개 동화 제목'), findsNothing);
    expect(
      tester.widget<FilterChip>(find.widgetWithText(FilterChip, '행복')).selected,
      isTrue,
    );
    await tester.tap(find.widgetWithText(FilterChip, '행복'));
    await tester.pump();
    expect(
      tester.widget<FilterChip>(find.widgetWithText(FilterChip, '행복')).selected,
      isFalse,
    );
    expect(tester.takeException(), isNull);
  });

  for (final width in [320.0, 390.0, 1200.0]) {
    testWidgets('감정 레이더는 요청된 6개 감정만 표시한다 ($width)', (tester) async {
      await tester.binding.setSurfaceSize(Size(width, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final scores = {
        '행복': 0.9,
        '중립': 0.8,
        '슬픔': 0.7,
        '공포': 0.6,
        '혐오': 0.99,
        '분노': 0.5,
        '놀람': 0.4,
      };
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: EmotionRadarChart(values: scores, color: Colors.purple),
            ),
          ),
        ),
      );
      expect(find.text('감정 분류 점수'), findsOneWidget);
      for (final emotion in ['행복', '중립', '슬픔', '공포', '분노', '놀람']) {
        expect(find.textContaining(emotion), findsOneWidget);
      }
      expect(find.textContaining('혐오'), findsNothing);
      expect(find.byType(ExpansionTile), findsNothing);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('패널 안의 레이더는 좁은 폭에서도 잘리지 않는다', (tester) async {
    await tester.binding.setSurfaceSize(const Size(320, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(18),
              child: Container(
                padding: const EdgeInsets.all(15),
                child: EmotionRadarChart(
                  values: const {
                    '행복': 0.7,
                    '중립': 0.4,
                    '슬픔': 0.2,
                    '공포': 0.3,
                    '분노': 0.1,
                    '놀람': 0.5,
                  },
                  color: Colors.purple,
                ),
              ),
            ),
          ),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
  });
}
