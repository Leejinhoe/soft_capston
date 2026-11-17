import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'app_theme.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';

const _visibleEmotionOrder = ['행복', '중립', '슬픔', '공포', '분노', '놀람'];
const _emotionPalette = <String, Color>{
  '행복': Color(0xFFFFC857),
  '중립': Color(0xFF8BA7D8),
  '슬픔': Color(0xFF38BDF8),
  '공포': Color(0xFFA78BFA),
  '분노': Color(0xFFF472B6),
  '놀람': Color(0xFFFF985F),
};

Map<String, double> _visibleEmotionScores(Map<String, double> scores) => {
  for (final label in _visibleEmotionOrder)
    if (scores[label]?.isFinite == true) label: scores[label]!.clamp(0.0, 1.0),
};

class PsychPage extends StatefulWidget {
  const PsychPage({super.key, this.onBack, this.story});

  final VoidCallback? onBack;
  final StorySession? story;

  @override
  State<PsychPage> createState() => _PsychPageState();
}

class _PsychPageState extends State<PsychPage> {
  final TextEditingController _searchController = TextEditingController();
  StorySession? _selectedStory;
  String _storyQuery = '';
  String? _selectedEmotionGroup;
  String? _selectedStoryEmotionGroup;

  String _emotionGroupKey(Map group) =>
      '${group['model']}|${(group['labels'] as List? ?? const []).join('|')}';
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      final state = context.read<AppState>();
      unawaited(state.loadUserData());
      unawaited(state.loadCumulativeEmotionSummary());
    });
  }

  @override
  void didUpdateWidget(covariant PsychPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.story == widget.story) return;
    _selectedStory = null;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      final state = context.read<AppState>();
      unawaited(state.loadUserData());
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadStoryEmotion(AppState state, StorySession? story) async {
    if (story == null ||
        !state.hasSignedInUser ||
        story.dbStoryId == null ||
        !state.canAnalyzeStory(story) ||
        state.isEmotionAnalysisLoading) {
      return;
    }
    if (state.emotionReportFor(story) == null) {
      await state.loadStoryEmotionAnalysis(story);
    }
    if (mounted) await state.restoreSavedPsychAnalysis(story);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.read<AppState>();
    final view = context
        .select<
          AppState,
          ({
            StorySession? story,
            String storiesKey,
            bool storiesLoading,
            String? storiesNotice,
            PsychResult? psych,
            bool canAnalyze,
            bool isLoading,
            bool restoreLoading,
            String? notice,
            Map<String, dynamic>? emotionReport,
            bool emotionLoading,
            String? emotionNotice,
            Map<String, dynamic>? cumulative,
            bool cumulativeLoading,
            String? cumulativeNotice,
          })
        >((state) {
          final story = _selectedStory;
          final stories = _analysisStories(state);
          return (
            story: story,
            storiesKey: stories
                .map(
                  (item) =>
                      '${_storyKey(item)}|${item.initialPrompt}|${item.chapters.length}|${item.choiceEmotionHistory.length}',
                )
                .join('\u0000'),
            storiesLoading: state.isUserDataLoading,
            storiesNotice: state.userDataErrorMessage,
            psych: story == null ? null : state.psychResultFor(story),
            canAnalyze: story != null && state.canAnalyzeStory(story),
            isLoading: state.isPsychLoading,
            restoreLoading: state.isPsychRestoreLoading,
            notice: state.psychAnalysisNotice,
            emotionReport: story == null ? null : state.emotionReportFor(story),
            emotionLoading: state.isEmotionAnalysisLoading,
            emotionNotice: state.emotionAnalysisNotice,
            cumulative: state.cumulativeEmotionSummary,
            cumulativeLoading: state.isCumulativeEmotionLoading,
            cumulativeNotice: state.cumulativeEmotionNotice,
          );
        });

    return Scaffold(
      backgroundColor: AppColors.pageBackground,
      appBar: AppBar(
        backgroundColor: AppColors.pageBackground,
        title: Text(
          view.story == null ? '심리 분석' : '동화 선택 해설',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        centerTitle: true,
        leading: IconButton(
          key: const Key('psych-back'),
          tooltip: view.story == null ? '뒤로가기' : '동화 목록으로',
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: view.story == null
              ? (widget.onBack ?? () => Navigator.of(context).maybePop())
              : _returnToPicker,
        ),
      ),
      body: SafeArea(
        child: view.story == null
            ? _buildStoryPicker(
                state,
                _analysisStories(state),
                isLoading: view.storiesLoading,
                notice: view.storiesNotice,
              )
            : _buildBody(
                context,
                state,
                view.story!,
                view.psych,
                canAnalyze: view.canAnalyze,
                isPsychLoading: view.isLoading,
                isPsychRestoreLoading: view.restoreLoading,
                notice: view.notice,
              ),
      ),
    );
  }

  String _storyKey(StorySession story) => story.dbStoryId?.isNotEmpty == true
      ? 'db:${story.dbStoryId}'
      : 'story:${story.storyId}';

  List<StorySession> _analysisStories(AppState state) {
    final candidates = [
      if (state.currentStory != null) state.currentStory!,
      ...state.completedStories,
      if (widget.story != null) widget.story!,
    ];
    final seen = <String>{};
    return candidates
        .where((story) => story.chapters.isNotEmpty)
        .where((story) => seen.add(_storyKey(story)))
        .toList(growable: false);
  }

  List<StorySession> _filteredStories(List<StorySession> stories) {
    final query = _storyQuery.trim().toLowerCase();
    if (query.isEmpty) return stories;
    return stories
        .where((story) {
          return story.initialPrompt.toLowerCase().contains(query) ||
              story.genre.toLowerCase().contains(query) ||
              story.fullStoryText.toLowerCase().contains(query);
        })
        .toList(growable: false);
  }

  void _selectStory(AppState state, StorySession story) {
    setState(() {
      _selectedStory = story;
      _selectedEmotionGroup = null;
      _selectedStoryEmotionGroup = null;
    });
    unawaited(_loadStoryEmotion(state, story));
  }

  void _returnToPicker() {
    setState(() {
      _selectedStory = null;
      _selectedEmotionGroup = null;
      _selectedStoryEmotionGroup = null;
    });
  }

  Widget _buildStoryPicker(
    AppState state,
    List<StorySession> allStories, {
    required bool isLoading,
    required String? notice,
  }) {
    final stories = _filteredStories(allStories);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPageTitle(selectingStory: true),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 3),
            decoration: BoxDecoration(
              color: AppColors.pageSurface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: TextField(
              controller: _searchController,
              onChanged: (value) => setState(() => _storyQuery = value),
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                icon: Icon(Icons.search, color: AppColors.gray2),
                hintText: '동화 제목, 장르, 내용 검색',
                hintStyle: TextStyle(color: AppColors.gray2),
                border: InputBorder.none,
              ),
            ),
          ),
          if (notice != null) ...[
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF59E0B).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                notice,
                style: const TextStyle(color: Color(0xFFFCD34D), fontSize: 12),
              ),
            ),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: Text(
                  '분석할 동화 ${stories.length}편',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              IconButton(
                tooltip: '서재 새로고침',
                onPressed: isLoading ? null : () => state.loadUserData(),
                icon: isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync, color: AppColors.p300),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Expanded(
            child: stories.isEmpty
                ? Center(
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(26),
                      decoration: BoxDecoration(
                        color: AppColors.pageSurface,
                        borderRadius: BorderRadius.circular(22),
                        border: Border.all(color: Colors.white10),
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(
                            Icons.auto_stories_rounded,
                            size: 46,
                            color: AppColors.p300,
                          ),
                          const SizedBox(height: 14),
                          Text(
                            allStories.isEmpty
                                ? '아직 분석할 동화가 없어요'
                                : '검색 결과가 없어요',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            '동화를 선택하면 그 이야기에서 고른 문장과 저장된 분류 점수를 확인할 수 있어요.',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                              height: 1.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                : ListView.separated(
                    itemCount: stories.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (context, index) =>
                        _storyPickerCard(state, stories[index]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _storyPickerCard(AppState state, StorySession story) {
    final choices = story.choiceEmotionHistory.length;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        key: Key('psych-story-${_storyKey(story)}'),
        borderRadius: BorderRadius.circular(20),
        onTap: () => _selectStory(state, story),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.pageSurface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            children: [
              Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  color: AppColors.p500.withValues(alpha: 0.24),
                  borderRadius: BorderRadius.circular(15),
                ),
                child: const Icon(
                  Icons.auto_stories_rounded,
                  color: AppColors.p300,
                  size: 25,
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      story.initialPrompt.trim().isEmpty
                          ? '나의 동화'
                          : story.initialPrompt,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        height: 1.35,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      '${story.genre} · ${story.chapters.length}장면 · 선택 $choices회',
                      style: const TextStyle(
                        color: Colors.white60,
                        fontSize: 11,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      choices > 0 ? '선택 기록 분석 가능' : '선택 기록이 아직 없어요',
                      style: TextStyle(
                        color: choices > 0 ? AppColors.teal : AppColors.gray2,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right, color: AppColors.p300),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    AppState state,
    StorySession? story,
    PsychResult? psych, {
    required bool canAnalyze,
    required bool isPsychLoading,
    required bool isPsychRestoreLoading,
    required String? notice,
  }) {
    if (story == null) return const SizedBox.shrink();
    if (story.chapters.isEmpty) return _buildChoiceRequiredState(story);

    if (!canAnalyze) {
      return _buildChoiceRequiredState(story);
    }

    if (psych == null) {
      return _buildAnalyzePrompt(
        context,
        state,
        story,
        isPsychLoading: isPsychLoading,
        isPsychRestoreLoading: isPsychRestoreLoading,
      );
    }

    return _buildResult(psych, story, notice, state);
  }

  Widget _buildChoiceRequiredState(StorySession story) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSelectedStoryHeader(story),
          const SizedBox(height: 18),
          _analysisPanel(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 34),
              child: Column(
                children: [
                  const Icon(
                    Icons.auto_stories_rounded,
                    size: 54,
                    color: AppColors.p300,
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    '한 번 선택하면 바로 분석할 수 있어요',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '아직 고른 선택이 없어요. 이야기를 읽고 한 번 선택하면\n'
                    '엔딩 전에도 지금까지의 선택과 감정 분류를 분석할 수 있어요.',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 13,
                      height: 1.6,
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

  Widget _buildPageTitle({bool selectingStory = false}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.p500, AppColors.pink],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: AppColors.p500.withValues(alpha: 0.18),
            blurRadius: 22,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            selectingStory ? '동화별 선택 기록  ✨' : '선택한 동화의 기록  ✨',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            selectingStory ? '분석할 동화를 선택하세요' : '동화 선택·감정 분석',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 28,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            selectingStory
                ? '서재에서 이야기를 고르면 해당 동화의 선택 기록만 분석해요.'
                : '아래 동화 제목을 확인한 뒤 그 이야기의 선택과 점수를 살펴봐요.',
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 14,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSelectedStoryHeader(StorySession story) {
    return Container(
      key: const Key('psych-selected-story'),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
      decoration: BoxDecoration(
        color: AppColors.p500.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppColors.p300.withValues(alpha: 0.32)),
      ),
      child: Row(
        children: [
          const Icon(Icons.menu_book_rounded, color: AppColors.p300),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  story.initialPrompt.trim().isEmpty
                      ? '나의 동화'
                      : story.initialPrompt,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${story.genre} · ${story.chapters.length}장면 · 선택 ${story.choiceEmotionHistory.length}회',
                  style: const TextStyle(color: Colors.white70, fontSize: 11),
                ),
              ],
            ),
          ),
          TextButton(
            key: const Key('psych-change-story'),
            onPressed: _returnToPicker,
            child: const Text('변경'),
          ),
        ],
      ),
    );
  }

  Widget _analysisPanel({required Widget child}) => Container(
    key: const Key('psych-analysis-panel'),
    width: double.infinity,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: const Color(0xFF0D061B),
      borderRadius: BorderRadius.circular(22),
      border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
    ),
    child: child,
  );

  Widget _innerAnalysisCard({required Widget child}) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: AppColors.pageSurface,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
    ),
    child: child,
  );

  Widget _analysisCaution() => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: 0.05),
      borderRadius: BorderRadius.circular(13),
    ),
    child: const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.info_outline_rounded, color: Colors.white54, size: 17),
        SizedBox(width: 8),
        Expanded(
          child: Text(
            '동화 속 선택에 대한 참고 해설이며, 아이의 실제 감정이나 심리 상태를 진단하지 않아요.',
            style: TextStyle(color: Colors.white60, fontSize: 11, height: 1.45),
          ),
        ),
      ],
    ),
  );

  Widget _buildCumulativeDisclosure(AppState state) => Material(
    color: AppColors.pageSurface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(18),
      side: const BorderSide(color: AppColors.border),
    ),
    clipBehavior: Clip.antiAlias,
    child: Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        key: const Key('cumulative-emotion-disclosure'),
        tilePadding: const EdgeInsets.symmetric(horizontal: 16),
        childrenPadding: const EdgeInsets.fromLTRB(10, 0, 10, 12),
        iconColor: AppColors.p300,
        collapsedIconColor: AppColors.p300,
        title: const Text(
          '모든 동화의 누적 감정 흐름',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
        ),
        subtitle: const Text(
          '전체 기록을 그래프로 확인',
          style: TextStyle(color: Colors.white54, fontSize: 11),
        ),
        children: [_buildCumulativePanel(state)],
      ),
    ),
  );

  Widget _buildAnalyzePrompt(
    BuildContext context,
    AppState state,
    StorySession story, {
    bool isPsychLoading = false,
    bool isPsychRestoreLoading = false,
  }) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSelectedStoryHeader(story),
          const SizedBox(height: 18),
          _analysisPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '동화 속 선택과 감정을 함께 돌아봐요',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final graph = _buildEmotionPanel(state, story);
                    final explanation = _buildExplanationPlaceholder(
                      context,
                      state,
                      story,
                      isPsychLoading: isPsychLoading,
                      isPsychRestoreLoading: isPsychRestoreLoading,
                    );
                    if (constraints.maxWidth < 760) {
                      return Column(
                        children: [
                          graph,
                          const SizedBox(height: 14),
                          explanation,
                        ],
                      );
                    }
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(child: graph),
                        const SizedBox(width: 16),
                        Expanded(child: explanation),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _buildCumulativeDisclosure(state),
          if (!story.hasReachedEnding) ...[
            const SizedBox(height: 12),
            _buildProgressNotice(story),
          ],
        ],
      ),
    );
  }

  Widget _buildExplanationPlaceholder(
    BuildContext context,
    AppState state,
    StorySession story, {
    required bool isPsychLoading,
    required bool isPsychRestoreLoading,
  }) {
    final loading = isPsychLoading || isPsychRestoreLoading || state.isLoading;
    final loadingLabel = isPsychRestoreLoading
        ? '저장된 해설을 확인하고 있어요.'
        : 'AI가 선택 기록을 바탕으로 해설을 작성하고 있어요.';
    return _innerAnalysisCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'LLM 종합 해설',
            style: TextStyle(
              color: AppColors.p300,
              fontSize: 15,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 5),
          const Text(
            '선택 기록과 저장된 감정 분류 결과를 함께 살펴봅니다',
            style: TextStyle(color: Colors.white54, fontSize: 11),
          ),
          const SizedBox(height: 16),
          if (loading) ...[
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(height: 12),
            Text(
              loadingLabel,
              style: const TextStyle(color: Colors.white70, height: 1.5),
            ),
          ] else ...[
            const Text(
              '아직 이 동화의 해설이 없어요. 아래 버튼을 누르면 선택한 장면과 저장된 점수를 바탕으로 해설을 만들어요.',
              style: TextStyle(color: Colors.white70, height: 1.6),
            ),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                key: const Key('psych-generate'),
                onPressed:
                    state.isEmotionAnalysisLoading ||
                        state.isPsychRestoreLoading ||
                        state.isLoading
                    ? null
                    : () => state.analyzeStoryAndHistory(story),
                icon: const Icon(Icons.auto_awesome_rounded, size: 18),
                label: Text(
                  state.isTemporaryEmotionTestStory(story)
                      ? '감정 점수 저장하고 해설 보기'
                      : '이 동화의 선택 해설 보기',
                ),
              ),
            ),
          ],
          const SizedBox(height: 16),
          _analysisCaution(),
          if (state.psychAnalysisNotice != null) ...[
            const SizedBox(height: 12),
            Text(
              state.psychAnalysisNotice!,
              style: const TextStyle(color: Color(0xFFFBBF24), fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCumulativePanel(AppState state) {
    final summary = state.cumulativeEmotionSummary;
    final groups = (summary?['groups'] as List? ?? const [])
        .whereType<Map>()
        .toList();
    final models = (summary?['models'] as List?) ?? const [];
    Map? selectedGroup;
    if (groups.isNotEmpty) {
      selectedGroup = groups
          .where((group) => _emotionGroupKey(group) == _selectedEmotionGroup)
          .firstOrNull;
      selectedGroup ??= groups
          .where((group) => (group['labels'] as List? ?? const []).length == 7)
          .firstOrNull;
      selectedGroup ??= groups.first;
    }
    final raw =
        selectedGroup?['averages'] ??
        (models.length > 1 ? null : summary?['averages']);
    final averages = raw is Map
        ? raw.entries
              .where((e) => e.value is num && (e.value as num).isFinite)
              .toList()
        : <MapEntry>[];
    averages.sort((a, b) => (b.value as num).compareTo(a.value as num));
    final visibleAverages = _visibleEmotionScores({
      for (final entry in averages)
        entry.key.toString(): (entry.value as num).toDouble(),
    });
    return Container(
      key: const Key('cumulative-emotion-panel'),
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '저장 동화와 임시 분석의 누적 선택 분류',
            style: TextStyle(
              color: Colors.white,
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            summary == null
                ? (state.isCumulativeEmotionLoading
                      ? '누적 기록을 불러오는 중이에요.'
                      : '누적 기록을 아직 확인하지 못했어요.')
                : '분석된 동화 ${summary['analyzed_stories'] ?? 0} / ${summary['total_stories'] ?? 0}편 · 임시 ${summary['temporary_stories'] ?? 0}편 포함 · 선택 ${summary['decisions'] ?? 0}개',
            style: const TextStyle(color: Colors.white70, fontSize: 12),
          ),
          const SizedBox(height: 8),
          const Text(
            '분석된 선택 문장의 분류 확률 평균이에요. 아이의 실제 감정, 성격이나 심리 상태를 뜻하지 않아요.',
            style: TextStyle(color: Colors.white70, fontSize: 12, height: 1.5),
          ),
          if (groups.length > 1) ...[
            const SizedBox(height: 12),
            const Text(
              '분류 모델별로 따로 보기',
              style: TextStyle(color: Colors.white70, fontSize: 13),
            ),
            const SizedBox(height: 6),
            DropdownButtonFormField<String>(
              initialValue: _emotionGroupKey(selectedGroup!),
              isExpanded: true,
              items: groups
                  .map(
                    (group) => DropdownMenuItem(
                      value: _emotionGroupKey(group),
                      child: Text(
                        '${group['model']} · ${(group['labels'] as List).length}개 분류 · 선택 ${group['decisions']}개',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  )
                  .toList(),
              onChanged: (value) =>
                  setState(() => _selectedEmotionGroup = value),
            ),
          ] else if (selectedGroup != null) ...[
            const SizedBox(height: 8),
            Text(
              '${selectedGroup['model']} · ${(selectedGroup['labels'] as List).length}개 분류 · 선택 ${selectedGroup['decisions']}개',
              style: const TextStyle(color: AppColors.p300, fontSize: 12),
            ),
          ] else if (models.length > 1)
            const Text(
              '서로 다른 모델 결과는 합산하지 않아요. 최신 서버를 다시 실행해 주세요.',
              style: TextStyle(color: Colors.orangeAccent, fontSize: 12),
            ),
          if (state.isCumulativeEmotionLoading) ...[
            const SizedBox(height: 12),
            const LinearProgressIndicator(),
            const SizedBox(height: 6),
            const Text(
              '저장된 누적 분류 결과를 불러오고 있어요.',
              style: TextStyle(color: Colors.white70, fontSize: 12),
            ),
          ],
          if (state.cumulativeEmotionNotice != null) ...[
            const SizedBox(height: 8),
            Text(
              state.cumulativeEmotionNotice!,
              style: const TextStyle(color: Colors.orangeAccent, fontSize: 12),
            ),
          ],
          if (summary != null &&
              averages.isNotEmpty &&
              visibleAverages.isEmpty &&
              !state.isCumulativeEmotionLoading)
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Text(
                '이 분류 모델에는 표시하도록 정한 6개 감정 점수가 없어요.',
                style: TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ),
          if (summary != null &&
              averages.isEmpty &&
              !state.isCumulativeEmotionLoading)
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Text(
                '누적된 분류 결과가 아직 없어요.',
                style: TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ),
          if (visibleAverages.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: EmotionRadarChart(
                key: const Key('cumulative-emotion-radar'),
                values: visibleAverages,
                color: AppColors.teal,
              ),
            ),
          if (selectedGroup != null &&
              visibleAverages.isNotEmpty &&
              (selectedGroup['trend'] as List? ?? const []).length >= 2) ...[
            const SizedBox(height: 24),
            EmotionTrendChart(
              key: ValueKey('trend-${_emotionGroupKey(selectedGroup)}'),
              points: (selectedGroup['trend'] as List)
                  .whereType<Map>()
                  .toList(),
              labels: visibleAverages.keys.toList(growable: false),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildEmotionPanel(AppState state, StorySession story) {
    final isTemporaryStory = story.storyId.startsWith('mock_');
    final isTemporaryModelTest = state.isTemporaryEmotionTestStory(story);
    final report = state.emotionReportFor(story);
    final items = (report?['items'] as List? ?? const [])
        .whereType<Map>()
        .toList();
    final byLabels = <String, List<Map>>{};
    for (final item in items) {
      final scores = item['scores'];
      if (scores is! Map || scores.isEmpty) continue;
      final labels =
          scores.entries
              .where(
                (entry) => entry.value is num && (entry.value as num).isFinite,
              )
              .map((entry) => entry.key.toString())
              .toList()
            ..sort();
      if (labels.isNotEmpty) {
        byLabels.putIfAbsent(labels.join('|'), () => []).add(item);
      }
    }
    final selectedKey = byLabels.containsKey(_selectedStoryEmotionGroup)
        ? _selectedStoryEmotionGroup
        : byLabels.keys
                  .where((key) => key.split('|').length == 7)
                  .firstOrNull ??
              byLabels.keys.firstOrNull;
    final selectedItems = byLabels[selectedKey] ?? const <Map>[];
    final totals = <String, double>{};
    final scored = selectedItems.length;
    for (final item in selectedItems) {
      final scores = item['scores'] as Map;
      for (final entry in scores.entries) {
        final score = entry.value;
        if (score is num && score.isFinite) {
          final key = entry.key.toString();
          totals[key] = (totals[key] ?? 0) + score.toDouble().clamp(0, 1);
        }
      }
    }
    final averages = totals.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final averageScores = <String, double>{
      for (final entry in totals.entries)
        entry.key: scored == 0 ? 0 : entry.value / scored,
    };
    final visibleAverageScores = _visibleEmotionScores(averageScores);
    return Container(
      key: const Key('emotion-analysis-panel'),
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '이번 동화의 감정 그래프',
            style: TextStyle(
              color: Colors.white,
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            report?['model']?.toString() ??
                (isTemporaryStory
                    ? (isTemporaryModelTest
                          ? '임시 동화 · 실제 감정 분류 모델 테스트'
                          : '임시 생성 · 실제 감정 분류 모델 미실행')
                    : '선택할 때 저장된 한국어 문장 분류 결과'),
            style: const TextStyle(color: AppColors.p300, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Text(
            isTemporaryStory
                ? (isTemporaryModelTest
                      ? '임시 동화에서 고른 문장을 실제 분류 모델로 분석한 점수예요.'
                      : '임시 생성에서는 실제 감정 분류 점수를 만들지 않아요.')
                : '선택 당시 저장된 분류 점수예요. 화면을 열 때 모델을 다시 실행하지 않아요.',
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 11,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 14),
          if (state.isEmotionAnalysisLoading)
            const LinearProgressIndicator()
          else if (visibleAverageScores.isNotEmpty) ...[
            if (byLabels.length > 1) ...[
              const Text(
                '분류 체계별로 따로 보기',
                style: TextStyle(color: Colors.white70, fontSize: 13),
              ),
              const SizedBox(height: 6),
              DropdownButtonFormField<String>(
                initialValue: selectedKey,
                isExpanded: true,
                items: byLabels.entries
                    .map(
                      (entry) => DropdownMenuItem(
                        value: entry.key,
                        child: Text(
                          '${entry.key.split('|').length}개 분류 · 선택 ${entry.value.length}개',
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (value) =>
                    setState(() => _selectedStoryEmotionGroup = value),
              ),
              const SizedBox(height: 10),
            ],
            Text(
              '선택 문장 $scored개 평균',
              style: const TextStyle(color: Colors.white70, fontSize: 11),
            ),
            if (state.emotionAnalysisNotice != null) ...[
              const SizedBox(height: 6),
              Text(
                state.emotionAnalysisNotice!,
                style: const TextStyle(color: AppColors.teal, fontSize: 12),
              ),
            ],
            const SizedBox(height: 12),
            EmotionRadarChart(
              key: const Key('story-emotion-radar'),
              values: visibleAverageScores,
              color: AppColors.p400,
            ),
            const SizedBox(height: 12),
            if (items.length > 1)
              Theme(
                data: Theme.of(
                  context,
                ).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  key: const Key('story-emotion-details'),
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(top: 4),
                  iconColor: AppColors.p300,
                  collapsedIconColor: AppColors.p300,
                  title: const Text(
                    '선택별 분류 결과',
                    style: TextStyle(color: Colors.white70, fontSize: 12),
                  ),
                  subtitle: Text(
                    '${items.length}개 문장',
                    style: const TextStyle(color: Colors.white54, fontSize: 10),
                  ),
                  children: [
                    ...items.map((item) {
                      final step = item['step']?.toString() ?? '?';
                      final label = item['label']?.toString();
                      final summary = label == null || label.isEmpty
                          ? '분류 보류'
                          : label;
                      return _detailText('$step번째 선택 · $summary');
                    }),
                    if (items.any((item) => item['status'] == 'uncertain'))
                      _detailText('일부 문장은 확신이 낮아 감정 이름을 표시하지 않았어요.'),
                  ],
                ),
              ),
          ] else if (averages.isNotEmpty)
            const Text(
              '이 분류 모델에는 표시하도록 정한 6개 감정 점수가 없어요.',
              style: TextStyle(color: Colors.white70, fontSize: 12),
            )
          else
            Text(
              state.emotionAnalysisNotice ??
                  (isTemporaryStory
                      ? (isTemporaryModelTest
                            ? '선택지를 고른 뒤 아래 분석 버튼을 누르면 모델이 점수를 계산하고 저장해요.'
                            : '임시 동화에는 실제 모델 분류 결과가 없어요.')
                      : '저장된 감정 분류 결과가 아직 없어요. 다음 선택부터 점수가 기록됩니다.'),
              style: const TextStyle(color: Colors.white70, fontSize: 12),
            ),
        ],
      ),
    );
  }

  Widget _buildChoiceEmotionPreview(StoryChoiceEmotion record) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: AppColors.p600.withValues(alpha: 0.35),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Text(
              '${record.step}',
              style: const TextStyle(
                color: AppColors.p300,
                fontSize: 11,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.choice,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressNotice(StorySession story) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.p500.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.p300.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.bookmark_added_rounded, color: AppColors.p300),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '진행 중 동화 · 지금까지 ${story.choiceEmotionHistory.length}번 선택했어요. '
              '새 선택의 분류 점수는 선택할 때 저장되고, 이 화면에서는 저장된 결과만 불러와요.',
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 12,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResult(
    PsychResult psych,
    StorySession story,
    String? notice,
    AppState state,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSelectedStoryHeader(story),
          const SizedBox(height: 16),
          if (notice != null) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
              decoration: BoxDecoration(
                color: const Color(0xFFF59E0B).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.info_outline,
                    color: Color(0xFFFCD34D),
                    size: 18,
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      notice,
                      style: const TextStyle(
                        color: Color(0xFFFCD34D),
                        fontSize: 12,
                        height: 1.45,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],
          _analysisPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '동화 속 선택과 감정을 함께 돌아봐요',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final graph = _buildEmotionPanel(state, story);
                    final explanation = _buildLlmExplanation(psych);
                    if (constraints.maxWidth < 760) {
                      return Column(
                        children: [
                          graph,
                          const SizedBox(height: 14),
                          explanation,
                        ],
                      );
                    }
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(child: graph),
                        const SizedBox(width: 16),
                        Expanded(child: explanation),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          _buildCumulativeDisclosure(state),
          if (!story.hasReachedEnding) ...[
            const SizedBox(height: 12),
            _buildProgressNotice(story),
          ],
          if (story.choiceEmotionHistory.isNotEmpty) ...[
            const SizedBox(height: 10),
            _buildDetailsDisclosure(
              key: const Key('psych-choice-history-disclosure'),
              title: '고른 선택 기록',
              subtitle: '선택 ${story.choiceEmotionHistory.length}회',
              children: story.choiceEmotionHistory
                  .map(_buildChoiceEmotionPreview)
                  .toList(growable: false),
            ),
          ],
          if (psych.choiceInsights.isNotEmpty) ...[
            const SizedBox(height: 8),
            _buildDetailsDisclosure(
              key: const Key('psych-choice-insights-disclosure'),
              title: '선택별 관찰',
              subtitle: '${psych.choiceInsights.length}개 기록',
              children: psych.choiceInsights
                  .asMap()
                  .entries
                  .map(
                    (entry) => _detailText('${entry.key + 1}. ${entry.value}'),
                  )
                  .toList(growable: false),
            ),
          ],
          if (psych.caregiverPrompts.isNotEmpty) ...[
            const SizedBox(height: 8),
            _buildDetailsDisclosure(
              key: const Key('psych-caregiver-prompts-disclosure'),
              title: '함께 이야기해 보기',
              subtitle: '대화 질문 ${psych.caregiverPrompts.length}개',
              children: psych.caregiverPrompts
                  .asMap()
                  .entries
                  .map(
                    (entry) => _detailText('${entry.key + 1}. ${entry.value}'),
                  )
                  .toList(growable: false),
            ),
          ],
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              key: const Key('psych-regenerate'),
              onPressed:
                  state.isEmotionAnalysisLoading ||
                      state.isPsychRestoreLoading ||
                      state.isLoading
                  ? null
                  : () => state.analyzeStoryAndHistory(
                      story,
                      forceRegenerate: true,
                    ),
              icon: const Icon(Icons.refresh_rounded, size: 17),
              label: Text(state.isPsychRestoreLoading ? '해설 확인 중' : '해설 다시 생성'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLlmExplanation(PsychResult psych) => _innerAnalysisCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'LLM 종합 해설',
          style: TextStyle(
            color: AppColors.p300,
            fontSize: 15,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 5),
        const Text(
          '선택 기록과 저장된 감정 분류 결과를 바탕으로',
          style: TextStyle(color: Colors.white54, fontSize: 11),
        ),
        const SizedBox(height: 14),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(15),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppColors.p600.withValues(alpha: 0.4),
                AppColors.pink.withValues(alpha: 0.28),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.p400.withValues(alpha: 0.22)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.auto_awesome_rounded,
                    color: Color(0xFFFFD76A),
                    size: 17,
                  ),
                  const SizedBox(width: 7),
                  Expanded(
                    child: Text(
                      psych.type.trim().isEmpty ? '이야기를 함께 돌아봐요' : psych.type,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                psych.description,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  height: 1.65,
                ),
              ),
              if (psych.dominantEmotions.isNotEmpty) ...[
                const SizedBox(height: 14),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: psych.dominantEmotions
                      .map(
                        (emotion) => Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 9,
                            vertical: 5,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.18),
                            borderRadius: BorderRadius.circular(18),
                          ),
                          child: Text(
                            emotion,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      )
                      .toList(growable: false),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        _analysisCaution(),
      ],
    ),
  );

  Widget _buildDetailsDisclosure({
    required Key key,
    required String title,
    required String subtitle,
    required List<Widget> children,
  }) => Material(
    color: AppColors.pageSurface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: AppColors.border),
    ),
    clipBehavior: Clip.antiAlias,
    child: Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        key: key,
        tilePadding: const EdgeInsets.symmetric(horizontal: 15),
        childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
        iconColor: AppColors.p300,
        collapsedIconColor: AppColors.p300,
        title: Text(
          title,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w700,
          ),
        ),
        subtitle: Text(
          subtitle,
          style: const TextStyle(color: Colors.white54, fontSize: 11),
        ),
        children: children,
      ),
    ),
  );

  Widget _detailText(String text) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Align(
      alignment: Alignment.centerLeft,
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white70,
          fontSize: 12,
          height: 1.55,
        ),
      ),
    ),
  );
}

class EmotionRadarChart extends StatelessWidget {
  const EmotionRadarChart({
    super.key,
    required this.values,
    required this.color,
  });

  final Map<String, double> values;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final entries = _visibleEmotionScores(values).entries.toList();
    final top = entries;
    if (top.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '감정 분류 점수',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.w700,
          ),
        ),
        if (top.length >= 3)
          Center(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final availableWidth = constraints.maxWidth.isFinite
                    ? constraints.maxWidth
                    : 290.0;
                final chartWidth = math.min(290.0, availableWidth);
                return SizedBox(
                  width: chartWidth,
                  height: chartWidth * 0.93,
                  child: CustomPaint(
                    painter: _EmotionRadarChartPainter(
                      values: {for (final entry in top) entry.key: entry.value},
                      color: color,
                    ),
                  ),
                );
              },
            ),
          )
        else
          const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (var i = 0; i < top.length; i++)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
                decoration: BoxDecoration(
                  color: (_emotionPalette[top[i].key] ?? color).withValues(
                    alpha: 0.10,
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: _emotionPalette[top[i].key] ?? color,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      '${top[i].key} ${(top[i].value.clamp(0.0, 1.0) * 100).round()}%',
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _EmotionRadarChartPainter extends CustomPainter {
  _EmotionRadarChartPainter({required this.values, required this.color});

  final Map<String, double> values;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final entries = values.entries.toList();
    if (entries.isEmpty) return;

    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width * 0.30, size.height * 0.32);
    final angles = List<double>.generate(
      entries.length,
      (index) => -math.pi / 2 + (2 * math.pi * index / entries.length),
    );
    Offset pointAt(int index, double scale) => Offset(
      center.dx + math.cos(angles[index]) * radius * scale,
      center.dy + math.sin(angles[index]) * radius * scale,
    );

    final gridPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.12)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    const scales = [0.25, 0.5, 0.75, 1.0];
    for (final scale in scales) {
      final grid = Path()..moveTo(pointAt(0, scale).dx, pointAt(0, scale).dy);
      for (var index = 1; index < entries.length; index++) {
        final point = pointAt(index, scale);
        grid.lineTo(point.dx, point.dy);
      }
      grid.close();
      canvas.drawPath(grid, gridPaint);

      final scaleLabel = TextPainter(
        text: TextSpan(
          text: '${(scale * 100).round()}',
          style: const TextStyle(color: Colors.white38, fontSize: 8),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      scaleLabel.paint(
        canvas,
        Offset(
          center.dx + 3,
          center.dy - radius * scale - scaleLabel.height / 2,
        ),
      );
    }

    final axisPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.15)
      ..strokeWidth = 1;
    for (var index = 0; index < entries.length; index++) {
      final point = pointAt(index, 1);
      canvas.drawLine(center, point, axisPaint);
    }

    final scorePath = Path();
    for (var index = 0; index < entries.length; index++) {
      final score = entries[index].value.isFinite
          ? entries[index].value.clamp(0.0, 1.0)
          : 0.0;
      final point = pointAt(index, score);
      if (index == 0) {
        scorePath.moveTo(point.dx, point.dy);
      } else {
        scorePath.lineTo(point.dx, point.dy);
      }
    }
    scorePath.close();
    canvas.drawPath(
      scorePath,
      Paint()
        ..color = color.withValues(alpha: 0.18)
        ..style = PaintingStyle.fill,
    );
    canvas.drawPath(
      scorePath,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = StrokeJoin.round,
    );

    for (var index = 0; index < entries.length; index++) {
      final rawScore = entries[index].value;
      final score = rawScore.isFinite ? rawScore.clamp(0.0, 1.0) : 0.0;
      final point = pointAt(index, score);
      canvas.drawCircle(point, 4.5, Paint()..color = color);

      final angle = angles[index];
      final labelCenter = Offset(
        center.dx + math.cos(angle) * (radius + 18),
        center.dy + math.sin(angle) * (radius + 18),
      );
      final label = TextPainter(
        text: TextSpan(
          text: entries[index].key,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        ),
        textDirection: TextDirection.ltr,
        textAlign: TextAlign.center,
      )..layout();
      final labelX = math.cos(angle) < -0.25
          ? labelCenter.dx - label.width
          : math.cos(angle) > 0.25
          ? labelCenter.dx
          : labelCenter.dx - label.width / 2;
      label.paint(canvas, Offset(labelX, labelCenter.dy - label.height / 2));
    }
  }

  @override
  bool shouldRepaint(covariant _EmotionRadarChartPainter oldDelegate) =>
      oldDelegate.values != values || oldDelegate.color != color;
}

