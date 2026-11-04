import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:test1/widgets/character_strip.dart';

void main() {
  testWidgets('character selection shows the selected gender catalog', (tester) async {
    var gender = 'male';
    var selected = 'male_01';
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: StatefulBuilder(
      builder: (context, setState) => CharacterStrip(
        gender: gender, selectedKey: selected,
        onGenderChanged: (value) => setState(() { gender = value; selected = '${value}_01'; }),
        onSelected: (value) => setState(() => selected = value),
      ),
    ))));
    await tester.pump();
    expect(find.text('민호'), findsOneWidget);
    await tester.tap(find.text('여자'));
    await tester.pump();
    expect(find.text('미나'), findsOneWidget);
    await tester.tap(find.text('하나'));
    await tester.pump();
    expect(selected, 'female_02');
  });
}
