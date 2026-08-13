import 'package:flutter_test/flutter_test.dart';

import 'package:fairytale_hyeonlim_merged/models/story_video.dart';

void main() {
  test('maps bridge choices to the castle bridge video', () {
    final clip = StoryVideoCatalog.forChapter(
      text: '',
      choice:
          '\uc131\uc73c\ub85c \uac00\uba70 \ub2e4\ub9ac\ub97c \uac74\ub108\uac04\ub2e4',
      chapter: 2,
      genre: '\ubaa8\ud5d8',
      characterKey: 'male_01',
    );

    expect(clip?.id, 'bridge_to_castle');
  });

  test('maps treasure choices to the hidden treasure video', () {
    final clip = StoryVideoCatalog.forChapter(
      text: '',
      choice: '\ubcf4\ubb3c\uc0c1\uc790\ub97c \uc5f4\uc5b4\ubcf8\ub2e4',
      chapter: 3,
      genre: '\ud310\ud0c0\uc9c0',
      characterKey: 'male_01',
    );

    expect(clip?.id, 'hidden_treasure');
  });

  test('maps lantern choices to the lantern path video', () {
    final clip = StoryVideoCatalog.forChapter(
      text: '',
      choice:
          '\uc9c0\ub3c4\ub97c \ubcf4\uba70 \ub4f1\ubd88\uc744 \ucc3e\ub294\ub2e4',
      chapter: 2,
      genre: '\uc790\uc5f0',
      characterKey: 'male_01',
    );

    expect(clip?.id, 'lantern_path');
  });

  test('maps door choices to the forest door adventure video', () {
    final clip = StoryVideoCatalog.forChapter(
      text: '',
      choice: '\ub9c8\ubc95\uc758 \ubb38\uc744 \uc5f4\uc5b4\ubcf8\ub2e4',
      chapter: 1,
      genre: '\ud310\ud0c0\uc9c0',
      characterKey: 'male_01',
    );

    expect(clip?.id, 'forest_door_adventure');
  });

  test('does not show a clip made with a different character', () {
    final clip = StoryVideoCatalog.forChapter(
      text: '',
      choice: '\ubcf4\ubb3c\uc0c1\uc790\ub97c \uc5f4\uc5b4\ubcf8\ub2e4',
      chapter: 1,
      genre: '\ud310\ud0c0\uc9c0',
      characterKey: 'female_01',
    );

    expect(clip, isNull);
  });

  test('does not use an unrelated fallback clip', () {
    final clip = StoryVideoCatalog.forChapter(
      text: '\uc870\uc6a9\ud788 \ud558\ub298\uc744 \ubc14\ub77c\ubcf8\ub2e4',
      choice: null,
      chapter: 4,
      genre: '\ud310\ud0c0\uc9c0',
      characterKey: 'male_01',
    );

    expect(clip, isNull);
  });
}
