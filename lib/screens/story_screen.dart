import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/app_state.dart';
import '../models/story_model.dart';
import 'psych_screen.dart';

class StoryScreen extends StatefulWidget {
  final StorySession? preloadedStory;
  const StoryScreen({super.key, this.preloadedStory});

  @override
  State<StoryScreen> createState() => _StoryScreenState();
}

class _StoryScreenState extends State<StoryScreen> {
  bool _showVocab = false;
  final _scrollCtrl = ScrollController();

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 600),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final story = widget.preloadedStory ?? state.currentStory;

    if (story == null) {
      return Scaffold(
        backgroundColor: AppColors.bg,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('📖', style: TextStyle(fontSize: 48)),
              const SizedBox(height: 16),
              const Text('동화가 없어요',
                  style: TextStyle(color: Colors.white, fontSize: 16)),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('돌아가기'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Stack(
        children: [
          _buildBackground(),
          SafeArea(
            child: Column(
              children: [
                _buildHeader(context, story),
                Expanded(
                  child: SingleChildScrollView(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildChapterInfo(story),
                        const SizedBox(height: 16),
                        ...story.chapters.map(
                            (c) => _buildChapterCard(c, story.chapters.length)),
                        if (state.isLoading) _buildLoadingCard(),
                        if (!state.isLoading && widget.preloadedStory == null)
                          ...[
                          const SizedBox(height: 24),
                          _buildChoices(context, story, state),
                        ],
                        if (story.vocab.isNotEmpty) ...[
                          const SizedBox(height: 24),
                          _buildVocabSection(story.vocab),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBackground() {
    return Positioned.fill(
      child: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.5),
            radius: 1.0,
            colors: [Color(0xFF160B3C), Color(0xFF06041A)],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, StorySession story) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: () {
              if (widget.preloadedStory != null) {
                Navigator.pop(context);
              } else {
                _showExitDialog(context);
              }
            },
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.arrow_back_ios_rounded,
                  color: Colors.white, size: 16),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  story.initialPrompt,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  '${story.genre} · ${_ageLabel(story.age)}',
                  style: const TextStyle(
                      color: AppColors.gray, fontSize: 11),
                ),
              ],
            ),
          ),
          if (widget.preloadedStory == null)
            GestureDetector(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const PsychScreen()),
              ),
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.pink.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: AppColors.pink.withOpacity(0.4)),
                ),
                child: const Text(
                  '🧠 분석',
                  style: TextStyle(
                      color: AppColors.pink, fontSize: 11,
                      fontWeight: FontWeight.w600),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildChapterInfo(StorySession story) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.p700.withOpacity(0.4),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              'Chapter ${story.currentChapter}',
              style: const TextStyle(
                  color: AppColors.p300, fontSize: 11,
                  fontWeight: FontWeight.w600),
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.teal.withOpacity(0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              '선택 ${story.allChoicesMade.length}회',
              style: const TextStyle(
                  color: AppColors.teal, fontSize: 11,
                  fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChapterCard(StoryChapter chapter, int totalChapters) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (chapter.choiceMade != null) ...[
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(
                horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.pink.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: AppColors.pink.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                const Text('👉', style: TextStyle(fontSize: 14)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    chapter.choiceMade!,
                    style: const TextStyle(
                        color: AppColors.pink2,
                        fontSize: 12,
                        fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ] else
          const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Text(
            chapter.text,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 15,
              height: 1.8,
              letterSpacing: 0.2,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildLoadingCard() {
    return Column(
      children: [
        const SizedBox(height: 20),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: [
              const CircularProgressIndicator(
                color: AppColors.p400,
                strokeWidth: 2,
              ),
              const SizedBox(height: 14),
              Text(
                'AI가 이야기를 이어쓰고 있어요...',
                style: TextStyle(
                    color: AppColors.p300.withOpacity(0.8),
                    fontSize: 13),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildChoices(
      BuildContext context, StorySession story, AppState state) {
    if (story.choices.isEmpty) return const SizedBox();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '어떻게 할까요?',
          style: TextStyle(
              color: Colors.white, fontSize: 16,
              fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 12),
        ...story.choices.asMap().entries.map((entry) {
          final i = entry.key;
          final choice = entry.value;
          final colors = [AppColors.p600, AppColors.pink, AppColors.teal];
          final emojis = ['🌟', '💫', '✨'];
          return Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: GestureDetector(
              onTap: () async {
                await state.continueStory(choice);
                _scrollToBottom();
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: colors[i % colors.length].withOpacity(0.12),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: colors[i % colors.length].withOpacity(0.4),
                  ),
                ),
                child: Row(
                  children: [
                    Text(emojis[i % emojis.length],
                        style: const TextStyle(fontSize: 18)),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        choice,
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            fontWeight: FontWeight.w500),
                      ),
                    ),
                    Icon(
                      Icons.arrow_forward_ios_rounded,
                      color: colors[i % colors.length],
                      size: 14,
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            onPressed: () => _finishStory(context, state),
            style: OutlinedButton.styleFrom(
              side: const BorderSide(color: AppColors.border),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: const Text(
              '🎉 여기서 이야기 끝내기',
              style: TextStyle(color: AppColors.gray, fontSize: 13),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildVocabSection(List<VocabWord> vocab) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GestureDetector(
          onTap: () => setState(() => _showVocab = !_showVocab),
          child: Container(
            padding: const EdgeInsets.symmetric(
                horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.teal.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: AppColors.teal.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                const Text('📚', style: TextStyle(fontSize: 16)),
                const SizedBox(width: 8),
                Text(
                  '단어 학습 (${vocab.length}개)',
                  style: const TextStyle(
                      color: AppColors.teal,
                      fontSize: 13,
                      fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                Icon(
                  _showVocab
                      ? Icons.keyboard_arrow_up_rounded
                      : Icons.keyboard_arrow_down_rounded,
                  color: AppColors.teal,
                ),
              ],
            ),
          ),
        ),
        if (_showVocab) ...[
          const SizedBox(height: 8),
          ...vocab.map((w) => _buildVocabCard(w)),
        ],
      ],
    );
  }

  Widget _buildVocabCard(VocabWord w) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                w.hard,
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 2),
              Text(
                '→ ${w.easy}',
                style: const TextStyle(
                    color: AppColors.teal, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              w.definition,
              style: const TextStyle(
                  color: AppColors.gray, fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }

  void _finishStory(BuildContext context, AppState state) {
    state.finishCurrentStory();
    Navigator.pop(context);
  }

  void _showExitDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.card,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20)),
        title: const Text('이야기를 그만할까요?',
            style: TextStyle(color: Colors.white)),
        content: const Text('지금까지의 이야기가 저장됩니다.',
            style: TextStyle(color: AppColors.gray)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('계속 읽기',
                style: TextStyle(color: AppColors.p400)),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<AppState>().finishCurrentStory();
              Navigator.pop(context);
            },
            child: const Text('나가기',
                style: TextStyle(color: AppColors.pink)),
          ),
        ],
      ),
    );
  }

  String _ageLabel(String age) {
    return const {
      '유아': '4-6세',
      '초등_저학년': '7-9세',
      '초등_고학년': '10-12세',
    }[age] ?? age;
  }
}
