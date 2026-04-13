import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:percent_indicator/percent_indicator.dart';
import '../main.dart';
import '../models/app_state.dart';
import '../models/story_model.dart';

class PsychScreen extends StatefulWidget {
  const PsychScreen({super.key});

  @override
  State<PsychScreen> createState() => _PsychScreenState();
}

class _PsychScreenState extends State<PsychScreen> {
  bool _analyzed = false;

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final story = state.currentStory;
    final psych = state.psychResult;

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: const Text('🧠 성격 분석'),
        backgroundColor: AppColors.bg,
        leading: Navigator.canPop(context)
            ? IconButton(
                icon: const Icon(Icons.arrow_back_ios_rounded),
                onPressed: () => Navigator.pop(context),
              )
            : null,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.5),
            radius: 0.9,
            colors: [Color(0xFF1a0530), Color(0xFF06041A)],
          ),
        ),
        child: SafeArea(
          child: _buildBody(context, state, story, psych),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, AppState state,
      StorySession? story, PsychResult? psych) {
    if (story == null || story.allChoicesMade.isEmpty) {
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
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(40),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('📖', style: TextStyle(fontSize: 56)),
            const SizedBox(height: 20),
            const Text(
              '아직 분석할 내용이 없어요',
              style: TextStyle(
                  color: Colors.white, fontSize: 18,
                  fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            const Text(
              '동화를 읽으면서 선택을 해보면\n내 성격을 알 수 있어요!',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.gray, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnalyzePrompt(
      BuildContext context, AppState state, StorySession story) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              children: [
                const Text('🔮', style: TextStyle(fontSize: 60)),
                const SizedBox(height: 16),
                const Text(
                  '내 성격 알아보기',
                  style: TextStyle(
                      color: Colors.white, fontSize: 20,
                      fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(
                  '${story.allChoicesMade.length}번의 선택을 분석해서\n나의 성격 유형을 알려드릴게요',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: AppColors.gray, fontSize: 13),
                ),
                const SizedBox(height: 8),
                // 선택 목록
                ...story.allChoicesMade.take(5).map((c) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      const Icon(Icons.check_circle_rounded,
                          color: AppColors.teal, size: 14),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(c,
                            style: const TextStyle(
                                color: AppColors.gray, fontSize: 11)),
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
                      backgroundColor: AppColors.p600,
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
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          // 타입 카드
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF2D1563), Color(0xFF1E0E4A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: AppColors.border),
              boxShadow: [
                BoxShadow(
                  color: AppColors.p600.withOpacity(0.3),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
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
                  style: TextStyle(
                      color: AppColors.p300.withOpacity(0.8),
                      fontSize: 13,
                      height: 1.6),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // 특성 분석
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '특성 분석',
                  style: TextStyle(
                      color: Colors.white, fontSize: 15,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                ...psych.traits.entries.map((e) {
                  final color =
                      traitColors[e.key] ?? AppColors.p400;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment:
                              MainAxisAlignment.spaceBetween,
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
                          backgroundColor:
                              color.withOpacity(0.15),
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
              color: AppColors.card,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '나의 선택 이야기',
                  style: TextStyle(
                      color: Colors.white, fontSize: 15,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
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
                            color: AppColors.p600.withOpacity(0.3),
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
