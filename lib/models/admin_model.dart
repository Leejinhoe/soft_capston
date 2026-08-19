import 'story_model.dart';
import 'notice_model.dart';

class AdminDashboard {
  final AdminStats stats;
  final List<AdminUser> users;
  final List<AdminStory> stories;
  final List<AdminCommunityPost> communityPosts;
  final List<Notice> notices;
  final List<VocabWord> vocabularies;

  const AdminDashboard({
    required this.stats,
    required this.users,
    required this.stories,
    required this.communityPosts,
    required this.notices,
    required this.vocabularies,
  });

  factory AdminDashboard.fromJson(Map<String, dynamic> json) {
    return AdminDashboard(
      stats: AdminStats.fromJson(json['stats'] as Map<String, dynamic>? ?? {}),
      users: (json['users'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(AdminUser.fromJson)
          .toList(),
      stories: (json['stories'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(AdminStory.fromJson)
          .toList(),
      communityPosts: (json['community_posts'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(AdminCommunityPost.fromJson)
          .toList(),
      notices: (json['notices'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(Notice.fromJson)
          .toList(),
      vocabularies: (json['vocabularies'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(VocabWord.fromJson)
          .where((word) => word.hard.trim().isNotEmpty)
          .toList(),
    );
  }
}

class AdminStats {
  final int userCount;
  final int localUserCount;
  final int socialUserCount;
  final int storyCount;
  final int sharedStoryCount;
  final int vocabularyCount;
  final int communityPostCount;
  final int commentCount;
  final int hiddenPostCount;
  final int noticeCount;

  const AdminStats({
    required this.userCount,
    required this.localUserCount,
    required this.socialUserCount,
    required this.storyCount,
    required this.sharedStoryCount,
    required this.vocabularyCount,
    required this.communityPostCount,
    required this.commentCount,
    required this.hiddenPostCount,
    required this.noticeCount,
  });

  factory AdminStats.fromJson(Map<String, dynamic> json) {
    int read(String key) => (json[key] as num?)?.toInt() ?? 0;
    return AdminStats(
      userCount: read('user_count'),
      localUserCount: read('local_user_count'),
      socialUserCount: read('social_user_count'),
      storyCount: read('story_count'),
      sharedStoryCount: read('shared_story_count'),
      vocabularyCount: read('vocabulary_count'),
      communityPostCount: read('community_post_count'),
      commentCount: read('comment_count'),
      hiddenPostCount: read('hidden_post_count'),
      noticeCount: read('notice_count'),
    );
  }
}

class AdminUser {
  final String id;
  final String accountId;
  final String nickname;
  final String? email;
  final String? phone;
  final String? address;
  final String provider;
  final String personalityType;
  final DateTime? createdAt;
  final DateTime? lastLogin;
  final int storyCount;
  final int vocabCount;

  const AdminUser({
    required this.id,
    required this.accountId,
    required this.nickname,
    required this.provider,
    required this.personalityType,
    required this.storyCount,
    required this.vocabCount,
    this.email,
    this.phone,
    this.address,
    this.createdAt,
    this.lastLogin,
  });

  factory AdminUser.fromJson(Map<String, dynamic> json) {
    return AdminUser(
      id: json['id']?.toString() ?? '',
      accountId: json['account_id']?.toString() ?? '',
      nickname: json['nickname']?.toString() ?? '이름 없음',
      email: _nullableText(json['email']),
      phone: _nullableText(json['phone']),
      address: _nullableText(json['address']),
      provider: json['provider']?.toString() ?? 'local',
      personalityType: json['personality_type']?.toString() ?? '분석 전',
      createdAt: _parseDate(json['created_at']),
      lastLogin: _parseDate(json['last_login']),
      storyCount: (json['story_count'] as num?)?.toInt() ?? 0,
      vocabCount: (json['vocab_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class AdminStory {
  final String id;
  final String userId;
  final String authorNickname;
  final String title;
  final String genre;
  final String targetAge;
  final int sceneCount;
  final bool isShared;
  final int likes;
  final int commentCount;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const AdminStory({
    required this.id,
    required this.userId,
    required this.authorNickname,
    required this.title,
    required this.genre,
    required this.targetAge,
    required this.sceneCount,
    required this.isShared,
    required this.likes,
    required this.commentCount,
    this.createdAt,
    this.updatedAt,
  });

  factory AdminStory.fromJson(Map<String, dynamic> json) {
    return AdminStory(
      id: json['id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      authorNickname: json['author_nickname']?.toString() ?? '동화 친구',
      title: json['title']?.toString() ?? '제목 없는 동화',
      genre: json['genre']?.toString() ?? '동화',
      targetAge: json['target_age']?.toString() ?? '',
      sceneCount: (json['scene_count'] as num?)?.toInt() ?? 0,
      isShared: json['is_shared'] as bool? ?? false,
      likes: (json['likes'] as num?)?.toInt() ?? 0,
      commentCount: (json['comment_count'] as num?)?.toInt() ?? 0,
      createdAt: _parseDate(json['created_at']),
      updatedAt: _parseDate(json['updated_at']),
    );
  }
}

class AdminCommunityPost {
  final String id;
  final String authorName;
  final String? authorAccountId;
  final String title;
  final String genre;
  final String preview;
  final DateTime? createdAt;
  final int viewCount;
  final int likeCount;
  final int commentCount;
  final bool isHidden;
  final String moderationStatus;
  final int reportCount;

  const AdminCommunityPost({
    required this.id,
    required this.authorName,
    required this.title,
    required this.genre,
    required this.preview,
    required this.viewCount,
    required this.likeCount,
    required this.commentCount,
    required this.isHidden,
    required this.moderationStatus,
    required this.reportCount,
    this.authorAccountId,
    this.createdAt,
  });

  factory AdminCommunityPost.fromJson(Map<String, dynamic> json) {
    final comments = json['comments'] as List? ?? const [];
    return AdminCommunityPost(
      id: json['id']?.toString() ?? '',
      authorName: json['author_name']?.toString() ?? '동화 친구',
      authorAccountId: _nullableText(json['author_account_id']),
      title: json['title']?.toString() ?? '제목 없는 게시글',
      genre: json['genre']?.toString() ?? '동화',
      preview: json['preview']?.toString() ?? '',
      createdAt: _parseDate(json['created_at']),
      viewCount: (json['view_count'] as num?)?.toInt() ?? 0,
      likeCount: (json['like_count'] as num?)?.toInt() ?? 0,
      commentCount: comments.length,
      isHidden: json['is_hidden'] as bool? ?? false,
      moderationStatus: json['moderation_status']?.toString() ?? 'visible',
      reportCount: (json['report_count'] as num?)?.toInt() ?? 0,
    );
  }
}

DateTime? _parseDate(Object? value) {
  final text = value?.toString();
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
