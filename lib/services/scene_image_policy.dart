import '../models/story_model.dart';

/// Whether two adjacent chapters explicitly describe the same quiet scene.
bool isSameQuietSceneContract(StoryChapter previous, StoryChapter current) {
  if (previous.chapter + 1 != current.chapter) {
    return false;
  }
  final before = previous.sceneContract;
  final after = current.sceneContract;
  if (before == null || after == null || before['valid'] != true || after['valid'] != true) {
    return false;
  }
  String value(Map<String, dynamic> contract, String key) =>
      (contract[key]?.toString() ?? '').trim().toLowerCase();
  const quietActions = {'conversation', 'idle'};
  if (!quietActions.contains(value(before, 'action')) ||
      !quietActions.contains(value(after, 'action'))) {
    return false;
  }
  final anchor = value(before, 'visual_anchor');
  if (anchor.isEmpty || anchor != value(after, 'visual_anchor')) return false;
  final character = value(before, 'character_key');
  if (character.isEmpty || character != value(after, 'character_key')) return false;
  String listKey(Map<String, dynamic> contract, String key) {
    final raw = contract[key];
    if (raw is! List) return '';
    final values = raw.map((item) => item.toString().trim().toLowerCase()).toList()..sort();
    return values.join('|');
  }
  final participants = listKey(before, 'character_keys');
  return participants.isNotEmpty && participants == listKey(after, 'character_keys') &&
      listKey(before, 'required_props') == listKey(after, 'required_props') &&
      value(before, 'target') == value(after, 'target');
}

/// Reuse only when both contracts explicitly identify the same quiet scene.
bool canReusePreviousSceneImage(StoryChapter previous, StoryChapter current) {
  if ((previous.imageUrl?.trim().isEmpty ?? true) ||
      current.imageBytes != null ||
      (current.imageUrl?.trim().isNotEmpty ?? false)) {
    return false;
  }
  return isSameQuietSceneContract(previous, current);
}
