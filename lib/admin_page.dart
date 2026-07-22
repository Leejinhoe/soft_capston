import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'main.dart';
import 'models/admin_model.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/db_service.dart';

class AdminPage extends StatefulWidget {
  final String adminAccountId;

  const AdminPage({
    super.key,
    required this.adminAccountId,
  });

  @override
  State<AdminPage> createState() => _AdminPageState();
}

class _AdminPageState extends State<AdminPage> {
  AdminDashboard? _dashboard;
  bool _isLoading = true;
  String? _error;
  int _selectedTab = 0;
  String _query = '';

  final _tabs = const ['개요', '회원', '동화', '게시판', '단어장'];

  @override
  void initState() {
    super.initState();
    _loadDashboard();
  }

  Future<void> _loadDashboard() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final dashboard = await DbService.fetchAdminDashboard(
        accountId: widget.adminAccountId,
      );
      if (!mounted) return;
      setState(() => _dashboard = dashboard);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceAll('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _runAdminAction({
    required String title,
    required String message,
    required Future<void> Function() action,
  }) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.card,
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('취소'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.pink),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('실행'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      await action();
      await _loadDashboard();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('관리 작업이 완료되었습니다.')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString().replaceAll('Exception: ', ''))),
      );
    }
  }

  void _logout() {
    context.read<AppState>().clearSignedInUser();
    Navigator.of(context).pushNamedAndRemoveUntil('/', (_) => false);
  }

  @override
  Widget build(BuildContext context) {
    final dashboard = _dashboard;

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadDashboard,
          color: AppColors.p500,
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(child: _buildHeader()),
              SliverToBoxAdapter(child: _buildSearchAndTabs()),
              if (_isLoading)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_error != null)
                SliverFillRemaining(
                  hasScrollBody: false,
                  child: _buildError(),
                )
              else if (dashboard == null)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: Center(child: Text('관리자 데이터를 불러오지 못했습니다.')),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(18, 0, 18, 28),
                  sliver: SliverToBoxAdapter(child: _buildTabBody(dashboard)),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 12),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: const LinearGradient(
            colors: [Color(0xFF26105C), Color(0xFF110023)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          border: Border.all(color: Colors.white12),
          boxShadow: [
            BoxShadow(
              color: AppColors.p700.withValues(alpha: 0.32),
              blurRadius: 30,
              offset: const Offset(0, 16),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: const Icon(
                    Icons.admin_panel_settings_rounded,
                    color: Colors.white,
                    size: 30,
                  ),
                ),
                const SizedBox(width: 14),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '관리자 센터',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 25,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        '회원, 동화, 게시판, 단어장을 한 곳에서 관리합니다.',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: '새로고침',
                  onPressed: _isLoading ? null : _loadDashboard,
                  icon: const Icon(Icons.refresh_rounded),
                ),
                IconButton(
                  tooltip: '로그아웃',
                  onPressed: _logout,
                  icon: const Icon(Icons.logout_rounded),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildHeaderChip('관리자', widget.adminAccountId),
                _buildHeaderChip('API', DbService.baseUrl),
                _buildHeaderChip('상태', _error == null ? '연결됨' : '오류'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white10),
      ),
      child: Text(
        '$label · $value',
        style: const TextStyle(
          color: Colors.white,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _buildSearchAndTabs() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 4, 18, 18),
      child: Column(
        children: [
          TextField(
            onChanged: (value) => setState(() => _query = value.trim()),
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: '회원, 동화 제목, 게시글, 단어 검색',
              hintStyle: const TextStyle(color: Colors.white38),
              prefixIcon:
                  const Icon(Icons.search_rounded, color: Colors.white54),
              filled: true,
              fillColor: AppColors.card,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(18),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: List.generate(_tabs.length, (index) {
                final selected = _selectedTab == index;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    selected: selected,
                    label: Text(_tabs[index]),
                    selectedColor: AppColors.p600,
                    backgroundColor: AppColors.card,
                    labelStyle: TextStyle(
                      color: selected ? Colors.white : Colors.white70,
                      fontWeight: FontWeight.w800,
                    ),
                    side: BorderSide(
                      color: selected ? AppColors.p400 : Colors.white10,
                    ),
                    onSelected: (_) => setState(() => _selectedTab = index),
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.cloud_off_rounded, color: AppColors.pink2, size: 48),
          const SizedBox(height: 12),
          Text(
            _error ?? '알 수 없는 오류',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white, fontSize: 15),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _loadDashboard,
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('다시 불러오기'),
          ),
        ],
      ),
    );
  }

  Widget _buildTabBody(AdminDashboard dashboard) {
    return switch (_selectedTab) {
      0 => _buildOverview(dashboard),
      1 => _buildUsers(dashboard.users),
      2 => _buildStories(dashboard.stories),
      3 => _buildPosts(dashboard.communityPosts),
      _ => _buildVocabularies(dashboard.vocabularies),
    };
  }

  Widget _buildOverview(AdminDashboard dashboard) {
    final stats = dashboard.stats;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth > 640;
            return GridView.count(
              crossAxisCount: wide ? 4 : 2,
              childAspectRatio: wide ? 1.55 : 1.25,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              children: [
                _buildStatCard('회원', stats.userCount, Icons.people_rounded),
                _buildStatCard(
                    '동화', stats.storyCount, Icons.auto_stories_rounded),
                _buildStatCard(
                    '게시글', stats.communityPostCount, Icons.forum_rounded),
                _buildStatCard(
                    '단어', stats.vocabularyCount, Icons.menu_book_rounded),
              ],
            );
          },
        ),
        const SizedBox(height: 14),
        _buildAdminPanel(
          title: '운영 요약',
          subtitle:
              '일반 ${stats.localUserCount}명 · 소셜 ${stats.socialUserCount}명 · 댓글 ${stats.commentCount}개',
          child: Column(
            children: [
              _buildProgressRow(
                '공유된 동화',
                stats.storyCount == 0
                    ? 0
                    : stats.sharedStoryCount / stats.storyCount,
                '${stats.sharedStoryCount}/${stats.storyCount}',
                AppColors.teal,
              ),
              _buildProgressRow(
                '숨김 게시글',
                stats.communityPostCount == 0
                    ? 0
                    : stats.hiddenPostCount / stats.communityPostCount,
                '${stats.hiddenPostCount}/${stats.communityPostCount}',
                AppColors.pink,
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        _buildAdminPanel(
          title: '빠른 점검',
          subtitle: '관리자가 자주 확인할 항목입니다.',
          child: Column(
            children: [
              _buildChecklistTile('신규 회원 확인', '최근 가입자 정보와 로그인 방식을 확인하세요.'),
              _buildChecklistTile(
                  '게시판 관리', '댓글 수, 숨김 여부, 신고 수를 확인하고 게시글을 정리하세요.'),
              _buildChecklistTile(
                  '학습 데이터 확인', '단어장이 과도하게 쌓이거나 잘못 저장된 단어가 없는지 확인하세요.'),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStatCard(String label, int value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Icon(icon, color: AppColors.p300),
          Text(
            value.toString(),
            style: const TextStyle(
              color: Colors.white,
              fontSize: 28,
              fontWeight: FontWeight.w900,
            ),
          ),
          Text(label, style: const TextStyle(color: Colors.white60)),
        ],
      ),
    );
  }

  Widget _buildProgressRow(
      String label, double value, String trailing, Color color) {
    final clamped = value.clamp(0, 1).toDouble();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(label, style: const TextStyle(color: Colors.white)),
              ),
              Text(trailing, style: const TextStyle(color: Colors.white54)),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: clamped,
              minHeight: 10,
              color: color,
              backgroundColor: Colors.white10,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChecklistTile(String title, String subtitle) {
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.check_circle_rounded, color: AppColors.teal),
      title: Text(
        title,
        style:
            const TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
      ),
      subtitle: Text(subtitle, style: const TextStyle(color: Colors.white54)),
    );
  }

  Widget _buildUsers(List<AdminUser> users) {
    final filtered = users.where((user) {
      final haystack = [
        user.accountId,
        user.nickname,
        user.email,
        user.phone,
        user.address,
        user.provider,
      ].whereType<String>().join(' ').toLowerCase();
      return haystack.contains(_query.toLowerCase());
    }).toList();

    return _buildAdminPanel(
      title: '회원 관리',
      subtitle: '총 ${filtered.length}명 표시 중',
      child: _buildListOrEmpty(
        filtered,
        (user) => _buildUserCard(user),
      ),
    );
  }

  Widget _buildUserCard(AdminUser user) {
    final isAdmin = user.accountId == widget.adminAccountId;
    return _buildItemCard(
      leading: Icons.person_rounded,
      title: '${user.nickname} (${user.accountId})',
      subtitle:
          '${user.provider} · 동화 ${user.storyCount}개 · 단어 ${user.vocabCount}개',
      badges: [
        user.email ?? '이메일 없음',
        '가입 ${_formatDate(user.createdAt)}',
        '최근 ${_formatDate(user.lastLogin)}',
      ],
      actions: [
        IconButton(
          tooltip: '회원 상세',
          onPressed: () => _showUserDetail(user),
          icon: const Icon(Icons.info_outline_rounded),
        ),
        IconButton(
          tooltip: isAdmin ? '관리자 계정은 삭제할 수 없음' : '회원 삭제',
          onPressed: isAdmin
              ? null
              : () => _runAdminAction(
                    title: '회원 삭제',
                    message: '${user.nickname} 회원과 연결된 동화/단어장/게시글을 삭제할까요?',
                    action: () => DbService.deleteAdminUser(
                      adminAccountId: widget.adminAccountId,
                      userId: user.id,
                    ),
                  ),
          icon: const Icon(Icons.delete_outline_rounded),
        ),
      ],
    );
  }

  Widget _buildStories(List<AdminStory> stories) {
    final filtered = stories.where((story) {
      final haystack = [
        story.title,
        story.genre,
        story.authorNickname,
        story.targetAge,
      ].join(' ').toLowerCase();
      return haystack.contains(_query.toLowerCase());
    }).toList();

    return _buildAdminPanel(
      title: '동화 관리',
      subtitle: '생성된 동화 ${filtered.length}개',
      child: _buildListOrEmpty(
        filtered,
        (story) => _buildStoryCard(story),
      ),
    );
  }

  Widget _buildStoryCard(AdminStory story) {
    return _buildItemCard(
      leading: Icons.auto_stories_rounded,
      title: story.title,
      subtitle:
          '${story.authorNickname} · ${story.genre} · ${story.sceneCount}장면',
      badges: [
        story.isShared ? '공유됨' : '비공개',
        '좋아요 ${story.likes}',
        '수정 ${_formatDate(story.updatedAt ?? story.createdAt)}',
      ],
      actions: [
        IconButton(
          tooltip: '동화 삭제',
          onPressed: () => _runAdminAction(
            title: '동화 삭제',
            message: '"${story.title}" 동화와 연결 단어를 삭제할까요?',
            action: () => DbService.deleteAdminStory(
              adminAccountId: widget.adminAccountId,
              storyId: story.id,
            ),
          ),
          icon: const Icon(Icons.delete_outline_rounded),
        ),
      ],
    );
  }

  Widget _buildPosts(List<AdminCommunityPost> posts) {
    final filtered = posts.where((post) {
      final haystack = [
        post.title,
        post.authorName,
        post.authorAccountId,
        post.genre,
        post.preview,
      ].whereType<String>().join(' ').toLowerCase();
      return haystack.contains(_query.toLowerCase());
    }).toList();

    return _buildAdminPanel(
      title: '게시판 관리',
      subtitle: '게시글 ${filtered.length}개',
      child: _buildListOrEmpty(
        filtered,
        (post) => _buildPostCard(post),
      ),
    );
  }

  Widget _buildPostCard(AdminCommunityPost post) {
    return _buildItemCard(
      leading: Icons.forum_rounded,
      title: post.title,
      subtitle:
          '${post.authorName} · 조회 ${post.viewCount} · 좋아요 ${post.likeCount} · 댓글 ${post.commentCount}',
      badges: [
        post.isHidden ? '숨김' : '노출',
        post.moderationStatus,
        '작성 ${_formatDate(post.createdAt)}',
      ],
      actions: [
        IconButton(
          tooltip: post.isHidden ? '게시글 노출' : '게시글 숨김',
          onPressed: () => _runAdminAction(
            title: post.isHidden ? '게시글 노출' : '게시글 숨김',
            message: '"${post.title}" 상태를 변경할까요?',
            action: () async {
              await DbService.updateAdminPostVisibility(
                adminAccountId: widget.adminAccountId,
                postId: post.id,
                isHidden: !post.isHidden,
              );
            },
          ),
          icon: Icon(
            post.isHidden
                ? Icons.visibility_rounded
                : Icons.visibility_off_rounded,
          ),
        ),
        IconButton(
          tooltip: '게시글 삭제',
          onPressed: () => _runAdminAction(
            title: '게시글 삭제',
            message: '"${post.title}" 게시글을 삭제할까요?',
            action: () => DbService.deleteAdminCommunityPost(
              adminAccountId: widget.adminAccountId,
              postId: post.id,
            ),
          ),
          icon: const Icon(Icons.delete_outline_rounded),
        ),
      ],
    );
  }

  Widget _buildVocabularies(List<VocabWord> words) {
    final filtered = words.where((word) {
      final haystack = [
        word.hard,
        word.easy,
        word.definition,
        word.sourceStoryTitle,
      ].whereType<String>().join(' ').toLowerCase();
      return haystack.contains(_query.toLowerCase());
    }).toList();

    return _buildAdminPanel(
      title: '단어장 관리',
      subtitle: '저장된 단어 ${filtered.length}개',
      child: _buildListOrEmpty(
        filtered,
        (word) => _buildVocabCard(word),
      ),
    );
  }

  Widget _buildVocabCard(VocabWord word) {
    return _buildItemCard(
      leading: Icons.menu_book_rounded,
      title: word.hard,
      subtitle: word.easy,
      badges: [
        word.sourceStoryTitle ?? '출처 없음',
        '저장 ${_formatDate(word.createdAt)}',
      ],
      actions: [
        IconButton(
          tooltip: '단어 삭제',
          onPressed: word.id == null
              ? null
              : () => _runAdminAction(
                    title: '단어 삭제',
                    message: '"${word.hard}" 단어를 삭제할까요?',
                    action: () => DbService.deleteAdminVocabulary(
                      adminAccountId: widget.adminAccountId,
                      vocabId: word.id!,
                    ),
                  ),
          icon: const Icon(Icons.delete_outline_rounded),
        ),
      ],
    );
  }

  Widget _buildAdminPanel({
    required String title,
    required String subtitle,
    required Widget child,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 4),
          Text(subtitle, style: const TextStyle(color: Colors.white54)),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }

  Widget _buildListOrEmpty<T>(List<T> items, Widget Function(T item) builder) {
    if (items.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 36),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(18),
        ),
        child: const Text(
          '표시할 데이터가 없습니다.',
          textAlign: TextAlign.center,
          style: TextStyle(color: Colors.white54),
        ),
      );
    }

    return Column(
      children: items
          .map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: builder(item),
            ),
          )
          .toList(),
    );
  }

  Widget _buildItemCard({
    required IconData leading,
    required String title,
    required String subtitle,
    required List<String> badges,
    required List<Widget> actions,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.045),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.p600.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(leading, color: AppColors.p300),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w900,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.white60, fontSize: 12),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: badges
                      .where((badge) => badge.trim().isNotEmpty)
                      .map(_buildBadge)
                      .toList(),
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Wrap(spacing: 2, children: actions),
        ],
      ),
    );
  }

  Widget _buildBadge(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white70,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _buildUserMetricCard(String label, int value, IconData icon) {
    return Container(
      width: 96,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.055),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.p300, size: 20),
          const SizedBox(height: 10),
          Text(
            value.toString(),
            style: const TextStyle(
              color: Colors.white,
              fontSize: 22,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 2),
          Text(label,
              style: const TextStyle(color: Colors.white54, fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildUserDataSection({
    required String title,
    required String emptyText,
    required List<Widget> children,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 15,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 10),
          if (children.isEmpty)
            Text(emptyText, style: const TextStyle(color: Colors.white54))
          else
            ...children,
        ],
      ),
    );
  }

  Widget _buildCompactDataRow({
    required IconData icon,
    required String title,
    required String subtitle,
    List<String> badges = const [],
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: AppColors.p600.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: AppColors.p300, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.white54, fontSize: 11),
                ),
                if (badges.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 5,
                    runSpacing: 5,
                    children: badges
                        .where((badge) => badge.trim().isNotEmpty)
                        .map(_buildBadge)
                        .toList(),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showUserDetail(AdminUser user) {
    final dashboard = _dashboard;
    final userStories =
        dashboard?.stories.where((story) => story.userId == user.id).toList() ??
            <AdminStory>[];
    final accountId = user.accountId.trim();
    final userPosts = dashboard?.communityPosts.where((post) {
          if (accountId.isNotEmpty && post.authorAccountId == accountId) {
            return true;
          }
          return post.authorName == user.nickname;
        }).toList() ??
        <AdminCommunityPost>[];
    final userWords = dashboard?.vocabularies
            .where((word) => word.userId == user.id)
            .toList() ??
        <VocabWord>[];

    showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.card,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (context) => SafeArea(
        child: FractionallySizedBox(
          heightFactor: 0.92,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        user.nickname,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _buildUserMetricCard(
                      '동화',
                      userStories.length,
                      Icons.auto_stories_rounded,
                    ),
                    _buildUserMetricCard(
                      '게시글',
                      userPosts.length,
                      Icons.forum_rounded,
                    ),
                    _buildUserMetricCard(
                      '단어',
                      userWords.length,
                      Icons.menu_book_rounded,
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                _buildDetailRow('계정', user.accountId),
                _buildDetailRow('이메일', user.email ?? '없음'),
                _buildDetailRow('전화번호', user.phone ?? '없음'),
                _buildDetailRow('주소', user.address ?? '없음'),
                _buildDetailRow('로그인 방식', user.provider),
                _buildDetailRow('성향', user.personalityType),
                _buildDetailRow('가입일', _formatDate(user.createdAt)),
                _buildDetailRow('최근 로그인', _formatDate(user.lastLogin)),
                const SizedBox(height: 18),
                _buildUserDataSection(
                  title: '회원별 동화',
                  emptyText: '이 회원이 만든 동화가 없습니다.',
                  children: userStories
                      .map(
                        (story) => _buildCompactDataRow(
                          icon: Icons.auto_stories_rounded,
                          title: story.title,
                          subtitle:
                              '${story.genre} · ${story.sceneCount}장면 · ${story.authorNickname}',
                          badges: [
                            story.isShared ? '공유됨' : '비공개',
                            '좋아요 ${story.likes}',
                            _formatDate(story.updatedAt ?? story.createdAt),
                          ],
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 12),
                _buildUserDataSection(
                  title: '회원별 게시판',
                  emptyText: '이 회원이 작성한 게시글이 없습니다.',
                  children: userPosts
                      .map(
                        (post) => _buildCompactDataRow(
                          icon: Icons.forum_rounded,
                          title: post.title,
                          subtitle:
                              '${post.genre} · 조회 ${post.viewCount} · 댓글 ${post.commentCount}',
                          badges: [
                            post.isHidden ? '숨김' : '노출',
                            post.moderationStatus,
                            _formatDate(post.createdAt),
                          ],
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 12),
                _buildUserDataSection(
                  title: '회원별 단어장',
                  emptyText: '이 회원이 저장한 단어가 없습니다.',
                  children: userWords
                      .map(
                        (word) => _buildCompactDataRow(
                          icon: Icons.menu_book_rounded,
                          title: word.hard,
                          subtitle: word.definition.isNotEmpty
                              ? word.definition
                              : word.easy,
                          badges: [
                            word.sourceStoryTitle ?? '출처 없음',
                            _formatDate(word.createdAt),
                          ],
                        ),
                      )
                      .toList(),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 88,
            child: Text(label, style: const TextStyle(color: Colors.white54)),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime? value) {
    if (value == null) return '없음';
    final local = value.toLocal();
    String two(int number) => number.toString().padLeft(2, '0');
    return '${local.year}.${two(local.month)}.${two(local.day)}';
  }
}
