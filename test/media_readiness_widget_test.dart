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
}
