import 'package:fairytale_hyeonlim_merged/models/media_readiness.dart';
import 'package:fairytale_hyeonlim_merged/widgets/media_readiness_widget.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows media preparation progress and character counts', (
    tester,
  ) async {
    const readiness = MediaReadiness(
      progressPercent: 80,
      readyProfiles: 4,
      targetProfiles: 5,
      readyAssets: 8,
      targetAssets: 10,
      workerRunning: true,
      characters: [
        CharacterReadiness(
          characterKey: 'fantasy_mina',
          name: '미나',
          assetCount: 2,
          targetAssetCount: 2,
          ready: true,
        ),
      ],
      queue: MediaQueueStatus(pending: 1, running: 1, completed: 3, failed: 0),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MediaReadinessWidget(
            readiness: readiness,
            isLoading: false,
            error: null,
            onRefresh: () {},
          ),
        ),
      ),
    );

    expect(find.text('미디어 준비 현황'), findsOneWidget);
    expect(find.text('80%'), findsOneWidget);
    expect(find.text('캐릭터 4/5'), findsOneWidget);
    expect(find.text('이미지 8/10'), findsOneWidget);
    expect(find.text('생성 서버 정상'), findsOneWidget);
    expect(find.text('미나'), findsOneWidget);
    expect(find.text('2/2장'), findsOneWidget);
  });

  testWidgets(
    'shows an actionable warning when integrated image URL is missing',
    (tester) async {
      final readiness = MediaReadiness.fromJson({
        'status': 'ok',
        'progress_percent': 100,
        'profiles': {'ready': 1, 'target': 1},
        'assets': {'ready': 8, 'target': 8},
        'worker': {'running': true},
        'provider': {
          'mode': 'integrated_server',
          'configured': false,
          'configuration_error': 'DB 서버 환경에 AI_API_BASE_URL을 설정해야 합니다.',
        },
        'queue': {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0},
        'characters': [],
      });

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MediaReadinessWidget(
              readiness: readiness,
              isLoading: false,
              error: null,
              onRefresh: () {},
            ),
          ),
        ),
      );

      expect(find.text('삽화 서버 주소 미설정'), findsOneWidget);
      expect(find.text('DB 서버 환경에 AI_API_BASE_URL을 설정해야 합니다.'), findsOneWidget);
    },
  );

  testWidgets('shows when the configured integrated server is unreachable', (
    tester,
  ) async {
    final readiness = MediaReadiness.fromJson({
      'status': 'ok',
      'progress_percent': 100,
      'profiles': {'ready': 1, 'target': 1},
      'assets': {'ready': 8, 'target': 8},
      'worker': {'running': true},
      'provider': {
        'mode': 'integrated_server',
        'configured': true,
        'reachable': false,
        'connection_error': '통합 서버에 연결할 수 없습니다. Colab 서버와 터널 주소를 확인하세요.',
      },
      'queue': {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0},
      'characters': [],
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MediaReadinessWidget(
            readiness: readiness,
            isLoading: false,
            error: null,
            onRefresh: () {},
          ),
        ),
      ),
    );

    expect(find.text('통합 서버 연결 확인 필요'), findsOneWidget);
    expect(
      find.text('통합 서버에 연결할 수 없습니다. Colab 서버와 터널 주소를 확인하세요.'),
      findsOneWidget,
    );
  });
}
