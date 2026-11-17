import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_theme.dart';
import 'community_report_sheet.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/db_service.dart';
import 'social_pages.dart';

enum _PostDeleteChoice { cancel, postOnly, postAndStory }

Future<_PostDeleteChoice?> _confirmPostDeletion(
  BuildContext context,
  CommunityPost post,
) {
  final hasSavedStory = post.storyId?.trim().isNotEmpty == true;
  return showDialog<_PostDeleteChoice>(
    context: context,
    builder: (context) => AlertDialog(
      backgroundColor: AppColors.pageSurface,
      title: Text(
        hasSavedStory ? '저장된 동화도 지울까요?' : '게시글을 삭제할까요?',
        style: const TextStyle(color: Colors.white),
      ),
      content: Text(
        hasSavedStory
            ? '"${post.title}" 게시글을 지워요. 내 동화에 저장된 원본도 함께 지울 수 있어요.'
            : '"${post.title}" 게시글이 커뮤니티에서 삭제돼요.',
        style: const TextStyle(color: AppColors.gray),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, _PostDeleteChoice.cancel),
          child: const Text('취소'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(context, _PostDeleteChoice.postOnly),
          child: const Text(
            '게시글만 지우기',
            style: TextStyle(color: AppColors.pink2),
          ),
        ),
        if (hasSavedStory)
          FilledButton(
            onPressed: () =>
                Navigator.pop(context, _PostDeleteChoice.postAndStory),
            style: FilledButton.styleFrom(backgroundColor: AppColors.pink2),
            child: const Text('동화도 함께 지우기'),
          ),
      ],
    ),
  );
}

class CommunityPage extends StatefulWidget {
  final int initialTab;

  const CommunityPage({super.key, this.initialTab = 0});

  @override
  State<CommunityPage> createState() => _CommunityPageState();
}

class _CommunityPageState extends State<CommunityPage> {
  static const _genres = [
    '전체',
    '판타지',
    '모험',
    'SF',
    '일상',
    '전래동화',
    '우정',
    '자연',
    '동물',
    '미스터리',
  ];

  final TextEditingController _searchController = TextEditingController();
  int _selectedTab = 0;
  String _selectedGenre = '전체';
  bool _isLoading = true;
  String? _error;
  String _query = '';
  int _visibleLimit = 10;
  List<CommunityPost> _posts = [];
  final Set<String> _likingPostIds = {};
  final Set<String> _scrappingPostIds = {};

