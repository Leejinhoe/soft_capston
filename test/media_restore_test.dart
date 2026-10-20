import 'package:flutter_test/flutter_test.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:fairytale_hyeonlim_merged/services/db_service.dart';
import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';

void main() {
  test('resuming polls the saved job without submitting another render', () async {
    final requests = <http.Request>[];
    final client = MockClient((request) async {
      requests.add(request);
      return http.Response(jsonEncode({
        'job_id': 'saved-job', 'status': 'completed',
        'result': {'image_url': '/api/media/images/image-1',
                   'video_url': '/api/media/videos/video-1'},
      }), 200);
    });
    final result = await http.runWithClient(() => DbService.generateSceneMedia(
      storyId: 'story', stepNumber: 1, storyText: 'A scene', genre: 'fantasy',
      age: '7', resumeJobId: 'saved-job',
    ), () => client);
    expect(requests.length, 1);
    expect(requests.single.method, 'GET');
    expect(requests.single.url.path, '/api/media/jobs/saved-job');
    expect(result?.status, 'completed');
    expect(result?.videoUrl, endsWith('/api/media/videos/video-1'));
  });
  test('missing persisted job becomes retryable instead of staying running', () {
    final chapter = StoryChapter(chapter: 1, text: 'A scene', mediaStatus: 'running');
    final story = StorySession(
      storyId: 'restore-test', genre: 'fantasy', age: '7', initialPrompt: 'test',
      chapters: [chapter], choices: [], choiceOptions: [], vocab: [],
      allChoicesMade: [], currentChapter: 1,
    );
    final state = AppState();
    state.restoreMediaJobs(story);
    expect(chapter.mediaStatus, 'failed');
    expect(chapter.mediaError, isNotEmpty);
    expect(story.mediaGenerationChapterNumbers, isEmpty);
    state.dispose();
  });
}
