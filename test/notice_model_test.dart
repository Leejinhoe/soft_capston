import 'package:flutter_test/flutter_test.dart';

import 'package:fairytale_hyeonlim_merged/models/notice_model.dart';

void main() {
  test('공지 API 응답을 앱 모델로 변환한다', () {
    final notice = Notice.fromJson({
      'id': 'notice-1',
      'title': '서비스 점검 안내',
      'content': '오늘 밤 서버 점검이 진행됩니다.',
      'is_pinned': true,
      'is_published': true,
      'created_at': '2026-08-12T10:00:00Z',
      'published_at': '2026-08-12T10:00:00Z',
      'email_requested': true,
      'email_delivery_status': 'completed',
      'email_recipient_count': 12,
      'email_sent_count': 12,
      'email_failed_count': 0,
    });

    expect(notice.id, 'notice-1');
    expect(notice.isPinned, isTrue);
    expect(notice.emailRequested, isTrue);
    expect(notice.emailDeliveryStatus, 'completed');
    expect(notice.emailSentCount, 12);
    expect(notice.publishedAt, isNotNull);
  });
}