const _trendColors = [
  Color(0xFFA78BFA),
  Color(0xFFF472B6),
  Color(0xFF2DD4BF),
  Color(0xFFFBBF24),
  Color(0xFF60A5FA),
];

class EmotionTrendChart extends StatefulWidget {
  const EmotionTrendChart({
    super.key,
    required this.points,
    required this.labels,
  });
  final List<Map> points;
  final List<String> labels;

  @override
  State<EmotionTrendChart> createState() => _EmotionTrendChartState();
}

class _EmotionTrendChartState extends State<EmotionTrendChart> {
  late Set<String> shown;

  @override
  void initState() {
    super.initState();
    shown = widget.labels.toSet();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '최근 선택 문장 분류 추이',
          style: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          '최근 최대 5회 분석의 선택 문장 점수 평균이에요. 가로축은 분석 순번이며 동화 제목은 표시하지 않아요. 아이의 실제 심리 변화로 볼 수는 없어요.',
          style: TextStyle(color: Colors.white60, fontSize: 12, height: 1.5),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: [
            for (var i = 0; i < widget.labels.length; i++)
              FilterChip(
                label: Text(widget.labels[i]),
                selected: shown.contains(widget.labels[i]),
                onSelected: (enabled) => setState(() {
                  if (enabled) {
                    shown.add(widget.labels[i]);
                  } else {
                    shown.remove(widget.labels[i]);
                  }
                }),
                selectedColor: _trendColors[i % _trendColors.length].withValues(
                  alpha: 0.25,
                ),
                checkmarkColor: _trendColors[i % _trendColors.length],
                side: BorderSide(
                  color: _trendColors[i % _trendColors.length].withValues(
                    alpha: 0.6,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 210,
          width: double.infinity,
          child: CustomPaint(
            painter: _EmotionTrendPainter(
              points: widget.points,
              labels: widget.labels,
              shown: shown,
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          '가로축: 이전 분석에서 최근 분석 순서',
          style: TextStyle(color: Colors.white60, fontSize: 11),
        ),
      ],
    );
  }
}

class _EmotionTrendPainter extends CustomPainter {
  const _EmotionTrendPainter({
    required this.points,
    required this.labels,
    required this.shown,
  });
  final List<Map> points;
  final List<String> labels;
  final Set<String> shown;

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    const left = 38.0;
    const top = 12.0;
    const bottom = 24.0;
    final width = math.max(0.0, size.width - left - 12);
    final height = math.max(0.0, size.height - top - bottom);
    for (final level in [0.0, 0.5, 1.0]) {
      final y = top + (1 - level) * height;
      canvas.drawLine(
        Offset(left, y),
        Offset(left + width, y),
        Paint()..color = Colors.white12,
      );
      final label = TextPainter(
        text: TextSpan(
          text: '${(level * 100).round()}%',
          style: const TextStyle(color: Colors.white54, fontSize: 10),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      label.paint(canvas, Offset(0, y - label.height / 2));
    }
    for (var i = 0; i < points.length; i++) {
      final x = left + width * i / (points.length - 1);
      final label = TextPainter(
        text: TextSpan(
          text: '${i + 1}',
          style: const TextStyle(color: Colors.white54, fontSize: 10),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      label.paint(canvas, Offset(x - label.width / 2, top + height + 6));
    }
    for (var series = 0; series < labels.length; series++) {
      final key = labels[series];
      if (!shown.contains(key)) continue;
      final color = _trendColors[series % _trendColors.length];
      final path = Path();
      var drawing = false;
      for (var i = 0; i < points.length; i++) {
        final averages = points[i]['averages'];
        final raw = averages is Map ? averages[key] : null;
        if (raw is! num || !raw.isFinite) {
          drawing = false;
          continue;
        }
        final x = left + width * i / (points.length - 1);
        final y = top + (1 - raw.toDouble().clamp(0.0, 1.0)) * height;
        if (drawing) {
          path.lineTo(x, y);
        } else {
          path.moveTo(x, y);
          drawing = true;
        }
        canvas.drawCircle(Offset(x, y), 3.5, Paint()..color = color);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _EmotionTrendPainter oldDelegate) => true;
}
