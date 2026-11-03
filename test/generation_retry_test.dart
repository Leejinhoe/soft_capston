import 'dart:convert';

import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

StorySession makeStory(List<StoryChapter> chapters) => StorySession(
  storyId: 'story', dbStoryId: 'db-story', genre: 'fantasy', age: '7',
  initialPrompt: 'test', chapters: chapters, choices: [], choiceOptions: [],
  vocab: [], allChoicesMade: ['choice'], currentChapter: chapters.length,
);

void main() {
  test('video retry kind is restored from saved scene', () {
    final story = StorySession.fromDatabaseJson({
      'id': 'db-story',
      'scenes': [
        {'step_number': 1, 'story_text': 'scene', 'media_status': 'failed',
         'media_requested_video': true},
      ],
    });
    expect(story.chapters.single.mediaRetryVideo, isTrue);
  });

  test('failed scene is retried before later progress is saved', () async {
    final state = AppState()..currentUserId = 'user';
    final chapters = [
      StoryChapter(chapter: 1, text: 'first', imageUrl: 'http://image/1'),
      StoryChapter(chapter: 2, text: 'second', imageUrl: 'http://image/2'),
    ];
    final story = makeStory(chapters);
    final steps = <int>[];
    var failFirst = true;
    var readingWrites = 0;
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/scenes')) {
        final step = (jsonDecode(request.body) as Map)['step_number'] as int;
        steps.add(step);
        if (step == 1 && failFirst) return http.Response('', 503);
        return http.Response('{}', 200);
      }
      if (request.url.path.endsWith('/reading-state')) {
        readingWrites++;
        return http.Response('{}', 200);
      }
      return http.Response('', 404);
    });
    await http.runWithClient(() async {
      await state.syncChapterForTesting(story, chapters[0]);
      expect(readingWrites, 0);
      expect(state.storySyncError, isNotNull);
      failFirst = false;
      await state.syncChapterForTesting(story, chapters[1]);
    }, () => client);
    expect(steps, [1, 1, 2]);
    expect(readingWrites, 1);
    expect(state.storySyncError, isNull);
    expect(story.syncedChapterNumbers, containsAll([1, 2]));
    state.dispose();
  });

  test('video retry stays a video request when an image already exists', () async {
    final state = AppState();
    final chapter = StoryChapter(chapter: 1, text: 'scene', imageUrl: 'http://image/1');
    final story = makeStory([chapter]);
    story.syncedChapterNumbers.add(1);
    final requests = <bool>[];
    final client = MockClient((request) async {
      requests.add((jsonDecode(request.body) as Map)['include_video'] as bool);
      if (requests.length == 1) return http.Response('', 503);
      return http.Response(jsonEncode({
        'job_id': 'video-job', 'status': 'completed',
        'request': {'include_video': true},
        'result': {'image_url': '/api/media/images/1', 'video_url': '/api/media/videos/2'},
      }), 200);
    });
    await http.runWithClient(() async {
      await state.generateVideoForChapter(story, chapter);
      expect(chapter.mediaStatus, 'failed');
      expect(chapter.mediaRetryVideo, isTrue);
      await state.retryMediaForChapter(story, chapter);
    }, () => client);
    expect(requests, [true, true]);
    expect(chapter.videoUrl, endsWith('/api/media/videos/2'));
    state.dispose();
  });
}
