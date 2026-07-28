class ModerationReport {
  final String id;
  final String? reporterAccountId;
  final String targetType;
  final String targetId;
  final String? postId;
  final String reason;
  final String? details;
  final String status;
  final String? actionTaken;
  final String? resolutionNote;
  final DateTime? createdAt;
  final DateTime? resolvedAt;
  final String? resolvedBy;

  const ModerationReport({
    required this.id,
    required this.targetType,
    required this.targetId,
    required this.reason,
    required this.status,
    this.reporterAccountId,
    this.postId,
    this.details,
    this.actionTaken,
    this.resolutionNote,
    this.createdAt,
    this.resolvedAt,
    this.resolvedBy,
  });

  factory ModerationReport.fromJson(Map<String, dynamic> json) {
    return ModerationReport(
      id: json['id']?.toString() ?? '',
      reporterAccountId: _nullableText(json['reporter_account_id']),
      targetType: json['target_type']?.toString() ?? '',
      targetId: json['target_id']?.toString() ?? '',
      postId: _nullableText(json['post_id']),
      reason: json['reason']?.toString() ?? '',
      details: _nullableText(json['details']),
      status: json['status']?.toString() ?? 'pending',
      actionTaken: _nullableText(json['action_taken']),
      resolutionNote: _nullableText(json['resolution_note']),
      createdAt: _parseDate(json['created_at']),
      resolvedAt: _parseDate(json['resolved_at']),
      resolvedBy: _nullableText(json['resolved_by']),
    );
  }

  bool get isPending => status == 'pending';
}

class UserWarning {
  final String id;
  final String userId;
  final String reason;
  final String severity;
  final String status;
  final String? createdBy;
  final DateTime? createdAt;
  final DateTime? expiresAt;
  final DateTime? resolvedAt;

  const UserWarning({
    required this.id,
    required this.userId,
    required this.reason,
    required this.severity,
    required this.status,
    this.createdBy,
    this.createdAt,
    this.expiresAt,
    this.resolvedAt,
  });

  factory UserWarning.fromJson(Map<String, dynamic> json) {
    return UserWarning(
      id: json['id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      reason: json['reason']?.toString() ?? '',
      severity: json['severity']?.toString() ?? 'notice',
      status: json['status']?.toString() ?? 'active',
      createdBy: _nullableText(json['created_by']),
      createdAt: _parseDate(json['created_at']),
      expiresAt: _parseDate(json['expires_at']),
      resolvedAt: _parseDate(json['resolved_at']),
    );
  }

  bool get isActive => status == 'active';
}

class ReportSubmissionResult {
  final String message;
  final bool created;
  final ModerationReport report;

  const ReportSubmissionResult({
    required this.message,
    required this.created,
    required this.report,
  });

  factory ReportSubmissionResult.fromJson(Map<String, dynamic> json) {
    return ReportSubmissionResult(
      message: json['message']?.toString() ?? '',
      created: json['created'] as bool? ?? false,
      report: ModerationReport.fromJson(
        json['report'] as Map<String, dynamic>? ?? const {},
      ),
    );
  }
}

DateTime? _parseDate(Object? value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty || text == 'None' || text == 'null') {
    return null;
  }
  return DateTime.tryParse(text);
}

String? _nullableText(Object? value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty || text == 'None' || text == 'null') {
    return null;
  }
  return text;
}
