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

  test('supports dedicated action keywords', () {
    for (final story in [
      'The hero jumps over the moon.',
      'The hero attacks the shadow with a sword.',
      'The hero receives the glowing key.',
      'The hero casts a magic spell.',
    ]) {
      expect(
        StoryCharacterAnimation.supports(
          characterKey: 'female_02',
          storyText: story,
        ),
        isTrue,
        reason: story,
      );
    }
  });

  test('selects v28 paths and keeps action scenes stationary', () {
    for (final gender in ['male', 'female']) {
      for (var index = 1; index <= 8; index++) {
        final key = '${gender}_${index.toString().padLeft(2, '0')}';
        for (final action in [
          'jump',
          'battle',
          'interaction',
          'action',
        ]) {
          expect(
            StoryCharacterAnimation.motionSheetAssetPath(
              characterKey: key,
              action: action,
            ),
            endsWith('_v28.png'),
            reason: '$key/$action',
          );
        }
      }
    }

    expect(
      StoryCharacterAnimation.usesMovingBackgroundForStory(
        'The hero runs toward the castle.',
      ),
      isTrue,
    );
    for (final story in [
      'The hero jumps over the moon.',
      'The hero attacks the shadow.',
      'The hero receives the glowing key.',
      'The hero casts a magic spell.',
    ]) {
      expect(
        StoryCharacterAnimation.usesMovingBackgroundForStory(story),
        isFalse,
        reason: story,
      );
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

  testWidgets('bundles v28 action fallback sheets for all character profiles', (
    tester,
  ) async {
    for (final gender in ['male', 'female']) {
      for (var index = 1; index <= 8; index++) {
        final key = '${gender}_${index.toString().padLeft(2, '0')}';
        for (final action in [
          'jump_cycle',
          'battle_cycle',
          'interaction_cycle',
          'action_sheet',
        ]) {
          final data = await rootBundle.load(
            'assets/characters/motion_sheets/${key}_${action}_v23.png',
          );
          expect(data.lengthInBytes, greaterThan(1000), reason: '$key/$action');
          expect(
            StoryCharacterAnimation.motionSheetAssetPath(
              characterKey: key,
              action: action == 'action_sheet' ? 'action' : action.replaceAll('_cycle', ''),
            ),
            'assets/characters/motion_sheets/${key}_${action}_v28.png',
            reason: '$key/$action v28 contract',
          );
        }
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
