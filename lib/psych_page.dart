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
    final psych = story == null ? null : state.psychResultFor(story);

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

    if (!state.canAnalyzeStory(story)) {
      return _buildEndingRequiredState(story);
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
              '고른 선택과 감정 점수를 AI가 분석하고 있어요...',
              style: TextStyle(color: AppColors.p300, fontSize: 14),
            ),
          ],
        ),
      );
    }

    if (psych == null) {
      return _buildAnalyzePrompt(context, state, story);
    }

    return _buildResult(psych, story, state);
  }

  Widget _buildEndingRequiredState(StorySession story) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPageTitle(),
          const Spacer(),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(28),
            decoration: BoxDecoration(
              color: const Color(0xFF140028),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              children: [
                const Icon(
                  Icons.auto_stories_rounded,
                  size: 54,
                  color: AppColors.p300,
                ),
                const SizedBox(height: 18),
                const Text(
                  '엔딩을 본 뒤 분석할 수 있어요',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  '현재 ${story.allChoicesMade.length}번 선택했어요.\n'
                  '동화의 마지막 선택까지 마치면 선택별 감정 점수를 AI에게 보내 분석 글을 만들어요.',
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
          const Spacer(),
          const SizedBox(height: 100),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 10),
          const Text(
            'AI 선택·감정 분석',
            style: TextStyle(
              color: Colors.white,
              fontSize: 34,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            '엔딩까지 고른 선택과 감정 점수를 AI가 함께 읽어요',
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
          'AI 선택·감정 분석',
          style: TextStyle(
            color: Colors.white,
            fontSize: 34,
            fontWeight: FontWeight.bold,
          ),
        ),
        SizedBox(height: 10),
        Text(
          '완결된 동화의 선택과 감정 점수로 만든 분석을 확인해보세요',
          style: TextStyle(color: Colors.white70, fontSize: 16),
        ),
      ],
    );
  }

  Widget _buildAnalyzePrompt(
      BuildContext context, AppState state, StorySession story) {
    final history = story.choiceEmotionHistory;
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
                  '${history.length}번의 선택과 각 선택에서 감지된 감정 점수를 바탕으로\n나의 이야기 탐험 성향을 분석해요.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
                const SizedBox(height: 18),
                ...history.map(_buildChoiceEmotionPreview),
                const SizedBox(height: 8),
                const Text(
                  '이 결과는 동화 속 선택을 바탕으로 한 놀이형 참고 분석이며, 의학적·심리학적 진단이 아니에요.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: AppColors.gray,
                    fontSize: 10,
                    height: 1.5,
                  ),
                ),
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
                      '🧠 선택 감정으로 AI 분석',
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
          const SizedBox(height: 80),
        ],
      ),
    );
  }

  Widget _buildChoiceEmotionPreview(StoryChoiceEmotion record) {
    final emotion = record.emotion;
    final top = emotion?.topEmotions.take(3).toList() ?? const [];
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
                const SizedBox(height: 6),
                Text(
                  top.isEmpty
                      ? '감정 점수 없음'
                      : top.map((item) {
                          final label = item.labelDisplay.isNotEmpty
                              ? item.labelDisplay
                              : item.label;
                          return '$label ${(item.score * 100).round()}%';
                        }).join(' · '),
                  style: const TextStyle(
                    color: AppColors.p300,
                    fontSize: 10,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResult(
    PsychResult psych,
    StorySession story,
    AppState state,
  ) {
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
          if (state.psychAnalysisNotice != null) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF59E0B).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: const Color(0xFFF59E0B).withValues(alpha: 0.35),
                ),
              ),
              child: Text(
                state.psychAnalysisNotice!,
                style: const TextStyle(
                  color: Color(0xFFFCD34D),
                  fontSize: 11,
                  height: 1.5,
                ),
              ),
            ),
            const SizedBox(height: 14),
          ],
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
                const Text(
                  'AI 감정 분석 글',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
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

          if (psych.dominantEmotions.isNotEmpty) ...[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: psych.dominantEmotions
                  .map(
                    (emotion) => Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 7,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.p500.withValues(alpha: 0.18),
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(
                          color: AppColors.p400.withValues(alpha: 0.35),
                        ),
                      ),
                      child: Text(
                        emotion,
                        style: const TextStyle(
                          color: AppColors.p300,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
            const SizedBox(height: 18),
          ],

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
                const Text(
                  '선택과 감정 근거',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                ...story.choiceEmotionHistory.map(_buildChoiceEmotionPreview),
              ],
            ),
          ),
          if (psych.choiceInsights.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
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
                    '선택별 AI 해석',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  ...psych.choiceInsights.asMap().entries.map(
                        (entry) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Text(
                            '${entry.key + 1}. ${entry.value}',
                            style: const TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                              height: 1.55,
                            ),
                          ),
                        ),
                      ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 80),
        ],
      ),
    );
  }
}
