import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_theme.dart';
import 'community_page.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/db_service.dart';
import 'story_page.dart';
import 'widgets/story_video_player.dart';

class LibraryPage extends StatefulWidget {
  const LibraryPage({super.key});

  @override
  State<LibraryPage> createState() => _LibraryPageState();
}

class _LibraryPageState extends State<LibraryPage> {
  final TextEditingController _searchController = TextEditingController();
  String _query = '';
  String _selectedGenre = '전체';
  final Set<String> _deletingStoryIds = {};
  final Set<String> _renamingStoryIds = {};
  Timer? _journeyVideoPoller;

  static const List<String> _genres = [
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

  @override
  void initState() {
    super.initState();
    unawaited(context.read<AppState>().refreshJourneyVideoStatuses());
    _journeyVideoPoller = Timer.periodic(const Duration(seconds: 6), (_) {
      if (!mounted) return;
      final state = context.read<AppState>();
      final hasQueuedVideo = state.completedStories.any(
        (story) => const {
          'waiting_for_images',
          'pending',
          'running',
        }.contains(story.assembledVideoStatus),
      );
      if (hasQueuedVideo) unawaited(state.refreshJourneyVideoStatuses());
    });
  }

  @override
  void dispose() {
    _journeyVideoPoller?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  List<StorySession> _filteredStories(List<StorySession> stories) {
    final query = _query.trim();
    return stories.where((story) {
      final matchesGenre =
          _selectedGenre == '전체' || story.genre == _selectedGenre;
      final matchesQuery =
          query.isEmpty ||
          story.initialPrompt.contains(query) ||
          story.genre.contains(query) ||
          story.fullStoryText.contains(query);
      return matchesGenre && matchesQuery;
    }).toList();
  }

  String _storyKey(StorySession story) => story.dbStoryId ?? story.storyId;

  void _openStory(StorySession story) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => StoryPage(preloadedStory: story)),
    );
  }

  void _resumeStory(AppState state, StorySession story) {
    if (!story.hasReachedEnding && story.choices.isNotEmpty) {
      state.resumeStory(story);
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const StoryPage()),
      );
    }
  }

  Widget _statusBadge(String label, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _requestJourneyVideo(AppState state, StorySession story) async {
    final queued = await state.retryStoryJourneyVideo(story);
    if (!mounted) return;
    final status = story.assembledVideoStatus;
    final message = !queued
        ? state.errorMessage ?? '영상 작업을 요청하지 못했어요.'
        : status == 'waiting_for_images'
        ? '삽화가 준비되면 영상을 자동으로 만들게요.'
        : status == 'completed'
        ? '동화 영상이 준비되어 있어요.'
        : '동화 영상 작업을 시작했어요. 서재에서 진행 상태를 확인할 수 있어요.';
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _showJourneyVideo(StorySession story) async {
    final videoUrl = story.assembledVideoUrl;
    if (videoUrl == null || videoUrl.isEmpty) return;
    await showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: AppColors.pageSurface,
        insetPadding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: AspectRatio(
            aspectRatio: 16 / 9,
            child: StoryVideoPlayer.network(
              videoUrl: videoUrl,
              title: story.initialPrompt,
              description: '동화 삽화를 이어 만든 이야기 영상입니다.',
              httpHeaders: DbService.mediaHeaders,
              autoplay: true,
            ),
          ),
        ),
      ),
    );
  }

  Widget _journeyVideoAction(AppState state, StorySession story) {
    if (!story.hasReachedEnding) return const SizedBox.shrink();
    final status = story.assembledVideoStatus;
    final videoUrl = story.assembledVideoUrl;
    if (status == 'completed' && videoUrl != null && videoUrl.isNotEmpty) {
      return Padding(
        padding: const EdgeInsets.only(top: 10),
        child: OutlinedButton.icon(
          onPressed: () => _showJourneyVideo(story),
          icon: const Icon(Icons.play_circle_outline_rounded, size: 18),
          label: const Text('영상 보기'),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.p300,
            side: const BorderSide(color: AppColors.p400),
          ),
        ),
      );
    }

    if (status == 'pending' ||
        status == 'running' ||
        status == 'waiting_for_images') {
      final label = status == 'waiting_for_images'
          ? '삽화 준비 중 · 준비되면 영상 합성을 시작해요'
          : status == 'pending'
          ? '동화 영상 생성 대기 중'
          : '동화 영상 만드는 중';
      return Padding(
        padding: const EdgeInsets.only(top: 10),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (status != 'waiting_for_images') ...[
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: Text(
                label,
                style: const TextStyle(color: AppColors.gray, fontSize: 12),
              ),
            ),
          ],
        ),
      );
    }

    if (status == 'failed') {
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Wrap(
          spacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              story.assembledVideoError ?? '영상 합성에 실패했어요.',
              style: const TextStyle(color: Colors.orangeAccent, fontSize: 12),
            ),
            TextButton.icon(
              onPressed: () => _requestJourneyVideo(state, story),
              icon: const Icon(Icons.refresh_rounded, size: 17),
              label: const Text('다시 시도'),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: TextButton.icon(
        onPressed: () => _requestJourneyVideo(state, story),
        icon: const Icon(Icons.movie_creation_outlined, size: 17),
        label: const Text('동화 영상 만들기'),
      ),
    );
  }

  Future<void> _deleteStory(AppState state, StorySession story) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.pageSurface,
        title: const Text('동화를 삭제할까요?', style: TextStyle(color: Colors.white)),
        content: Text(
          '"${story.initialPrompt}" 기록과 연결된 단어장이 함께 삭제돼요.',
          style: const TextStyle(color: AppColors.gray),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('삭제', style: TextStyle(color: AppColors.pink2)),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final key = _storyKey(story);
    setState(() => _deletingStoryIds.add(key));
    final deleted = await state.deleteCompletedStory(story);
    if (!mounted) return;
    setState(() => _deletingStoryIds.remove(key));

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          deleted
              ? '동화를 삭제했어요.'
              : '삭제 실패: ${state.errorMessage ?? '알 수 없는 오류'}',
        ),
      ),
    );
  }

  Future<void> _renameStory(AppState state, StorySession story) async {
    final controller = TextEditingController(text: story.initialPrompt);
    final title = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.pageSurface,
        title: const Text('동화 제목 수정', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: '새 제목을 입력하세요',
            hintStyle: const TextStyle(color: AppColors.gray2),
            filled: true,
            fillColor: AppColors.pageInput,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(18),
              borderSide: const BorderSide(color: AppColors.border),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(18),
              borderSide: const BorderSide(color: AppColors.border),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(18),
              borderSide: const BorderSide(color: AppColors.p400, width: 1.5),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, controller.text.trim()),
            child: const Text('저장'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (title == null) return;

    final key = _storyKey(story);
    setState(() => _renamingStoryIds.add(key));
    final renamed = await state.renameCompletedStory(story, title);
    if (!mounted) return;
    setState(() => _renamingStoryIds.remove(key));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          renamed
              ? '동화 제목을 수정했어요.'
              : '수정 실패: ${state.errorMessage ?? '알 수 없는 오류'}',
        ),
      ),
    );
  }

  Widget _searchBox() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.border),
      ),
      child: TextField(
        controller: _searchController,
        onChanged: (value) => setState(() => _query = value),
        style: const TextStyle(color: Colors.white),
        decoration: const InputDecoration(
          icon: Icon(Icons.search, color: AppColors.gray2, size: 20),
          hintText: '동화 제목, 장르, 내용 검색...',
          hintStyle: TextStyle(color: AppColors.gray2),
          border: InputBorder.none,
        ),
      ),
    );
  }

  Widget _genreFilters() {
    return SizedBox(
      height: 38,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _genres.length,
        separatorBuilder: (_, _) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final genre = _genres[index];
          final selected = genre == _selectedGenre;
          return ChoiceChip(
            label: Text(genre),
            selected: selected,
            onSelected: (_) => setState(() => _selectedGenre = genre),
            selectedColor: AppColors.p700,
            backgroundColor: AppColors.pageSurface,
            labelStyle: TextStyle(
              color: selected ? Colors.white : AppColors.gray,
              fontWeight: FontWeight.w700,
            ),
            side: const BorderSide(color: AppColors.border),
          );
        },
      ),
    );
  }

  Widget _storyCard(AppState state, StorySession story) {
    final deleting = _deletingStoryIds.contains(_storyKey(story));
    final renaming = _renamingStoryIds.contains(_storyKey(story));
    final busy = deleting || renaming;
    final isInProgress = !story.hasReachedEnding && story.choices.isNotEmpty;
    final preview = story.fullStoryText.replaceAll(RegExp(r'\s+'), ' ').trim();
    final date = story.createdAt;
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: busy ? null : () => _openStory(story),
      child: Container(
        padding: const EdgeInsets.fromLTRB(18, 16, 8, 16),
        decoration: BoxDecoration(
          color: AppColors.pageSurface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
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
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  if (preview.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      preview,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white60,
                        height: 1.4,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 9),
                  Wrap(
                    spacing: 10,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        story.genre,
                        style: const TextStyle(
                          color: AppColors.p300,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      Text(
                        '${story.chapters.length}장면',
                        style: const TextStyle(
                          color: Colors.white54,
                          fontSize: 12,
                        ),
                      ),
                      Text(
                        '선택 ${story.allChoicesMade.length}회',
                        style: const TextStyle(
                          color: Colors.white54,
                          fontSize: 12,
                        ),
                      ),
                      if (story.isCommunityShared)
                        _statusBadge(
                          '커뮤니티에 공유됨',
                          Icons.public_rounded,
                          Colors.lightBlueAccent,
                        ),
                      if (isInProgress)
                        _statusBadge(
                          '만드는 중',
                          Icons.edit_note_rounded,
                          AppColors.pink,
                        ),
                      if (date != null)
                        Text(
                          '${date.year}.${date.month.toString().padLeft(2, '0')}.${date.day.toString().padLeft(2, '0')}',
                          style: const TextStyle(
                            color: Colors.white38,
                            fontSize: 12,
                          ),
                        ),
                    ],
                  ),
                  if (isInProgress) ...[
                    const SizedBox(height: 10),
                    FilledButton.icon(
                      onPressed: busy ? null : () => _resumeStory(state, story),
                      icon: const Icon(Icons.play_arrow_rounded),
                      label: const Text('이어하기'),
                      style: FilledButton.styleFrom(
                        backgroundColor: AppColors.pink,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 10,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                  ],
                  if (!story.hasReachedEnding && story.choices.isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text(
                        '이전 저장 상태가 없어 본문만 열 수 있어요.',
                        style: TextStyle(
                          color: Colors.orangeAccent,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  _journeyVideoAction(state, story),
                ],
              ),
            ),
            if (busy)
              const Padding(
                padding: EdgeInsets.all(10),
                child: SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              )
            else
              PopupMenuButton<String>(
                tooltip: '동화 메뉴',
                color: AppColors.pageSurface,
                onSelected: (value) {
                  if (value == 'edit') _renameStory(state, story);
                  if (value == 'delete') _deleteStory(state, story);
                },
                itemBuilder: (_) => const [
                  PopupMenuItem(
                    value: 'edit',
                    child: Text('제목 수정', style: TextStyle(color: Colors.white)),
                  ),
                  PopupMenuItem(
                    value: 'delete',
                    child: Text(
                      '삭제',
                      style: TextStyle(color: Colors.redAccent),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmpty(AppState state, bool hasFilter) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const SizedBox(height: 120),
        Text(
          hasFilter ? '조건에 맞는 동화가 없어요' : '📖',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: hasFilter ? Colors.white : null,
            fontSize: hasFilter ? 18 : 56,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 16),
        Text(
          hasFilter ? '검색어나 장르 필터를 바꿔보세요.' : '아직 읽은 동화가 없어요',
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          hasFilter ? '' : '동화를 만들어서 읽어보세요!',
          textAlign: TextAlign.center,
          style: const TextStyle(color: AppColors.gray, fontSize: 13),
        ),
        if (state.isUserDataLoading) ...[
          const SizedBox(height: 18),
          const Center(child: CircularProgressIndicator(color: AppColors.p400)),
        ],
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final data = context
        .select<
          AppState,
          ({String storiesKey, bool isLoading, String? error})
        >((state) {
          final storiesKey = state.completedStories
              .map(
                (story) =>
                    '${story.dbStoryId}|${story.storyId}|${story.initialPrompt}|${story.genre}|${story.chapters.length}|${story.fullStoryText.hashCode}|${story.allChoicesMade.length}|${story.currentChapter}|${story.hasReachedEnding}|${story.choices.length}|${story.isCommunityShared}|${story.assembledVideoStatus}|${story.assembledVideoUrl}|${story.assembledVideoError}',
              )
              .join('\u0000');
          return (
            storiesKey: storiesKey,
            isLoading: state.isUserDataLoading,
            error: state.userDataErrorMessage,
          );
        });
    final state = context.read<AppState>();
    final stories = _filteredStories(state.completedStories);
    final hasFilter = _query.trim().isNotEmpty || _selectedGenre != '전체';

    return Scaffold(
      backgroundColor: AppColors.pageBackground,
      appBar: AppBar(
        title: const Text('📚 내 서재'),
        backgroundColor: AppColors.pageBackground,
        actions: [
          IconButton(
            onPressed: data.isLoading
                ? null
                : () => context.read<AppState>().loadUserData(),
            icon: const Icon(Icons.sync),
            tooltip: 'DB 기록 새로고침',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => context.read<AppState>().loadUserData(),
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 10),
              sliver: SliverToBoxAdapter(
                child: Column(
                  children: [
                    Align(
                      alignment: Alignment.centerRight,
                      child: OutlinedButton.icon(
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const CommunityPage(initialTab: 2),
                          ),
                        ),
                        icon: const Icon(Icons.people_outline),
                        label: const Text('내가 공유한 동화'),
                      ),
                    ),
                    const SizedBox(height: 12),
                    _searchBox(),
                    const SizedBox(height: 14),
                    _genreFilters(),
                    if (data.error != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        data.error!,
                        style: const TextStyle(color: Colors.orangeAccent),
                      ),
                      TextButton(
                        onPressed: state.retryStorySync,
                        child: const Text('동화 저장 다시 시도'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            if (stories.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: _buildEmpty(state, hasFilter),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 32),
                sliver: SliverList.separated(
                  itemCount: stories.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 12),
                  itemBuilder: (context, index) =>
                      _storyCard(state, stories[index]),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
