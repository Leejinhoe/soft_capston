import 'package:flutter_test/flutter_test.dart';

import 'package:fairytale_hyeonlim_merged/services/vocabulary_catalog.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('finds bundled dictionary words present in a story', () async {
    final matches = await VocabularyCatalog.findMatches(
      '아이는 가게 앞에서 가격표를 살펴보았어요.',
      sourceStoryTitle: '작은 장보기 모험',
    );

    final words = matches.map((word) => word.hard).toSet();
    expect(words, contains('가게'));
    expect(words, contains('가격표'));
    expect(
      matches.every((word) => word.sourceStoryTitle == '작은 장보기 모험'),
      isTrue,
    );
  });

  test('does not return dictionary entries absent from the story', () async {
    final matches = await VocabularyCatalog.findMatches(
      '토끼가 숲속에서 친구를 만났어요.',
      sourceStoryTitle: '숲속 친구',
    );

    expect(matches.any((word) => word.hard == '가격표'), isFalse);
  });
}
