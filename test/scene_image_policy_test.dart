import 'package:flutter_test/flutter_test.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/services/scene_image_policy.dart';

Map<String, dynamic> contract({String action = 'conversation', String anchor = 'forest clearing', String character = 'female_01', List<String> props = const []}) => {
  'valid': true, 'action': action, 'visual_anchor': anchor,
  'character_key': character, 'character_keys': [character], 'required_props': props,
};

StoryChapter chapter(int n, Map<String, dynamic>? c, {String? image}) =>
    StoryChapter(chapter: n, text: 'scene', sceneContract: c, imageUrl: image);

void main() {
  const image = '/api/media/images/0123456789abcdef01234567';
  test('reuses the same known quiet scene', () {
    expect(canReusePreviousSceneImage(chapter(1, contract(), image: image), chapter(2, contract())), isTrue);
  });
  test('generates for different place, important action, character or props', () {
    final previous = chapter(1, contract(), image: image);
    expect(canReusePreviousSceneImage(previous, chapter(2, contract(anchor: 'castle'))), isFalse);
    expect(canReusePreviousSceneImage(previous, chapter(2, contract(action: 'journey'))), isFalse);
    expect(canReusePreviousSceneImage(previous, chapter(2, contract(character: 'male_01'))), isFalse);
    expect(canReusePreviousSceneImage(previous, chapter(2, contract(props: ['key']))), isFalse);
  });
  test('generates when prior image, context or validity is missing', () {
    expect(canReusePreviousSceneImage(chapter(1, contract()), chapter(2, contract())), isFalse);
    expect(canReusePreviousSceneImage(chapter(1, null, image: image), chapter(2, contract())), isFalse);
    expect(canReusePreviousSceneImage(chapter(1, contract(), image: image), chapter(2, {...contract(), 'valid': false})), isFalse);
  });
  test('does not replace existing image or reuse nonadjacent scenes', () {
    final previous = chapter(1, contract(), image: image);
    expect(canReusePreviousSceneImage(previous, chapter(2, contract(), image: image)), isFalse);
    expect(canReusePreviousSceneImage(previous, chapter(3, contract())), isFalse);
  });
  test('isSameQuietSceneContract matches before previous imageUrl is ready', () {
    expect(isSameQuietSceneContract(chapter(1, contract()), chapter(2, contract())), isTrue);
    expect(isSameQuietSceneContract(chapter(1, contract()), chapter(2, contract(action: 'journey'))), isFalse);
  });
}
