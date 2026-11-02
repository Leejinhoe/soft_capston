import 'package:flutter/material.dart';

import 'story_page.dart';
import 'vocabulary_page.dart';
import 'mind_page.dart';
import 'board_page.dart';
import 'profile_page.dart';

class HomePage extends StatelessWidget {
  final String displayName;

  const HomePage({
    super.key,
    required this.displayName,
  });

  void movePage(BuildContext context, Widget page) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => page,
      ),
    );
  }

  Widget buildMenuCard({
    required IconData icon,
    required String title,
    required String subtitle,
    required List<Color> colors,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 18),
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: colors,
          ),
          borderRadius: BorderRadius.circular(28),
          boxShadow: [
            BoxShadow(
              color: colors.first.withOpacity(0.3),
              blurRadius: 18,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 62,
              height: 62,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.15),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(
                icon,
                color: Colors.white,
                size: 30,
              ),
            ),
            const SizedBox(width: 18),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.arrow_forward_ios,
              color: Colors.white70,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user =
    displayName.trim().isEmpty ? '사용자' : displayName;

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 10),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '✨ AI Fairy Tale',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 34,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  GestureDetector(
                    onTap: () {
                      movePage(
                        context,
                        ProfilePage(
                          userName: user,
                        ),
                      );
                    },
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF140028),
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(
                          color: Colors.white10,
                        ),
                      ),
                      child: const Icon(
                        Icons.person,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                '$user님만의\n특별한 이야기를 만들어보세요.',
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 18,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 36),
// 동화 생성
              buildMenuCard(
                icon: Icons.auto_awesome,
                title: '동화 생성',
                subtitle: 'AI가 새로운 이야기를 만들어줘요',
                colors: const [
                  Color(0xFF8B5CF6),
                  Color(0xFFEC4899),
                ],
                onTap: () {
                  movePage(
                    context,
                    StoryPage(
                      displayName: user,
                    ),
                  );
                },
              ),
// 커뮤니티
              buildMenuCard(
                icon: Icons.forum,
                title: '커뮤니티',
                subtitle: '다른 친구들의 동화를 구경해요',
                colors: const [
                  Color(0xFF10B981),
                  Color(0xFF34D399),
                ],
                onTap: () {
                  movePage(
                    context,
                    BoardPage(
                      displayName: user,
                    ),
                  );
                },
              ),
// 단어장
              buildMenuCard(
                icon: Icons.menu_book,
                title: '단어장',
                subtitle: '새로운 단어와 표현을 학습해요',
                colors: const [
                  Color(0xFF3B82F6),
                  Color(0xFF06B6D4),
                ],
                onTap: () {
                  movePage(
                    context,
                    VocabularyPage(
                      displayName: user,
                    ),
                  );
                },
              ),
// 심리 분석
              buildMenuCard(
                icon: Icons.psychology,
                title: '심리 분석',
                subtitle: 'AI가 관심사와 감정을 분석해줘요',
                colors: const [
                  Color(0xFFF59E0B),
                  Color(0xFFEF4444),
                ],
                onTap: () {
                  movePage(
                    context,
                    MindPage(
                      userName: user,
                    ),
                  );
                },
              ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }
}