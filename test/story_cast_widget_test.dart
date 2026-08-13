import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/widgets/story_cast_widget.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses backend story_cast and keeps its fixed identity', () {
    final story = StorySession.fromDatabaseJson({
      'id': 'story-1',
      'genre': 'fantasy',
      'characters': {'hero': "꼬마 용사 '용감이'", 'key_item': "마법의 열쇠 '희망의 열쇠'"},
      'story_cast': [
        {
          'role': 'hero',
          'name': '용감이',
          'character_key': 'fantasy_mina',
          'profile_name': '판타지 미나',
        },
      ],
      'scenes': [
        {'step_number': 1, 'story_text': '용감이는 숲으로 떠났다.'},
      ],
    });

    expect(story.storyCast, hasLength(1));
    expect(story.selectedHeroCharacterKey, 'fantasy_mina');
    expect(story.effectiveStoryCast.single.name, '용감이');
    expect(story.effectiveStoryCast.single.characterKey, 'fantasy_mina');
    expect(story.effectiveStoryCast.single.identityLabel, '판타지 미나');
  });

  test('falls back to characters and excludes key_item', () {
    final story = StorySession(
      storyId: 'story-2',
      genre: 'fantasy',
      age: '7',
      initialPrompt: '용감이의 모험',
      chapters: const [],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      characters: {
        'hero': "꼬마 용사 '용감이'",
        'companion': "숲의 요정 '루나'",
        'key_item': "마법의 열쇠 '희망의 열쇠'",
      },
    );

    expect(story.effectiveStoryCast, hasLength(2));
    expect(
      story.effectiveStoryCast.map((member) => member.name),
      containsAll(['용감이', '루나']),
    );
    expect(
      story.effectiveStoryCast.every(
        (member) => member.identityLabel == '프로필 배정 대기',
      ),
      isTrue,
    );
  });

  test('selected hero falls back to the saved character override', () {
    final story = StorySession(
      storyId: 'story-override',
      genre: 'fantasy',
      age: '7',
      initialPrompt: 'A castle journey',
      chapters: const [],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      characterOverrides: const {'hero': 'male_01'},
    );

    expect(story.selectedHeroCharacterKey, 'male_01');
  });

  test('explicit hero selection takes priority over legacy cast data', () {
    final story = StorySession(
      storyId: 'story-explicit-selection',
      genre: 'fantasy',
      age: '7',
      initialPrompt: 'A castle journey',
      chapters: const [],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      characterOverrides: const {'hero': 'male_01'},
      storyCast: const [
        StoryCastMember(
          role: 'hero',
          name: 'Legacy hero',
          characterKey: 'fantasy_mina',
        ),
      ],
    );

    expect(story.selectedHeroCharacterKey, 'male_01');
    expect(story.effectiveStoryCast.single.characterKey, 'male_01');
    expect(story.effectiveStoryCast.single.identityLabel, '민호');
  });

  testWidgets('opens a compact cast bottom sheet', (tester) async {
    const members = [
      StoryCastMember(
        role: 'hero',
        name: '용감이',
        characterKey: 'adventure_jun',
        profileName: '모험가 준',
      ),
      StoryCastMember(
        role: 'companion',
        name: '루나',
        characterKey: 'fantasy_mina',
        profileName: '판타지 미나',
      ),
    ];

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: StoryCastWidget(members: members)),
      ),
    );

    expect(find.text('등장인물 2명 · 얼굴 고정 완료'), findsOneWidget);
    await tester.tap(find.byKey(const Key('story-cast-open')));
    await tester.pumpAndSettle();

    expect(find.text('등장인물 배정'), findsOneWidget);
    expect(find.text('용감이'), findsOneWidget);
    expect(find.text('주인공 · 모험가 준'), findsOneWidget);
    expect(find.text('루나'), findsOneWidget);
    expect(find.text('동료 · 판타지 미나'), findsOneWidget);
    expect(find.byIcon(Icons.lock_outline_rounded), findsNWidgets(2));
  });
}
