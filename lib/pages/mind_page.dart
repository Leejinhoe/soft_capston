import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../widgets/custom_bottom_nav.dart';

class MindPage extends StatefulWidget {
  final String userId;
  final String userName;

  const MindPage({
    super.key,
    this.userId = 'user123',
    required this.userName,
  });

  @override
  State<MindPage> createState() => _MindPageState();
}

class _MindPageState extends State<MindPage> {
  final List<Map<String, dynamic>> emotions = [
    {
      'title': '행복',
      'value': 82,
      'description': '긍정적인 감정이 높게 나타났어요.',
    },
    {
      'title': '기대',
      'value': 76,
      'description': '새로운 경험을 기대하고 있어요.',
    },
    {
      'title': '불안',
      'value': 38,
      'description': '약간의 걱정이 존재해요.',
    },
    {
      'title': '슬픔',
      'value': 25,
      'description': '부정 감정은 낮은 편이에요.',
    },
    {
      'title': '분노',
      'value': 12,
      'description': '감정 조절이 잘 되고 있어요.',
    },
  ];

  final List<Map<String, dynamic>> interests = [
    {'title': '과학', 'value': 85},
    {'title': '공학', 'value': 72},
    {'title': '사회', 'value': 63},
    {'title': '인문', 'value': 91},
    {'title': '보건', 'value': 45},
    {'title': '봉사', 'value': 77},
  ];

  @override
  Widget build(BuildContext context) {
    final displayName =
    widget.userName.trim().isEmpty ? '사용자' : widget.userName;

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF070018),
        elevation: 0,
        foregroundColor: Colors.white,
        title: const Text(
          'AI 심리 분석',
          style: TextStyle(
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'mind',
        userId: widget.userId,
        displayName: displayName,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [
                    Color(0xFF8B5CF6),
                    Color(0xFFEC4899),
                  ],
                ),
                borderRadius: BorderRadius.circular(24),
              ),
              child: Text(
                '$displayName님의 심리 분석 결과예요 ✨\n'
                    '과학과 인문 분야의 관심도가 높으며 '
                    '긍정적인 감정 비중이 높게 나타났습니다.\n'
                    '새로운 아이디어를 탐색하고 '
                    '창의적인 문제 해결에 강점을 보이는 성향으로 분석됩니다.',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 22,
                  height: 1.6,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(height: 30),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF140028),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: Colors.white10,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '성향 레이더 분석',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    height: 350,
                    child: RadarChart(
                      RadarChartData(
                        radarShape: RadarShape.polygon,
                        tickCount: 5,
                        ticksTextStyle: const TextStyle(
                          color: Colors.white38,
                          fontSize: 10,
                        ),
                        radarBorderData: const BorderSide(
                          color: Colors.white24,
                        ),
                        gridBorderData: const BorderSide(
                          color: Colors.white10,
                        ),
                        titleTextStyle: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.bold,
                        ),
                        getTitle: (index, angle) {
                          return RadarChartTitle(
                            text: emotions[index]['title'],
                          );
                        },
                        dataSets: [
                          RadarDataSet(
                            fillColor: Colors.purple.withOpacity(0.4),
                            borderColor: Colors.purpleAccent,
                            entryRadius: 3,
                            borderWidth: 3,
                            dataEntries: emotions.map((e) {
                              return RadarEntry(
                                value: e['value'].toDouble(),
                              );
                            }).toList(),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 30),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF140028),
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: Colors.white10,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '성향 상세 분석',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    height: 320,
                    child: BarChart(
                      BarChartData(
                        alignment: BarChartAlignment.spaceAround,
                        maxY: 100,
                        titlesData: FlTitlesData(
                          leftTitles: const AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                            ),
                          ),
                          bottomTitles: AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: true,
                              getTitlesWidget: (value, meta) {
                                return Padding(
                                  padding: const EdgeInsets.only(
                                    top: 8,
                                  ),
                                  child: Text(
                                    emotions[value.toInt()]['title'],
                                    style: const TextStyle(
                                      color: Colors.white70,
                                      fontSize: 11,
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                          topTitles: const AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: false,
                            ),
                          ),
                          rightTitles: const AxisTitles(
                            sideTitles: SideTitles(
                              showTitles: false,
                            ),
                          ),
                        ),
                        borderData: FlBorderData(
                          show: false,
                        ),
                        gridData: const FlGridData(
                          show: true,
                        ),
                        barGroups: List.generate(
                          emotions.length,
                              (index) {
                            return BarChartGroupData(
                              x: index,
                              barRods: [
                                BarChartRodData(
                                  toY: emotions[index]['value'].toDouble(),
                                  width: 18,
                                  borderRadius: BorderRadius.circular(6),
                                  gradient: const LinearGradient(
                                    colors: [
                                      Color(0xFF8B5CF6),
                                      Color(0xFFEC4899),
                                    ],
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 30),
            const Text(
              '상세 성향 설명',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 20),
            ...emotions.map((stat) {
              return Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: const Color(0xFF140028),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: Colors.white10,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          stat['title'],
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          '${stat['value']}점',
                          style: const TextStyle(
                            color: Colors.purpleAccent,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      stat['description'],
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 15,
                        height: 1.6,
                      ),
                    ),
                  ],
                ),
              );
            }).toList(),
            const SizedBox(height: 100),
          ],
        ),
      ),
    );
  }
}