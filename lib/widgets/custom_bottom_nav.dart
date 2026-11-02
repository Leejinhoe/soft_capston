import 'package:flutter/material.dart';

import '../pages/home_page.dart';
import '../pages/story_page.dart';
import '../pages/vocabulary_page.dart';
import '../pages/mind_page.dart';
import '../pages/board_page.dart';
import '../pages/profile_page.dart';

class CustomBottomNav extends StatelessWidget {
  final String currentPage;
  final String displayName;
  final String userId;

  const CustomBottomNav({
    super.key,
    required this.currentPage,
    required this.displayName,
    this.userId = 'user123',
  });

  void movePage(
      BuildContext context,
      Widget page,
      ) {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => page,
      ),
    );
  }

  Widget navItem({
    required BuildContext context,
    required IconData icon,
    required String label,
    required Widget page,
    required bool selected,
  }) {
    return GestureDetector(
      onTap: () => movePage(
        context,
        page,
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: 10,
          vertical: 6,
        ),
        decoration: BoxDecoration(
          color: selected
              ? Colors.white.withOpacity(0.08)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              color: selected ? Colors.white : Colors.white70,
              size: 23,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                color: selected ? Colors.white : Colors.white70,
                fontSize: 11,
                fontWeight:
                selected ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 86,
      decoration: const BoxDecoration(
        color: Color(0xFF140028),
        border: Border(
          top: BorderSide(
            color: Colors.white10,
          ),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
// 홈
          navItem(
            context: context,
            icon: Icons.home,
            label: '홈',
            page: HomePage(
              userId: userId,
              displayName: displayName,
            ),
            selected: currentPage == 'home',
          ),
// 동화 생성
          navItem(
            context: context,
            icon: Icons.auto_awesome,
            label: '동화',
            page: StoryPage(
              userId: userId,
              displayName: displayName,
            ),
            selected: currentPage == 'story',
          ),
// 커뮤니티
          navItem(
            context: context,
            icon: Icons.forum,
            label: '커뮤니티',
            page: BoardPage(
              userId: userId,
              displayName: displayName,
            ),
            selected: currentPage == 'board',
          ),
// 단어장
          navItem(
            context: context,
            icon: Icons.menu_book,
            label: '단어장',
            page: VocabularyPage(
              userId: userId,
              displayName: displayName,
            ),
            selected: currentPage == 'vocabulary',
          ),
// 심리 분석
          navItem(
            context: context,
            icon: Icons.psychology,
            label: '심리',
            page: MindPage(
              userId: userId,
              userName: displayName,
            ),
            selected: currentPage == 'mind',
          ),
// 프로필
          navItem(
            context: context,
            icon: Icons.person,
            label: '프로필',
            page: ProfilePage(
              userId: userId,
              userName: displayName,
            ),
            selected: currentPage == 'profile',
          ),
        ],
      ),
    );
  }
}