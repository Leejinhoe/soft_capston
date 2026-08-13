import 'package:fairytale_hyeonlim_merged/widgets/story_character_animation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('capture movement animation preview', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1000, 560));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark(useMaterial3: true),
        home: Scaffold(
          backgroundColor: const Color(0xff101427),
          body: Center(
            child: RepaintBoundary(
              key: const Key('free-animation-preview'),
              child: const SizedBox(
                width: 900,
                child: StoryCharacterAnimation(
                  characterKey: 'male_01',
                  storyText: 'Mino runs toward the glowing castle.',
                  genre: 'fantasy',
                ),
              ),
            ),
          ),
        ),
      ),
    );

    await tester.runAsync(
      () => Future<void>.delayed(const Duration(seconds: 2)),
    );
    await tester.pump();
    await tester.tap(
      find.byKey(const Key('story-character-animation-toggle')),
    );
    await tester.pump();

    await expectLater(
      find.byKey(const Key('free-animation-preview')),
      matchesGoldenFile(
        '../output/video_previews/flutter_free_character_animation.png',
      ),
    );
  });
}
