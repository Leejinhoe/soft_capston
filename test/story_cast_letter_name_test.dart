import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/models/character_profile.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('캐릭터 설명 대신 맵의 캐릭터 이름을 편지 수신인으로 쓴다', () {
    final story = StorySession(
      storyId: 'letter-cast',
      genre: '모험',
      age: '',
      initialPrompt: '숲속 우체부',
      chapters: [StoryChapter(chapter: 1, text: '다온이 숲길을 걸었어요.')],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      characters: const {'다온': '밝고 호기심이 많은 어린 도우미예요.', '루루': '숲길을 잘 아는 여우예요.'},
      characterOverrides: const {'hero': 'male_01'},
    );

    final cast = story.effectiveStoryCast;
    expect(cast.map((member) => member.letterDisplayName()).toList(), [
      '다온',
      '루루',
    ]);
    expect(cast.first.role, 'hero');
  });

  test('영문 placeholder 대신 선택한 주인공 프로필 이름을 쓴다', () {
    final story = StorySession(
      storyId: 'letter-placeholder',
      genre: '모험',
      age: '',
      initialPrompt: '숲속 우체부',
      chapters: [StoryChapter(chapter: 1, text: '이야기')],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      characters: const {'hero': 'The selected story protagonist'},
      characterOverrides: const {'hero': 'male_01'},
    );

    expect(
      story.effectiveStoryCast.single.letterDisplayName(),
      CharacterProfileCatalog.defaultNameFor('male_01'),
    );
  });
}
