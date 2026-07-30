import 'package:fairytale_hyeonlim_merged/models/character_profile.dart';
import 'package:fairytale_hyeonlim_merged/widgets/character_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('bundled catalog keeps eight profiles for each gender', () {
    expect(
      CharacterProfileCatalog.defaults
          .where((profile) => profile.gender == 'male'),
      hasLength(8),
    );
    expect(
      CharacterProfileCatalog.defaults
          .where((profile) => profile.gender == 'female'),
      hasLength(8),
    );
    expect(CharacterProfileCatalog.defaults.first.displayName, '민호');
  });

  testWidgets('selects a profile and switches gender tabs', (tester) async {
    const profiles = [
      CharacterProfile(
        characterKey: 'demo_male',
        name: 'Minho',
        gender: 'male',
        ageGroup: 'child',
        description: 'A brave child.',
        roleTags: ['hero'],
      ),
      CharacterProfile(
        characterKey: 'demo_female',
        name: 'Mina',
        gender: 'female',
        ageGroup: 'child',
        description: 'A bright mage.',
        roleTags: ['mage'],
      ),
    ];
    String? selectedKey;

    await tester.pumpWidget(
      MaterialApp(
        home: StatefulBuilder(
          builder: (context, setState) => Scaffold(
            body: CharacterPicker(
              profiles: profiles,
              loadRemoteProfiles: false,
              selectedCharacterKey: selectedKey,
              onSelected: (profile) {
                setState(() => selectedKey = profile.characterKey);
              },
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('character-card-demo_male')));
    await tester.pump();
    expect(selectedKey, 'demo_male');
    expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);
    expect(find.byType(ClipOval), findsOneWidget);
    expect(find.byType(ListView), findsOneWidget);
    expect(find.byType(GridView), findsNothing);

    await tester.tap(find.text('여자'));
    await tester.pump();
    expect(find.byKey(const Key('character-card-demo_female')), findsOneWidget);

    await tester.tap(find.byKey(const Key('character-card-demo_female')));
    await tester.pump();
    expect(selectedKey, 'demo_female');
  });
}