  @override
  void initState() {
    super.initState();
    _selectedTab = widget.initialTab.clamp(0, 2).toInt();
    _loadPosts();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadPosts() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final sort = _selectedTab == 1 ? 'popular' : 'latest';
      final posts = await DbService.fetchCommunityPosts(sort: sort);
      if (!mounted) return;
      setState(() {
        _posts = posts;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString().replaceAll('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  void _selectTab(int index) {
    if (_selectedTab == index) return;
    setState(() {
      _selectedTab = index;
      _visibleLimit = 10;
    });
    _loadPosts();
  }

  List<CommunityPost> _visiblePosts(String? accountId) {
    final query = _query.trim();
    return _posts.where((post) {
      final matchesMine =
          _selectedTab != 2 ||
          (accountId != null &&
              accountId.isNotEmpty &&
              post.authorAccountId == accountId);
      final matchesQuery =
          query.isEmpty ||
          post.title.contains(query) ||
          post.preview.contains(query) ||
          post.fullText.contains(query) ||
          post.genre.contains(query) ||
          post.authorName.contains(query);
      final matchesGenre =
          _selectedGenre == '전체' || post.genre == _selectedGenre;
      return matchesMine && matchesQuery && matchesGenre;
    }).toList();
  }

  String _relativeTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return '방금 전';
    if (diff.inHours < 1) return '${diff.inMinutes}분 전';
    if (diff.inDays < 1) return '${diff.inHours}시간 전';
    if (diff.inDays < 7) return '${diff.inDays}일 전';
    return '${time.month}월 ${time.day}일';
  }

  String _storyEmoji(String genre) {
    return const {
          '판타지': '🏰',
          '모험': '🗺️',
          '우정': '🤝',
          '자연': '🌿',
          '동물': '🐾',
          '미스터리': '🔍',
        }[genre] ??
        '📖';
  }

  Future<void> _openShareSheet() async {
    final state = context.read<AppState>();
    final stories = state.completedStories;
    if (stories.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('서재에 저장된 동화가 없어요. 동화를 완성한 뒤 공유해보세요!')),
      );
      return;
    }

    final selected = await showModalBottomSheet<StorySession>(
      context: context,
      backgroundColor: AppColors.pageSurface,
      isScrollControlled: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '✏️ 어떤 동화를 공유할까요?',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '내 서재에 있는 완성 동화 중 하나를 골라 게시판에 올릴 수 있어요.',
                  style: TextStyle(
                    color: AppColors.gray,
                    fontSize: 12,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 16),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 360),
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: stories.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final story = stories[index];
                      return InkWell(
                        borderRadius: BorderRadius.circular(16),
                        onTap: () => Navigator.pop(context, story),
                        child: Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: AppColors.pageInput,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: AppColors.border),
                          ),
                          child: Row(
                            children: [
                              Text(
                                _storyEmoji(story.genre),
                                style: const TextStyle(fontSize: 28),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      story.initialPrompt,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      '${story.genre} · ${story.chapters.length}챕터',
                                      style: const TextStyle(
                                        color: AppColors.gray,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const Icon(
                                Icons.arrow_forward_ios_rounded,
                                color: AppColors.gray2,
                                size: 14,
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );

    if (selected == null) return;

    try {
      final post = await DbService.createCommunityPost(
        authorName: state.currentDisplayName,
        authorAccountId: state.currentAccountId,
        storyId: selected.dbStoryId,
        genre: selected.genre,
        title: selected.initialPrompt,
        preview: selected.fullStoryText.length > 120
            ? '${selected.fullStoryText.substring(0, 120)}...'
            : selected.fullStoryText,
        fullText: selected.fullStoryText,
        storyEmoji: _storyEmoji(selected.genre),
      );

      if (!mounted) return;
      setState(() {
        _posts = [post, ..._posts];
        _selectedTab = 0;
      });
      unawaited(state.loadUserData());
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('게시판에 동화를 공유했어요!')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('공유 실패: ${e.toString().replaceAll('Exception: ', '')}'),
        ),
      );
    }
  }

  Future<void> _openDetail(CommunityPost post) async {
    final updated = await Navigator.push<CommunityPost>(
      context,
      MaterialPageRoute(
        builder: (_) => CommunityPostDetailPage(initialPost: post),
      ),
    );
    if (!mounted) return;
    if (updated == null) {
      unawaited(_loadPosts());
      return;
    }
    setState(() {
      final index = _posts.indexWhere((item) => item.id == updated.id);
      if (index >= 0) {
        _posts[index] = updated;
      }
    });
  }

  Future<void> _likePost(CommunityPost post) async {
    if (_likingPostIds.contains(post.id)) return;
    final accountId = context.read<AppState>().currentAccountId;
    setState(() => _likingPostIds.add(post.id));
    try {
      final updated = await DbService.likeCommunityPost(
        postId: post.id,
        accountId: accountId,
      );
      if (!mounted) return;
      setState(() {
        final index = _posts.indexWhere((item) => item.id == updated.id);
        if (index >= 0) {
          _posts[index] = updated;
        }
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '좋아요 저장 실패: ${e.toString().replaceAll('Exception: ', '')}',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _likingPostIds.remove(post.id));
      }
    }
  }

  Future<void> _toggleScrap(CommunityPost post) async {
    if (_scrappingPostIds.contains(post.id)) return;
    setState(() => _scrappingPostIds.add(post.id));
    try {
      final result = await DbService.toggleCommunityScrap(post.id);
      if (!mounted) return;
      final index = _posts.indexWhere((item) => item.id == post.id);
      if (index >= 0) {
        setState(
          () => _posts[index] = _posts[index].copyWith(
            isScrapped: result['is_scrapped'] == true,
          ),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', '')),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _scrappingPostIds.remove(post.id));
    }
  }

  Future<void> _deletePost(CommunityPost post) async {
    final state = context.read<AppState>();
    if (post.authorAccountId != state.currentAccountId) return;

    final choice = await _confirmPostDeletion(context, post);
    if (choice == null || choice == _PostDeleteChoice.cancel) return;

    try {
      await DbService.deleteCommunityPost(
        postId: post.id,
        accountId: state.currentAccountId,
        deleteStory: choice == _PostDeleteChoice.postAndStory,
      );
      if (!mounted) return;
      setState(() => _posts.removeWhere((item) => item.id == post.id));
      await state.loadUserData();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            choice == _PostDeleteChoice.postAndStory
                ? '게시글과 저장된 동화를 삭제했어요.'
                : '게시글을 삭제했어요.',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '게시글 삭제 실패: ${e.toString().replaceAll('Exception: ', '')}',
          ),
        ),
      );
    }
  }

