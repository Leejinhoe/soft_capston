import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'main.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'story_page.dart';

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

  static const List<String> _genres = [
    '전체',
    '판타지',
    '모험',
    '우정',
    '자연',
    '동물',
    '미스터리',
  ];

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<StorySession> _filteredStories(List<StorySession> stories) {
    final query = _query.trim();
    return stories.where((story) {
      final matchesGenre =
          _selectedGenre == '전체' || story.genre == _selectedGenre;
      final matchesQuery = query.isEmpty ||
          story.initialPrompt.contains(query) ||
          story.genre.contains(query) ||
          story.fullStoryText.contains(query);
      return matchesGenre && matchesQuery;
    }).toList();
  }

  String _storyKey(StorySession story) => story.dbStoryId ?? story.storyId;

  Future<void> _deleteStory(AppState state, StorySession story) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.card,
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
        backgroundColor: AppColors.card,
        title: const Text('동화 제목 수정', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: '새 제목을 입력하세요',
            hintStyle: const TextStyle(color: AppColors.gray2),
            filled: true,
            fillColor: AppColors.bg2,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
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
        color: AppColors.card,
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
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final genre = _genres[index];
          final selected = genre == _selectedGenre;
          return ChoiceChip(
            label: Text(genre),
            selected: selected,
            onSelected: (_) => setState(() => _selectedGenre = genre),
            selectedColor: AppColors.p700,
            backgroundColor: AppColors.card,
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
    return InkWell(
      borderRadius: BorderRadius.circular(22),
      onTap: busy
          ? null
          : () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => StoryPage(preloadedStory: story),
                ),
              ),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            Container(
              width: 58,
              height: 58,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppColors.p700, AppColors.pink],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Center(
                child: Text(
                  _genreEmoji(story.genre),
                  style: const TextStyle(fontSize: 28),
                ),
              ),
            ),
            const SizedBox(width: 14),
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
                      fontSize: 15,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      _chip(story.genre, AppColors.p400),
                      _chip('${story.chapters.length}챕터', AppColors.teal),
                      _chip(
                          '선택 ${story.allChoicesMade.length}회', AppColors.pink),
                      if (story.dbStoryId != null)
                        _chip('DB 저장됨', Colors.greenAccent),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            busy
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        onPressed: () => _renameStory(state, story),
                        icon: const Icon(Icons.edit_outlined),
                        color: AppColors.gray2,
                        tooltip: '제목 수정',
                      ),
                      IconButton(
                        onPressed: () => _deleteStory(state, story),
                        icon: const Icon(Icons.delete_outline),
                        color: AppColors.gray2,
                        tooltip: '삭제',
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
          const Center(
            child: CircularProgressIndicator(color: AppColors.p400),
          ),
        ],
        if (state.userDataErrorMessage != null) ...[
          const SizedBox(height: 18),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Text(
              'DB 기록을 불러오지 못했어요: ${state.userDataErrorMessage}',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.orangeAccent, fontSize: 12),
            ),
          ),
        ],
      ],
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style:
            TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700),
      ),
    );
  }

  String _genreEmoji(String genre) {
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

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final stories = _filteredStories(state.completedStories);
    final hasFilter = _query.trim().isNotEmpty || _selectedGenre != '전체';

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: const Text('📚 내 서재'),
        backgroundColor: AppColors.bg,
        actions: [
          IconButton(
            onPressed: state.isUserDataLoading
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
                    _searchBox(),
                    const SizedBox(height: 14),
                    _genreFilters(),
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
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
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
