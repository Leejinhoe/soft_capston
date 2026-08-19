class Notice {
  final String id;
  final String title;
  final String content;
  final bool isPinned;
  final bool isPublished;
  final String? authorAccountId;
  final DateTime? createdAt;
  final DateTime? publishedAt;
  final DateTime? updatedAt;
  final bool emailRequested;
  final String emailDeliveryStatus;
  final int emailRecipientCount;
  final int emailSentCount;
  final int emailFailedCount;
  final String? emailDeliveryError;

  const Notice({
    required this.id,
    required this.title,
    required this.content,
    required this.isPinned,
    required this.isPublished,
    required this.emailRequested,
    required this.emailDeliveryStatus,
    required this.emailRecipientCount,
    required this.emailSentCount,
    required this.emailFailedCount,
    this.authorAccountId,
    this.createdAt,
    this.publishedAt,
    this.updatedAt,
    this.emailDeliveryError,
  });

  factory Notice.fromJson(Map<String, dynamic> json) {
    DateTime? date(String key) =>
        DateTime.tryParse(json[key]?.toString() ?? '');
    int count(String key) => (json[key] as num?)?.toInt() ?? 0;
    String? text(String key) {
      final value = json[key]?.toString().trim();
      return value == null || value.isEmpty || value == 'null' ? null : value;
    }

    return Notice(
      id: json['id']?.toString() ?? '',
      title: json['title']?.toString() ?? '공지사항',
      content: json['content']?.toString() ?? '',
      isPinned: json['is_pinned'] as bool? ?? false,
      isPublished: json['is_published'] as bool? ?? true,
      authorAccountId: text('author_account_id'),
      createdAt: date('created_at'),
      publishedAt: date('published_at'),
      updatedAt: date('updated_at'),
      emailRequested: json['email_requested'] as bool? ?? false,
      emailDeliveryStatus:
          json['email_delivery_status']?.toString() ?? 'not_requested',
      emailRecipientCount: count('email_recipient_count'),
      emailSentCount: count('email_sent_count'),
      emailFailedCount: count('email_failed_count'),
      emailDeliveryError: text('email_delivery_error'),
    );
  }
}
