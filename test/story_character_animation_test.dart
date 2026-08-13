import 'package:fairytale_hyeonlim_merged/widgets/story_character_animation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('supports movement for every bundled character profile', () {
    for (final gender in ['male', 'female']) {
      for (var index = 1; index <= 8; index++) {
        final key = '${gender}_${index.toString().padLeft(2, '0')}';
        expect(
          StoryCharacterAnimation.supports(
            characterKey: key,
            storyText: 'The hero runs toward the castle.',
          ),
          isTrue,
          reason: key,
        );
      }
    }
  });

  test('does not animate dialogue, stationary scenes, or unknown profiles', () {
    expect(
      StoryCharacterAnimation.supports(
        characterKey: 'male_01',
        storyText: 'The hero said, "Let us go together."',
      ),
      isFalse,
    );
    expect(
      StoryCharacterAnimation.supports(
        characterKey: 'male_01',
        storyText: 'The hero reads a map in silence.',
      ),
      isFalse,
    );
    expect(
      StoryCharacterAnimation.supports(
        characterKey: 'custom_hero',
        storyText: 'The hero runs toward the castle.',
      ),
      isFalse,
    );
  });

  testWidgets('bundles normalized run cycles for all character profiles', (
    tester,
  ) async {
    for (final gender in ['male', 'female']) {
      for (var index = 1; index <= 8; index++) {
        final key = '${gender}_${index.toString().padLeft(2, '0')}';
        final data = await rootBundle.load(
          'assets/characters/motion_sheets/${key}_run_cycle_v16.png',
        );
        expect(data.lengthInBytes, greaterThan(1000), reason: key);
      }
    }
  });

  testWidgets('renders and pauses the movement animation', (tester) async {
    await tester.binding.setSurfaceSize(const Size(800, 600));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 720,
              child: StoryCharacterAnimation(
                characterKey: 'male_01',
                storyText: 'Mino runs toward the castle.',
                genre: 'fantasy',
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

    expect(
      find.byKey(const Key('story-character-animation-movement')),
      findsOneWidget,
    );
    expect(find.byIcon(Icons.pause), findsOneWidget);

    await tester.tap(
      find.byKey(const Key('story-character-animation-toggle')),
    );
    await tester.pump();

    expect(find.byIcon(Icons.play_arrow), findsOneWidget);
  });
}
