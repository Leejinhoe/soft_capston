import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:percent_indicator/percent_indicator.dart';
import 'main.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';

class PsychPage extends StatefulWidget {
  const PsychPage({super.key});

  @override
  State<PsychPage> createState() => _PsychPageState();
}

class _PsychPageState extends State<PsychPage> {
  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final story = state.activePsychStory;
    final psych = state.psychResult;

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      body: SafeArea(
        child: _buildBody(context, state, story, psych),
      ),
    );
  }

  Widget _buildBody(BuildContext context, AppState state, StorySession? story,
      PsychResult? psych) {
    if (story == null || story.chapters.isEmpty) {
      return _buildEmptyState();
    }

    if (state.isPsychLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('🔮', style: TextStyle(fontSize: 56)),
            SizedBox(height: 20),
            CircularProgressIndicator(color: AppColors.p400, strokeWidth: 2),
            SizedBox(height: 16),
            Text(
              'AI가 성격을 분석하고 있어요...',
              style: TextStyle(color: AppColors.p300, fontSize: 14),
            ),
          ],
        ),
      );
    }

    if (psych == null) {
      return _buildAnalyzePrompt(context, state, story);
    }

    return _buildResult(psych, story);
  }

  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 10),
          const Text(
            'AI 심리 분석',
            style: TextStyle(
              color: Colors.white,
              fontSize: 34,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            '동화를 만들면 AI가 성향을 분석해요',
            style: TextStyle(color: Colors.white70, fontSize: 16),
          ),
          const Spacer(),
          Center(
            child: Container(
              padding: const EdgeInsets.all(28),
              decoration: BoxDecoration(
                color: const Color(0xFF140028),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: Colors.white10),
              ),
              child: const Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('📖', style: TextStyle(fontSize: 56)),
                  SizedBox(height: 20),
                  Text(
                    '아직 분석할 동화가 없어요',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    '동화를 하나 만들면\n이야기 분위기와 선택을 함께 분석해요!',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
          const Spacer(),
          const SizedBox(height: 100),
        ],
      ),
    );
  }

  Widget _buildPageTitle() {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(height: 10),
        Text(
          'AI 심리 분석',
          style: TextStyle(
            color: Colors.white,
            fontSize: 34,
            fontWeight: FontWeight.bold,
          ),
        ),
        SizedBox(height: 10),
        Text(
          '내 선택으로 만든 성향 결과를 확인해보세요',
          style: TextStyle(color: Colors.white70, fontSize: 16),
        ),
      ],
    );
  }

  Widget _buildAnalyzePrompt(
      BuildContext context, AppState state, StorySession story) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPageTitle(),
          const Spacer(),
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: const Color(0xFF140028),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              children: [
                const Text('🔮', style: TextStyle(fontSize: 60)),
                const SizedBox(height: 16),
                const Text(
                  '내 성격 알아보기',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(
                  '${story.chapters.length}개의 장면과 ${story.allChoicesMade.length}번의 선택을 바탕으로\n나의 성격 유형을 알려드릴게요',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
                if (story.allChoicesMade.isEmpty) ...[
                  const SizedBox(height: 8),
                  const Text(
                    '선택 전에는 이야기 감정 데이터 중심으로 먼저 분석해요.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.p300, fontSize: 12),
                  ),
                ],
                const SizedBox(height: 8),
                // 선택 목록
                if (story.allChoicesMade.isEmpty)
                  ...story.chapters.take(3).map((chapter) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Row(
                          children: [
                            const Icon(Icons.auto_stories_rounded,
                                color: AppColors.teal, size: 14),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                '${chapter.chapter}장 · ${chapter.text.replaceAll('\n', ' ').trim()}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    color: Colors.white70, fontSize: 11),
                              ),
                            ),
                          ],
                        ),
                      ))
                else
                  ...story.allChoicesMade.take(5).map((c) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Row(
                          children: [
                            const Icon(Icons.check_circle_rounded,
                                color: Colors.greenAccent, size: 14),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(c,
                                  style: const TextStyle(
                                      color: Colors.white70, fontSize: 11)),
                            ),
                          ],
                        ),
                      )),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => state.loadPsychAnalysis(),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF8B5CF6),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                    ),
                    child: const Text(
                      '🧠 분석 시작',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 15,
                          fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const Spacer(),
          const SizedBox(height: 100),
        ],
      ),
    );
  }

  Widget _buildResult(PsychResult psych, StorySession story) {
    const traitColors = {
      '모험적': AppColors.p500,
      '친절함': AppColors.pink,
      '용감함': Color(0xFFF59E0B),
      '창의적': AppColors.teal,
      '협동심': Color(0xFF10B981),
    };

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPageTitle(),
          const SizedBox(height: 30),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
              ),
              borderRadius: BorderRadius.circular(24),
            ),
            child: Column(
              children: [
                const Text('🌟', style: TextStyle(fontSize: 52)),
                const SizedBox(height: 12),
                Text(
                  psych.type,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  psych.description,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 14,
                    height: 1.6,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // 특성 분석
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF140028),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '특성 분석',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                ...psych.traits.entries.map((e) {
                  final color = traitColors[e.key] ?? AppColors.p400;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(e.key,
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600)),
                            Text(
                              '${e.value}%',
                              style: TextStyle(
                                  color: color,
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        LinearPercentIndicator(
                          percent: (e.value / 100).clamp(0.0, 1.0),
                          lineHeight: 8,
                          barRadius: const Radius.circular(4),
                          backgroundColor: color.withValues(alpha: 0.15),
                          progressColor: color,
                          padding: EdgeInsets.zero,
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // 선택 이력
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFF140028),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  story.allChoicesMade.isEmpty ? '분석한 이야기' : '나의 선택 이야기',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                if (story.allChoicesMade.isEmpty)
                  ...story.chapters.asMap().entries.map((e) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 22,
                            height: 22,
                            decoration: BoxDecoration(
                              color: AppColors.p600.withValues(alpha: 0.3),
                              shape: BoxShape.circle,
                            ),
                            child: Center(
                              child: Text(
                                '${e.key + 1}',
                                style: const TextStyle(
                                    color: AppColors.p300,
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              e.value.text,
                              style: const TextStyle(
                                  color: AppColors.gray,
                                  fontSize: 12,
                                  height: 1.5),
                            ),
                          ),
                        ],
                      ),
                    );
                  })
                else
                  ...story.allChoicesMade.asMap().entries.map((e) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 22,
                            height: 22,
                            decoration: BoxDecoration(
                              color: AppColors.p600.withValues(alpha: 0.3),
                              shape: BoxShape.circle,
                            ),
                            child: Center(
                              child: Text(
                                '${e.key + 1}',
                                style: const TextStyle(
                                    color: AppColors.p300,
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700),
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              e.value,
                              style: const TextStyle(
                                  color: AppColors.gray,
                                  fontSize: 12,
                                  height: 1.5),
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
              ],
            ),
          ),
          const SizedBox(height: 80),
        ],
      ),
    );
  }
}