  Widget _buildTab(int index, String title) {
    final isActive = _selectedTab == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => _selectTab(index),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          decoration: BoxDecoration(
            color: isActive
                ? Colors.white.withValues(alpha: 0.08)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(14),
          ),
          alignment: Alignment.center,
          child: Text(
            title,
            style: TextStyle(
              color: isActive ? Colors.white : Colors.white70,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ),
    );
  }

  Widget _searchBox() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 4),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        decoration: BoxDecoration(
          color: AppColors.pageSurface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: Colors.white10),
        ),
        child: TextField(
          controller: _searchController,
          onChanged: (value) => setState(() {
            _query = value;
            _visibleLimit = 10;
          }),
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            icon: Icon(Icons.search, color: Colors.white54, size: 20),
            hintText: '제목, 내용, 장르 검색...',
            hintStyle: TextStyle(color: Colors.white38),
            border: InputBorder.none,
          ),
        ),
      ),
    );
  }

  Widget _genreFilters() {
    return SizedBox(
      height: 46,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        itemCount: _genres.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final genre = _genres[index];
          final selected = genre == _selectedGenre;
          return ChoiceChip(
            label: Text(genre),
            selected: selected,
            onSelected: (_) => setState(() {
              _selectedGenre = genre;
              _visibleLimit = 10;
            }),
            selectedColor: AppColors.p600,
            backgroundColor: AppColors.pageSurface,
            side: const BorderSide(color: AppColors.border),
            labelStyle: TextStyle(
              color: selected ? Colors.white : Colors.white70,
              fontWeight: FontWeight.w700,
            ),
          );
        },
      ),
    );
  }

  Widget _buildFeedCard(CommunityPost post, String? accountId) {
    final isLiked = post.isLikedBy(accountId);
    final isLiking = _likingPostIds.contains(post.id);
    final isScrapping = _scrappingPostIds.contains(post.id);
    final isMine =
        accountId != null &&
        accountId.isNotEmpty &&
        post.authorAccountId == accountId;

    final imageUrl = DbService.resolveMediaUrl(post.authorProfileImageUrl);
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: AppColors.border),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(24),
        onTap: () => _openDetail(post),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  InkWell(
                    customBorder: const CircleBorder(),
                    onTap: () =>
                        showPublicProfile(context, post.authorAccountId),
                    child: CircleAvatar(
                      radius: 19,
                      backgroundColor: AppColors.p600.withValues(alpha: 0.38),
                      backgroundImage: imageUrl == null
                          ? null
                          : NetworkImage(
                              imageUrl,
                              headers: DbService.mediaHeaders,
                            ),
                      child: imageUrl == null
                          ? Text(
                              post.authorName.trim().isEmpty
                                  ? '?'
                                  : post.authorName.trim()[0],
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w800,
                              ),
                            )
                          : null,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: InkWell(
                      onTap: () =>
                          showPublicProfile(context, post.authorAccountId),
                      child: Text(
                        post.authorName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white70,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                  Text(
                    _relativeTime(post.createdAt),
                    style: const TextStyle(color: Colors.white38, fontSize: 12),
                  ),
                  if (isMine)
                    IconButton(
                      tooltip: '게시글 삭제',
                      visualDensity: VisualDensity.compact,
                      onPressed: () => _deletePost(post),
                      icon: const Icon(
                        Icons.delete_outline_rounded,
                        color: Colors.white38,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 15),
              Text(
                post.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                post.preview,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: Colors.white60, height: 1.5),
              ),
              const SizedBox(height: 15),
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.p600.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '#${post.genre}',
                      style: const TextStyle(
                        color: AppColors.p300,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const Spacer(),
                  InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: isLiking ? null : () => _likePost(post),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 5,
                        vertical: 6,
                      ),
                      child: Row(
                        children: [
                          Icon(
                            isLiked
                                ? Icons.favorite_rounded
                                : Icons.favorite_border_rounded,
                            color: isLiked ? AppColors.pink2 : Colors.white60,
                            size: 17,
                          ),
                          const SizedBox(width: 5),
                          Text(
                            '${post.likeCount}',
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Icon(
                    Icons.chat_bubble_rounded,
                    color: Colors.lightBlueAccent,
                    size: 16,
                  ),
                  const SizedBox(width: 5),
                  Text(
                    '${post.commentCount}',
                    style: const TextStyle(color: Colors.white70, fontSize: 12),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    tooltip: post.isScrapped ? '스크랩 취소' : '스크랩',
                    onPressed: isScrapping ? null : () => _toggleScrap(post),
                    icon: Icon(
                      post.isScrapped
                          ? Icons.bookmark_rounded
                          : Icons.bookmark_border_rounded,
                      color: post.isScrapped ? AppColors.p400 : Colors.white54,
                      size: 20,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final accountId = context.select<AppState, String?>(
      (state) => state.currentAccountId,
    );
    final visiblePosts = _visiblePosts(accountId);
    final shownCount = visiblePosts.length < _visibleLimit
        ? visiblePosts.length
        : _visibleLimit;
    final hasMore = shownCount < visiblePosts.length;
    final hasFilter =
        _query.trim().isNotEmpty || _selectedTab == 2 || _selectedGenre != '전체';

    return Scaffold(
      backgroundColor: AppColors.pageBackground,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 10, 24, 0),
              child: Row(
                children: [
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '✨ 커뮤니티',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 34,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        SizedBox(height: 10),
                        Text(
                          '다른 친구들의 이야기를 만나보세요',
                          style: TextStyle(color: Colors.white70, fontSize: 16),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: _openShareSheet,
                    style: IconButton.styleFrom(
                      backgroundColor: AppColors.pageSurface,
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white10),
                    ),
                    icon: const Icon(Icons.edit),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
              child: Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: AppColors.pageSurface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Colors.white10),
                ),
                child: Row(
                  children: [
                    _buildTab(0, '최신'),
                    _buildTab(1, '인기'),
                    _buildTab(2, '내 글'),
                  ],
                ),
              ),
            ),
            _searchBox(),
            const SizedBox(height: 12),
            _genreFilters(),
            const SizedBox(height: 8),
            Expanded(
              child: RefreshIndicator(
                onRefresh: _loadPosts,
                child: _isLoading
                    ? const Center(
                        child: CircularProgressIndicator(
                          color: Color(0xFF7C3AED),
                        ),
                      )
                    : _error != null
                    ? ListView(
                        padding: const EdgeInsets.all(32),
                        children: [
                          const SizedBox(height: 120),
                          const Text(
                            '게시판을 불러오지 못했어요',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _error!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.grey),
                          ),
                        ],
                      )
                    : visiblePosts.isEmpty
                    ? ListView(
                        padding: const EdgeInsets.all(32),
                        children: [
                          const SizedBox(height: 120),
                          Text(
                            hasFilter
                                ? '조건에 맞는 게시글이 없어요.\n검색어를 바꾸거나 최신 탭을 확인해보세요.'
                                : '아직 공유된 동화가 없어요.\n첫 번째 이야기를 올려보세요!',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: Colors.grey,
                              height: 1.6,
                            ),
                          ),
                        ],
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(24, 20, 24, 100),
                        itemCount: shownCount + 1 + (hasMore ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index == 0) {
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 12),
                              child: Text(
                                '이야기 ${visiblePosts.length}개',
                                style: const TextStyle(
                                  color: Colors.white54,
                                  fontSize: 13,
                                ),
                              ),
                            );
                          }
                          if (index <= shownCount) {
                            return _buildFeedCard(
                              visiblePosts[index - 1],
                              accountId,
                            );
                          }
                          return Padding(
                            padding: const EdgeInsets.only(top: 2, bottom: 18),
                            child: OutlinedButton(
                              onPressed: () =>
                                  setState(() => _visibleLimit += 10),
                              style: OutlinedButton.styleFrom(
                                foregroundColor: AppColors.p300,
                                side: const BorderSide(color: AppColors.p400),
                                padding: const EdgeInsets.symmetric(
                                  vertical: 14,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(16),
                                ),
                              ),
                              child: const Text(
                                '더보기',
                                style: TextStyle(fontWeight: FontWeight.bold),
                              ),
                            ),
                          );
                        },
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class CommunityPostDetailPage extends StatefulWidget {
  final CommunityPost initialPost;

  const CommunityPostDetailPage({super.key, required this.initialPost});

  @override
  State<CommunityPostDetailPage> createState() =>
      _CommunityPostDetailPageState();
}

class _CommunityPostDetailPageState extends State<CommunityPostDetailPage> {
  final TextEditingController _commentController = TextEditingController();
  CommunityPost? _post;
  bool _isLoading = true;
  bool _isSubmitting = false;
  bool _isLiking = false;
  bool _isScrapping = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDetail();
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _loadDetail() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final post = await DbService.fetchCommunityPostDetail(
        widget.initialPost.id,
      );
      if (!mounted) return;
      setState(() => _post = post);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString().replaceAll('Exception: ', '');
        _post = widget.initialPost;
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  String _relativeTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return '방금 전';
    if (diff.inHours < 1) return '${diff.inMinutes}분 전';
    if (diff.inDays < 1) return '${diff.inHours}시간 전';
    if (diff.inDays < 7) return '${diff.inDays}일 전';
    return '${time.month}월 ${time.day}일';
  }

  Future<void> _submitComment() async {
    final content = _commentController.text.trim();
    if (content.isEmpty || _post == null) return;

    final state = context.read<AppState>();
    setState(() => _isSubmitting = true);
    try {
      final updated = await DbService.addCommunityComment(
        postId: _post!.id,
        authorName: state.currentDisplayName,
        authorAccountId: state.currentAccountId,
        content: content,
      );
      if (!mounted) return;
      _commentController.clear();
      setState(() => _post = updated);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('댓글을 남겼어요!')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '댓글 저장 실패: ${e.toString().replaceAll('Exception: ', '')}',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  Future<void> _likePost() async {
    if (_post == null || _isLiking) return;
    final state = context.read<AppState>();
    setState(() => _isLiking = true);
    try {
      final updated = await DbService.likeCommunityPost(
        postId: _post!.id,
        accountId: state.currentAccountId,
      );
      if (!mounted) return;
      setState(() => _post = updated);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '좋아요 저장 실패: ${e.toString().replaceAll('Exception: ', '')}',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _isLiking = false);
      }
    }
  }

  Future<void> _toggleScrap() async {
    if (_post == null || _isScrapping) return;
    setState(() => _isScrapping = true);
    try {
      final result = await DbService.toggleCommunityScrap(_post!.id);
      if (mounted) {
        setState(
          () => _post = _post!.copyWith(
            isScrapped: result['is_scrapped'] == true,
          ),
        );
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.toString().replaceFirst('Exception: ', '')),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isScrapping = false);
    }
  }

  Future<void> _deletePost() async {
    final post = _post ?? widget.initialPost;
    final state = context.read<AppState>();
    if (post.authorAccountId != state.currentAccountId) return;

    final choice = await _confirmPostDeletion(context, post);
    if (choice == null || choice == _PostDeleteChoice.cancel) return;

    try {
      await DbService.deleteCommunityPost(
        postId: post.id,
        accountId: state.currentAccountId,
        deleteStory: choice == _PostDeleteChoice.postAndStory,
      );
      if (!mounted) return;
      await state.loadUserData();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            choice == _PostDeleteChoice.postAndStory
                ? '게시글과 저장된 동화를 삭제했어요.'
                : '게시글을 삭제했어요.',
          ),
        ),
      );
      Navigator.pop(context);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '게시글 삭제 실패: ${e.toString().replaceAll('Exception: ', '')}',
          ),
        ),
      );
    }
  }

  Future<void> _deleteComment(CommunityComment comment) async {
    final post = _post ?? widget.initialPost;
    final state = context.read<AppState>();
    final accountId = state.currentAccountId;
    final canDelete =
        accountId != null &&
        accountId.isNotEmpty &&
        (comment.authorAccountId == accountId ||
            post.authorAccountId == accountId);
    if (!canDelete) return;

    try {
      final updated = await DbService.deleteCommunityComment(
        postId: post.id,
        commentId: comment.id,
        accountId: accountId,
      );
      if (!mounted) return;
      setState(() => _post = updated);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('댓글을 삭제했어요.')));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '댓글 삭제 실패: ${e.toString().replaceAll('Exception: ', '')}',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final post = _post ?? widget.initialPost;
    final accountId = context.select<AppState, String?>(
      (state) => state.currentAccountId,
    );
    final isLiked = post.isLikedBy(accountId);
    final isMine =
        accountId != null &&
        accountId.isNotEmpty &&
        post.authorAccountId == accountId;
    return Scaffold(
      backgroundColor: AppColors.pageBackground,
      appBar: AppBar(
        backgroundColor: AppColors.pageBackground,
        title: const Text('동화 게시글'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context, post),
        ),
        actions: [
          if (!isMine)
            IconButton(
              tooltip: '게시글 신고',
              icon: const Icon(Icons.flag_outlined),
              onPressed: () => showCommunityReportSheet(
                context,
                targetType: 'post',
                targetId: post.id,
                accountId: accountId,
              ),
            ),
          if (isMine)
            IconButton(
              onPressed: _deletePost,
              icon: const Icon(Icons.delete_outline),
              tooltip: '게시글 삭제',
            ),
        ],
      ),
      body: _isLoading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF7C3AED)),
            )
          : Column(
              children: [
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      Container(
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(
                          color: AppColors.pageSurface,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: const Color(0x338B5CF6)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                CircleAvatar(
                                  backgroundColor: const Color(0xFF7C3AED),
                                  backgroundImage:
                                      post.authorProfileImageUrl
                                              ?.trim()
                                              .isNotEmpty !=
                                          true
                                      ? null
                                      : NetworkImage(
                                          DbService.resolveMediaUrl(
                                                post.authorProfileImageUrl!,
                                              ) ??
                                              '',
                                          headers: DbService.mediaHeaders,
                                        ),
                                  child:
                                      post.authorProfileImageUrl
                                              ?.trim()
                                              .isNotEmpty !=
                                          true
                                      ? Text(post.storyEmoji)
                                      : null,
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      InkWell(
                                        onTap: () => showPublicProfile(
                                          context,
                                          post.authorAccountId,
                                        ),
                                        child: Text(
                                          post.authorName,
                                          style: const TextStyle(
                                            color: Colors.white,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                      Text(
                                        _relativeTime(post.createdAt),
                                        style: const TextStyle(
                                          color: Colors.grey,
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: const Color(0x338B5CF6),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Text(
                                    post.genre,
                                    style: const TextStyle(
                                      color: Color(0xFFA78BFA),
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            Text(
                              post.title,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            const SizedBox(height: 12),
                            Text(
                              post.fullText,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 14,
                                height: 1.7,
                              ),
                            ),
                            const SizedBox(height: 16),
                            Row(
                              children: [
                                const Icon(
                                  Icons.remove_red_eye_outlined,
                                  size: 16,
                                  color: Colors.grey,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  '조회 ${post.viewCount}',
                                  style: const TextStyle(
                                    color: Colors.grey,
                                    fontSize: 12,
                                  ),
                                ),
                                const SizedBox(width: 16),
                                const Icon(
                                  Icons.chat_bubble_outline,
                                  size: 16,
                                  color: Colors.grey,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  '댓글 ${post.commentCount}',
                                  style: const TextStyle(
                                    color: Colors.grey,
                                    fontSize: 12,
                                  ),
                                ),
                                const SizedBox(width: 16),
                                InkWell(
                                  borderRadius: BorderRadius.circular(18),
                                  onTap: _isLiking ? null : _likePost,
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 4,
                                      vertical: 4,
                                    ),
                                    child: Row(
                                      children: [
                                        Icon(
                                          isLiked
                                              ? Icons.favorite
                                              : Icons.favorite_border,
                                          size: 16,
                                          color: isLiked
                                              ? Colors.pinkAccent
                                              : Colors.grey,
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          '좋아요 ${post.likeCount}',
                                          style: const TextStyle(
                                            color: Colors.grey,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                                IconButton(
                                  tooltip: post.isScrapped ? '스크랩 취소' : '스크랩',
                                  onPressed: _isScrapping ? null : _toggleScrap,
                                  icon: Icon(
                                    post.isScrapped
                                        ? Icons.bookmark
                                        : Icons.bookmark_border,
                                    size: 19,
                                    color: post.isScrapped
                                        ? Colors.purpleAccent
                                        : Colors.grey,
                                  ),
                                ),
                              ],
                            ),
                            if (_error != null) ...[
                              const SizedBox(height: 12),
                              Text(
                                '상세 새로고침 중 문제가 있었어요: $_error',
                                style: const TextStyle(
                                  color: Colors.orangeAccent,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        '💬 댓글',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (post.comments.isEmpty)
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: AppColors.pageSurface,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: const Color(0x338B5CF6)),
                          ),
                          child: const Text(
                            '아직 댓글이 없어요. 첫 댓글을 남겨보세요!',
                            style: TextStyle(color: Colors.grey),
                          ),
                        )
                      else
                        ...post.comments.map((comment) {
                          final canDeleteComment =
                              accountId != null &&
                              accountId.isNotEmpty &&
                              (comment.authorAccountId == accountId ||
                                  post.authorAccountId == accountId);
                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: AppColors.pageSurface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: const Color(0x338B5CF6),
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    InkWell(
                                      onTap: () => showPublicProfile(
                                        context,
                                        comment.authorAccountId,
                                      ),
                                      child: Text(
                                        comment.authorName,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ),
                                    const Spacer(),
                                    Text(
                                      _relativeTime(comment.createdAt),
                                      style: const TextStyle(
                                        color: Colors.grey,
                                        fontSize: 11,
                                      ),
                                    ),
                                    if (canDeleteComment) ...[
                                      const SizedBox(width: 8),
                                      InkWell(
                                        onTap: () => _deleteComment(comment),
                                        borderRadius: BorderRadius.circular(12),
                                        child: const Padding(
                                          padding: EdgeInsets.all(4),
                                          child: Icon(
                                            Icons.delete_outline,
                                            color: Colors.white38,
                                            size: 16,
                                          ),
                                        ),
                                      ),
                                    ],
                                    if (comment.authorAccountId != accountId)
                                      IconButton(
                                        tooltip: '댓글 신고',
                                        icon: const Icon(
                                          Icons.flag_outlined,
                                          size: 17,
                                          color: Colors.white54,
                                        ),
                                        onPressed: () =>
                                            showCommunityReportSheet(
                                              context,
                                              targetType: 'comment',
                                              targetId: comment.id,
                                              postId: post.id,
                                              accountId: accountId,
                                            ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  comment.content,
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 13,
                                    height: 1.5,
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                    ],
                  ),
                ),
                SafeArea(
                  top: false,
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                    decoration: const BoxDecoration(
                      color: Color(0xFF0D0520),
                      border: Border(top: BorderSide(color: Color(0x338B5CF6))),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _commentController,
                            minLines: 1,
                            maxLines: 3,
                            style: const TextStyle(color: Colors.white),
                            decoration: InputDecoration(
                              hintText: '댓글을 남겨보세요',
                              hintStyle: const TextStyle(color: Colors.white38),
                              filled: true,
                              fillColor: AppColors.pageInput,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(18),
                                borderSide: const BorderSide(
                                  color: AppColors.border,
                                ),
                              ),
                              enabledBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(18),
                                borderSide: const BorderSide(
                                  color: AppColors.border,
                                ),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(18),
                                borderSide: const BorderSide(
                                  color: AppColors.p400,
                                  width: 1.5,
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        ElevatedButton(
                          onPressed: _isSubmitting ? null : _submitComment,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.p600,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 16,
                            ),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                          ),
                          child: _isSubmitting
                              ? const SizedBox(
                                  height: 18,
                                  width: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : const Text(
                                  '등록',
                                  style: TextStyle(color: Colors.white),
                                ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
