import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('캐릭터 성별 정보를 음성 합성용 값으로 정규화한다', () {
    final male = StoryCharacter.fromJson({'name': '도윤', 'gender': '남성'});
    final female = StoryCharacter.fromJson({'name': '하늘', 'gender': 'female'});
    final unknown = StoryCharacter.fromJson({'name': '구름 용'});

    expect(male.gender, 'male');
    expect(female.gender, 'female');
    expect(unknown.gender, 'unknown');
    expect(male.toJson()['gender'], 'male');
  });
}
