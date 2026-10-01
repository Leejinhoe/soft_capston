import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/story_page.dart';
import 'package:fairytale_hyeonlim_merged/widgets/story_character_animation.dart';
import 'package:fairytale_hyeonlim_merged/widgets/story_video_player.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  for (final width in [390.0, 1200.0]) {
    testWidgets('motion remains accessible without autoplay at width $width', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(Size(width, 1000));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final story = StorySession(
        storyId: 'mock_motion_preview',
        genre: '판타지',
        age: '',
        initialPrompt: '친구를 찾아가는 모험',
        chapters: [
          StoryChapter(chapter: 1, text: 'The hero runs toward the castle.'),
        ],
        choices: const ['친구와 함께 길을 찾는다'],
        choiceOptions: const [],
        vocab: const [],
        characterOverrides: const {'hero': 'male_01'},
      );
      await tester.pumpWidget(
        ChangeNotifierProvider(
          create: (_) => AppState(),
          child: MaterialApp(home: StoryPage(preloadedStory: story)),
        ),
      );
      await tester.pumpAndSettle();
      final button = find.widgetWithText(OutlinedButton, '캐릭터 움직임 보기');
      await tester.scrollUntilVisible(button, 300);
      expect(button, findsOneWidget);
      expect(find.byType(StoryCharacterAnimation), findsNothing);
      expect(find.byType(StoryVideoPlayer), findsNothing);
      expect(tester.takeException(), isNull);

      await tester.tap(button);
      await tester.pump();
      expect(find.byType(Dialog), findsOneWidget);
      expect(find.byType(StoryCharacterAnimation), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
