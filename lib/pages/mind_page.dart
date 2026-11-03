import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/psych_traits.dart';
import '../widgets/custom_bottom_nav.dart';
import 'mind_detail_page.dart';
import 'story_page.dart';

/// 심리 탭: 분기형 동화에서 고른 선택지로 본 놀이 속 성향 (GET /api/psych/me)
/// 열 때마다 아직 분석 안 된 완료 동화를 서버가 최대 3개씩 분석해 줍니다.
class MindPage extends StatefulWidget {
  final String userName;

  const MindPage({
    super.key,
    required this.userName,
  });

  @override
  State<MindPage> createState() => _MindPageState();
}

class _MindPageState extends State<MindPage> {
  bool isLoading = true;
  String? errorMessage;
  Map<String, dynamic>? data;

  /// 꺾은선 그래프에서 보이는 성향 (범례를 눌러 켜고 끔)
  final Set<String> visibleTraits = kPsychTraits.map((t) => t.key).toSet();

  String get displayName => widget.userName.trim().isEmpty ? '사용자' : widget.userName;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      isLoading = data == null;
      errorMessage = null;
    });
    try {
      final response = await ApiClient.get('/api/psych/me');
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
      debugPrint('심리분석 조회 오류: $e');
      if (!mounted) return;
      setState(() {
        errorMessage = '마음 이야기를 불러오지 못했어요. 잠시 후 다시 해 주세요.';
        isLoading = false;
      });
    }
  }

  Future<void> openDetail(Map story) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => MindDetailPage(
          storyId: story['story_id'] as String,
          title: (story['title'] ?? '') as String,
        ),
      ),
    );
    // 상세에서 새로 분석했을 수 있으니 다시 불러옴
    if (mounted && story['analyzed'] != true) load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kMindBg,
      appBar: AppBar(
        backgroundColor: kMindBg,
        elevation: 0,
        foregroundColor: Colors.white,
        title: const Text('마음 이야기', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'mind',
        displayName: displayName,
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
            Text(
              '동화 속 선택들을 살펴보는 중이에요… 🔍',
              style: TextStyle(color: Colors.white70, fontSize: 16),
            ),
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
              Text(errorMessage ?? '마음 이야기를 불러오지 못했어요.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white70, fontSize: 16)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: load,
                style: ElevatedButton.styleFrom(
                    backgroundColor: kMindPurple, foregroundColor: Colors.white),
                child: const Text('다시 불러오기'),
              ),
            ],
          ),
        ),
      );
    }

    final d = data!;
    final stories = List<Map>.from(d['stories'] ?? []);
    final notice = (d['notice'] ?? '') as String;
    final message = (d['message'] ?? '') as String;

    return RefreshIndicator(
      color: kMindPurple,
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 40),
        children: [
          header(d),
          const SizedBox(height: 14),
          PsychNotice(text: notice),
          if (stories.isEmpty) ...[
            const SizedBox(height: 24),
            emptyState(message),
          ] else ...[
            if (message.isNotEmpty) ...[
              const SizedBox(height: 14),
              pendingBanner(message),
            ],
            const SizedBox(height: 22),
            radarCard(d),
            const SizedBox(height: 22),
            trendCard(d),
            const SizedBox(height: 28),
            const Text('동화별 마음 이야기',
                style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            const Text('카드를 누르면 선택 하나하나의 이야기를 볼 수 있어요.',
                style: TextStyle(color: Colors.white60, fontSize: 14)),
            const SizedBox(height: 14),
            ...stories.map(storyCard),
          ],
        ],
      ),
    );
  }

  // ----------------------------------------
  // 맨 위 인사
  // ----------------------------------------
  Widget header(Map d) {
    final count = (d['analyzed_count'] ?? 0) as int;
    final average = d['average'] as Map?;
    String line;
    if (average != null) {
      final top = kPsychTraits.reduce(
          (a, b) => traitScore(average, a.key) >= traitScore(average, b.key) ? a : b);
      line = '동화 $count편 속 선택에서\n${top.emoji} ${top.labelWithSubject} 가장 반짝였어요!';
    } else {
      line = '동화 속에서 고른 선택으로\n우리 아이의 마음을 들여다봐요.';
    }
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [kMindPurple, kMindPink]),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$displayName님의 마음 이야기 ✨',
              style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.w600)),
          const SizedBox(height: 10),
          Text(line,
              style: const TextStyle(
                  color: Colors.white, fontSize: 21, height: 1.45, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget pendingBanner(String message) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: kMindPurple.withOpacity(0.15),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: kMindPurple.withOpacity(0.4)),
      ),
      child: Row(
        children: [
          const Text('⏳', style: TextStyle(fontSize: 18)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message,
                style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.4)),
          ),
        ],
      ),
    );
  }

  Widget emptyState(String message) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 36),
      decoration: BoxDecoration(
        color: kMindCard,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        children: [
          const Text('📖', style: TextStyle(fontSize: 52)),
          const SizedBox(height: 14),
          Text(
            message.isEmpty ? '동화를 끝까지 만들면 분석해 줄게요!' : message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white, fontSize: 19, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          const Text(
            '이야기 속에서 고른 선택지들을 모아\n어떤 마음이 반짝였는지 알려 줄게요.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white60, fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 22),
          ElevatedButton.icon(
            onPressed: () => Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (_) => StoryPage(displayName: displayName)),
            ),
            icon: const Icon(Icons.auto_awesome),
            label: const Text('동화 만들러 가기'),
            style: ElevatedButton.styleFrom(
              backgroundColor: kMindPurple,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
          ),
        ],
      ),
    );
  }

  // ----------------------------------------
  // 평균 성향 (레이더)
  // ----------------------------------------
  Widget radarCard(Map d) {
    final average = d['average'] as Map?;
    final count = (d['analyzed_count'] ?? 0) as int;
    if (average == null) {
      return const MindCard(
        title: '지금까지의 평균 성향',
        child: Text('분석이 끝나면 여기에 그래프가 나타나요.',
            style: TextStyle(color: Colors.white60, fontSize: 15)),
      );
    }
    return MindCard(
      title: '지금까지의 평균 성향',
      subtitle: '끝까지 만든 동화 $count편을 모아 봤어요.',
      child: Column(
        children: [
          SizedBox(
            height: 280,
            child: RadarChart(
              RadarChartData(
                radarShape: RadarShape.polygon,
                tickCount: 4,
                ticksTextStyle: const TextStyle(color: Colors.transparent, fontSize: 1),
                radarBorderData: const BorderSide(color: Colors.white24),
                gridBorderData: const BorderSide(color: Colors.white10),
                tickBorderData: const BorderSide(color: Colors.white10),
                titlePositionPercentageOffset: 0.14,
                titleTextStyle: const TextStyle(
                    color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
                getTitle: (index, angle) {
                  final t = kPsychTraits[index];
                  return RadarChartTitle(text: '${t.emoji} ${t.shortLabel}');
                },
                dataSets: [
                  // 0~100 눈금을 고정하려고 넣는 보이지 않는 기준선
                  _scaleSet(0),
                  _scaleSet(100),
                  RadarDataSet(
                    fillColor: kMindPurple.withOpacity(0.35),
                    borderColor: const Color(0xFFC4B5FD),
                    borderWidth: 2,
                    entryRadius: 4,
                    dataEntries: kPsychTraits
                        .map((t) => RadarEntry(value: traitScore(average, t.key)))
                        .toList(),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          // 숫자로도 보기 (색만으로 구분하지 않게)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: kPsychTraits
                .map((t) => scoreChip(t, traitScore(average, t.key).round()))
                .toList(),
          ),
        ],
      ),
    );
  }

  RadarDataSet _scaleSet(double value) => RadarDataSet(
        fillColor: Colors.transparent,
        borderColor: Colors.transparent,
        borderWidth: 0,
        entryRadius: 0,
        dataEntries: List.generate(kPsychTraits.length, (_) => RadarEntry(value: value)),
      );

  Widget scoreChip(PsychTrait t, int score) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.06),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: t.color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text('${t.label} ',
              style: const TextStyle(color: Colors.white70, fontSize: 13)),
          Text('$score',
              style: const TextStyle(
                  color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  // ----------------------------------------
  // 최근 동화 성향 변화 (꺾은선)
  // ----------------------------------------
  Widget trendCard(Map d) {
    final trend = List<Map>.from(d['trend'] ?? []);
    if (trend.length < 2) {
      return const MindCard(
        title: '최근 동화 속 성향 변화',
        child: Text('동화를 2편 이상 끝까지 만들면\n마음이 어떻게 달라지는지 볼 수 있어요. 🌱',
            style: TextStyle(color: Colors.white60, fontSize: 15, height: 1.5)),
      );
    }
    final shown = kPsychTraits.where((t) => visibleTraits.contains(t.key)).toList();

    return MindCard(
      title: '최근 동화 속 성향 변화',
      subtitle: '최근 ${trend.length}편이에요. 왼쪽이 예전, 오른쪽이 가장 최근 동화예요.\n아래 이름을 눌러 선을 켜고 끌 수 있어요.',
      child: Column(
        children: [
          // 범례 (눌러서 켜고 끄기)
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: kPsychTraits.map((t) {
              final on = visibleTraits.contains(t.key);
              return GestureDetector(
                onTap: () => setState(() {
                  if (on && visibleTraits.length > 1) {
                    visibleTraits.remove(t.key);
                  } else {
                    visibleTraits.add(t.key);
                  }
                }),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: on ? Colors.white.withOpacity(0.08) : Colors.transparent,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: on ? Colors.white24 : Colors.white10),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 14,
                        height: 3,
                        color: on ? t.color : Colors.white24,
                      ),
                      const SizedBox(width: 6),
                      Text(t.label,
                          style: TextStyle(
                              color: on ? Colors.white : Colors.white38, fontSize: 13)),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 230,
            child: LineChart(
              LineChartData(
                minX: 0,
                maxX: (trend.length - 1).toDouble(),
                minY: 0,
                maxY: 100,
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  horizontalInterval: 25,
                  getDrawingHorizontalLine: (_) =>
                      const FlLine(color: Colors.white10, strokeWidth: 1),
                ),
                borderData: FlBorderData(show: false),
                titlesData: FlTitlesData(
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      interval: 25,
                      reservedSize: 32,
                      getTitlesWidget: (value, meta) => Text(
                        value.toInt().toString(),
                        style: const TextStyle(color: Colors.white38, fontSize: 11),
                      ),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      interval: 1,
                      reservedSize: 30,
                      getTitlesWidget: (value, meta) {
                        final i = value.toInt();
                        if (i < 0 || i >= trend.length || value != i.toDouble()) {
                          return const SizedBox.shrink();
                        }
                        final date = psychDateLabel(trend[i]['completed_at']);
                        return Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(date.isEmpty ? '${i + 1}' : date,
                              style: const TextStyle(color: Colors.white54, fontSize: 11)),
                        );
                      },
                    ),
                  ),
                ),
                lineTouchData: LineTouchData(
                  touchTooltipData: LineTouchTooltipData(
                    getTooltipColor: (_) => const Color(0xFF2A1450),
                    fitInsideHorizontally: true,
                    fitInsideVertically: true,
                    getTooltipItems: (spots) => spots.map((s) {
                      final t = shown[s.barIndex];
                      final isFirst = s == spots.first;
                      final title = trend[s.x.toInt()]['title'] ?? '';
                      return LineTooltipItem(
                        isFirst ? '$title\n' : '',
                        const TextStyle(
                            color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                        children: [
                          TextSpan(
                            text: '${t.emoji} ${t.shortLabel} ${s.y.round()}',
                            style: const TextStyle(
                                color: Colors.white70, fontSize: 12, fontWeight: FontWeight.normal),
                          ),
                        ],
                      );
                    }).toList(),
                  ),
                ),
                lineBarsData: shown
                    .map((t) => LineChartBarData(
                          spots: List.generate(
                            trend.length,
                            (i) => FlSpot(i.toDouble(), traitScore(trend[i]['traits'] as Map?, t.key)),
                          ),
                          color: t.color,
                          barWidth: 2.5,
                          isCurved: false,
                          dotData: FlDotData(
                            show: true,
                            getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
                              radius: 4,
                              color: t.color,
                              strokeWidth: 2,
                              strokeColor: kMindCard,
                            ),
                          ),
                        ))
                    .toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ----------------------------------------
  // 동화별 카드
  // ----------------------------------------
  Widget storyCard(Map story) {
    final analyzed = story['analyzed'] == true;
    final top = analyzed ? psychTraitOf(story['top_trait'] as String?) : null;
    final date = psychDateLabel(story['completed_at']);
    final choiceCount = story['choice_count'] ?? 0;
    final summary = (story['summary'] ?? '') as String;

    return GestureDetector(
      onTap: () => openDetail(story),
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: kMindCard,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: Colors.white10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    story['title'] ?? '제목 없는 이야기',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                const Icon(Icons.chevron_right, color: Colors.white38),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              [if (date.isNotEmpty) date, if ((story['genre'] ?? '') != '') story['genre'], '선택 $choiceCount번']
                  .join(' · '),
              style: const TextStyle(color: Colors.white54, fontSize: 13),
            ),
            const SizedBox(height: 12),
            if (top != null) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: top.color.withOpacity(0.18),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: top.color.withOpacity(0.6)),
                ),
                child: Text('${top.emoji} ${top.labelWithSubject} 돋보였어요',
                    style: const TextStyle(
                        color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
              ),
              if (summary.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(summary,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.5)),
              ],
            ] else
              const Text('⏳ 아직 살펴보는 중이에요. 눌러서 바로 볼 수도 있어요.',
                  style: TextStyle(color: Colors.white60, fontSize: 14)),
          ],
        ),
      ),
    );
  }
}
