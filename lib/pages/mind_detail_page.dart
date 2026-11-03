import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/psych_traits.dart';

/// 동화 하나의 마음 이야기: 성향 막대그래프, 선택별 해석, 요약, 대화 질문
/// (GET /api/psych/stories/{id}, 아직 분석 전이면 서버가 이때 분석)
class MindDetailPage extends StatefulWidget {
  final String storyId;
  final String title;

  const MindDetailPage({super.key, required this.storyId, required this.title});

  @override
  State<MindDetailPage> createState() => _MindDetailPageState();
}

class _MindDetailPageState extends State<MindDetailPage> {
  bool isLoading = true;
  String? errorMessage;
  Map<String, dynamic>? data;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      isLoading = true;
      errorMessage = null;
    });
    try {
      final response = await ApiClient.get('/api/psych/stories/${widget.storyId}');
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() {
          data = Map<String, dynamic>.from(ApiClient.decode(response) ?? {});
          isLoading = false;
        });
      } else {
        setState(() {
          errorMessage = ApiClient.errorMessage(response, '마음 이야기를 불러오지 못했어요.');
          isLoading = false;
        });
      }
    } catch (e) {
      debugPrint('심리분석 상세 오류: $e');
      if (!mounted) return;
      setState(() {
        errorMessage = '마음 이야기를 불러오지 못했어요. 잠시 후 다시 해 주세요.';
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kMindBg,
      appBar: AppBar(
        backgroundColor: kMindBg,
        elevation: 0,
        foregroundColor: Colors.white,
        title: Text(
          (data?['title'] ?? widget.title).toString(),
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: buildBody(),
    );
  }

  Widget buildBody() {
    if (isLoading) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: kMindPurple),
            SizedBox(height: 18),
            Text('선택 하나하나를 살펴보는 중이에요… 🔍',
                style: TextStyle(color: Colors.white70, fontSize: 16)),
          ],
        ),
      );
    }
    if (data == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('🌙', style: TextStyle(fontSize: 44)),
              const SizedBox(height: 12),
              Text(errorMessage ?? '마음 이야기를 불러오지 못했어요.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.5)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: load,
                style: ElevatedButton.styleFrom(
                    backgroundColor: kMindPurple, foregroundColor: Colors.white),
                child: const Text('다시 해 보기'),
              ),
            ],
          ),
        ),
      );
    }

    final d = data!;
    final traits = d['traits'] as Map?;
    final insights = List<Map>.from(d['insights'] ?? []);
    final questions = List<String>.from(d['questions'] ?? []);
    final date = psychDateLabel(d['completed_at']);
    final genre = (d['genre'] ?? '') as String;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
      children: [
        if (date.isNotEmpty || genre.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Text([if (date.isNotEmpty) '$date에 완성한 동화', if (genre.isNotEmpty) genre].join(' · '),
                style: const TextStyle(color: Colors.white54, fontSize: 14)),
          ),
        summaryCard((d['summary'] ?? '') as String),
        const SizedBox(height: 20),
        barCard(traits),
        const SizedBox(height: 20),
        insightCard(insights),
        const SizedBox(height: 20),
        questionCard(questions),
        const SizedBox(height: 20),
        PsychNotice(text: (d['notice'] ?? '') as String),
      ],
    );
  }

  // ----------------------------------------
  // 요약
  // ----------------------------------------
  Widget summaryCard(String summary) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [kMindPurple.withOpacity(0.35), kMindPink.withOpacity(0.25)],
        ),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: kMindPurple.withOpacity(0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('✨ 이 동화 속 우리 아이',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Text(summary,
              style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.65)),
        ],
      ),
    );
  }

  // ----------------------------------------
  // 성향 막대그래프
  // ----------------------------------------
  Widget barCard(Map? traits) {
    return MindCard(
      title: '이 동화의 성향',
      subtitle: '이 이야기 속 선택에서 드러난 정도예요. (0~100)',
      child: SizedBox(
        height: 240,
        child: BarChart(
          BarChartData(
            alignment: BarChartAlignment.spaceAround,
            minY: 0,
            maxY: 100,
            borderData: FlBorderData(show: false),
            gridData: FlGridData(
              show: true,
              drawVerticalLine: false,
              horizontalInterval: 25,
              getDrawingHorizontalLine: (_) => const FlLine(color: Colors.white10, strokeWidth: 1),
            ),
            titlesData: FlTitlesData(
              topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 52,
                  getTitlesWidget: (value, meta) {
                    final t = kPsychTraits[value.toInt()];
                    return Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Column(
                        children: [
                          Text('${t.emoji} ${t.shortLabel}',
                              style: const TextStyle(color: Colors.white70, fontSize: 12)),
                          const SizedBox(height: 2),
                          Text('${traitScore(traits, t.key).round()}',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
            barTouchData: BarTouchData(
              touchTooltipData: BarTouchTooltipData(
                getTooltipColor: (_) => const Color(0xFF2A1450),
                fitInsideHorizontally: true,
                getTooltipItem: (group, groupIndex, rod, rodIndex) {
                  final t = kPsychTraits[group.x];
                  return BarTooltipItem(
                    '${t.label} ${rod.toY.round()}점',
                    const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
                  );
                },
              ),
            ),
            barGroups: List.generate(kPsychTraits.length, (i) {
              final t = kPsychTraits[i];
              return BarChartGroupData(
                x: i,
                barRods: [
                  BarChartRodData(
                    toY: traitScore(traits, t.key),
                    width: 22,
                    color: t.color,
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                    backDrawRodData: BackgroundBarChartRodData(
                      show: true,
                      toY: 100,
                      color: Colors.white.withOpacity(0.04),
                    ),
                  ),
                ],
              );
            }),
          ),
        ),
      ),
    );
  }

  // ----------------------------------------
  // 선택별 해석
  // ----------------------------------------
  Widget insightCard(List<Map> insights) {
    return MindCard(
      title: '선택 하나하나의 이야기',
      subtitle: '어떤 갈림길에서 무엇을 골랐는지 함께 돌아봐요.',
      child: Column(
        children: [
          for (var i = 0; i < insights.length; i++) insightItem(i + 1, insights[i], i == insights.length - 1),
        ],
      ),
    );
  }

  Widget insightItem(int number, Map item, bool isLast) {
    final choice = (item['choice'] ?? '') as String;
    final options = List<String>.from(item['options'] ?? []).where((o) => o != choice).toList();
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 왼쪽 번호 + 이어지는 선
          SizedBox(
            width: 32,
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  alignment: Alignment.center,
                  decoration: const BoxDecoration(color: kMindPurple, shape: BoxShape.circle),
                  child: Text('$number',
                      style: const TextStyle(
                          color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
                ),
                if (!isLast)
                  Expanded(child: Container(width: 2, color: kMindPurple.withOpacity(0.3))),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 22),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('장면 ${item['scene']}에서 고른 것',
                      style: const TextStyle(color: Colors.white54, fontSize: 12)),
                  const SizedBox(height: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: kMindPurple.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: kMindPurple.withOpacity(0.6)),
                    ),
                    child: Text('👉 $choice',
                        style: const TextStyle(
                            color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
                  ),
                  if (options.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text('다른 길: ${options.join(' / ')}',
                        style: const TextStyle(color: Colors.white38, fontSize: 12, height: 1.4)),
                  ],
                  const SizedBox(height: 8),
                  Text(item['insight'] ?? '',
                      style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.55)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ----------------------------------------
  // 보호자 대화 질문
  // ----------------------------------------
  Widget questionCard(List<String> questions) {
    return MindCard(
      title: '아이와 이렇게 이야기 나눠 보세요',
      subtitle: '정답은 없어요. 아이의 생각을 귀 기울여 들어 주세요.',
      child: Column(
        children: questions
            .map((q) => Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.06),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('💬', style: TextStyle(fontSize: 18)),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(q,
                            style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.5)),
                      ),
                    ],
                  ),
                ))
            .toList(),
      ),
    );
  }
}
