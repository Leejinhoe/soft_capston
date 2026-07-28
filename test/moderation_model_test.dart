import 'package:flutter_test/flutter_test.dart';
import 'package:fairytale_hyeonlim_merged/models/moderation_model.dart';

void main() {
  test('ModerationReport parses API response and pending state', () {
    final report = ModerationReport.fromJson({
      'id': 'report-1',
      'reporter_account_id': 'reader@example.com',
      'target_type': 'post',
      'target_id': 'post-1',
      'reason': '부적절한 내용',
      'status': 'pending',
      'created_at': '2026-07-28T10:00:00Z',
    });

    expect(report.id, 'report-1');
    expect(report.reporterAccountId, 'reader@example.com');
    expect(report.isPending, isTrue);
    expect(report.createdAt, DateTime.utc(2026, 7, 28, 10));
  });

  test('UserWarning parses active warning response', () {
    final warning = UserWarning.fromJson({
      'id': 'warning-1',
      'user_id': 'user-1',
      'reason': '커뮤니티 이용 규칙 위반',
      'severity': 'caution',
      'status': 'active',
      'created_at': '2026-07-28T11:00:00Z',
    });

    expect(warning.userId, 'user-1');
    expect(warning.severity, 'caution');
    expect(warning.isActive, isTrue);
  });

  test('ReportSubmissionResult preserves duplicate result', () {
    final result = ReportSubmissionResult.fromJson({
      'message': '이미 접수된 신고입니다.',
      'created': false,
      'report': {
        'id': 'report-1',
        'target_type': 'comment',
        'target_id': 'comment-1',
        'reason': '도배',
        'status': 'pending',
      },
    });

    expect(result.created, isFalse);
    expect(result.report.targetType, 'comment');
  });
}
