import 'package:flutter_test/flutter_test.dart';

import 'package:fairytale_hyeonlim_merged/models/story_model.dart';

void main() {
  test('parses a partial video result so the scene can be retried', () {
    final result = SceneMediaResult.fromJson({
      'job_id': 'job-1',
      'status': 'partial',
      'error': 'video provider unavailable',
      'request': {'include_video': true},
      'result': {
        'image_url': '/api/media/images/image-1',
        'video_url': null,
        'metadata': {
          'video_status': 'failed',
          'video_error': 'video provider unavailable',
        },
      },
    });

    expect(result.isPartial, isTrue);
    expect(result.hasMedia, isTrue);
    expect(result.includeVideoRequested, isTrue);
    expect(result.videoStatus, 'failed');
    expect(result.error, 'video provider unavailable');
  });
}
