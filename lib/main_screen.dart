import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'app_theme.dart';
import 'community_page.dart';
import 'create_page.dart';
import 'models/app_state.dart';
import 'notice_page.dart';
import 'profile_page.dart';
import 'psych_page.dart';
import 'vocab_page.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  late final List<Widget?> _pages;

  @override
  void initState() {
    super.initState();
    _pages = List<Widget?>.filled(6, null);
    _pages[0] = _createPage(0);
  }

  Widget _createPage(int index) => switch (index) {
    0 => HomePage(onSelectTab: _selectTab),
    1 => const CreatePage(),
    2 => const CommunityPage(),
    3 => const VocabPage(),
    4 => PsychPage(onBack: () => _selectTab(0)),
    5 => const ProfilePage(),
    _ => const SizedBox.shrink(),
  };

  void _selectTab(int index) {
    if (index < 0 || index >= _pages.length) return;
    context.read<AppState>().selectMainTab(index);
  }

  @override
  Widget build(BuildContext context) {
    final selectedIndex = context.select<AppState, int>(
      (state) => state.selectedMainTab,
    );
    _pages[selectedIndex] ??= _createPage(selectedIndex);
    return Scaffold(
      backgroundColor: AppColors.pageBackground,
      body: IndexedStack(
        index: selectedIndex,
        children: [for (final page in _pages) page ?? const SizedBox.shrink()],
      ),
      bottomNavigationBar: selectedIndex == 0
          ? null
          : HyeonlimBottomNav(
              selectedIndex: selectedIndex,
              onTap: _selectTab,
            ),
    );
  }
}

class HyeonlimBottomNav extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onTap;

  const HyeonlimBottomNav({
    super.key,
    required this.selectedIndex,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    const items = [
      _NavItem(Icons.home, '홈'),
      _NavItem(Icons.auto_awesome, '동화'),
      _NavItem(Icons.forum, '커뮤니티'),
      _NavItem(Icons.menu_book, '단어장'),
      _NavItem(Icons.psychology, '심리'),
      _NavItem(Icons.person, '프로필'),
    ];

    return Container(
      height: 86,
      decoration: const BoxDecoration(
        color: AppColors.pageSurface,
        border: Border(top: BorderSide(color: Colors.white10)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: List.generate(items.length, (index) {
            final item = items[index];
            final selected = selectedIndex == index;
            return GestureDetector(
              onTap: () => onTap(index),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: selected
                      ? Colors.white.withValues(alpha: 0.08)
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      item.icon,
                      color: selected ? Colors.white : Colors.white70,
                      size: 23,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.label,
                      style: TextStyle(
                        color: selected ? Colors.white : Colors.white70,
                        fontSize: 11,
                        fontWeight: selected
                            ? FontWeight.bold
                            : FontWeight.normal,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}

class _NavItem {
  final IconData icon;
  final String label;

  const _NavItem(this.icon, this.label);
}

class HomePage extends StatefulWidget {
  final ValueChanged<int> onSelectTab;

  const HomePage({super.key, required this.onSelectTab});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  Widget _buildMenuCard({
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
          gradient: LinearGradient(colors: colors),
          borderRadius: BorderRadius.circular(28),
          boxShadow: [
            BoxShadow(
              color: colors.first.withValues(alpha: 0.3),
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
                color: Colors.white.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(icon, color: Colors.white, size: 30),
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
                    style: const TextStyle(color: Colors.white70, fontSize: 14),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white70),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final displayName = context.select<AppState, String>(
      (state) => state.currentDisplayName,
    );
    final user = displayName.trim().isEmpty ? '사용자' : displayName;

    return Scaffold(
      backgroundColor: AppColors.pageBackground,
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
                  Row(
                    children: [
                      IconButton(
                        tooltip: '공지사항',
                        onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute(builder: (_) => const NoticePage()),
                        ),
                        icon: const Icon(
                          Icons.notifications_none_rounded,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(width: 4),
                      GestureDetector(
                        onTap: () => widget.onSelectTab(5),
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.pageSurface,
                            borderRadius: BorderRadius.circular(18),
                            border: Border.all(color: Colors.white10),
                          ),
                          child: const Icon(Icons.person, color: Colors.white),
                        ),
                      ),
                    ],
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
              _buildMenuCard(
                icon: Icons.auto_awesome,
                title: '동화 생성',
                subtitle: 'AI가 새로운 이야기를 만들어줘요',
                colors: const [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                onTap: () => widget.onSelectTab(1),
              ),
              _buildMenuCard(
                icon: Icons.forum,
                title: '커뮤니티',
                subtitle: '다른 친구들의 동화를 구경해요',
                colors: const [Color(0xFF10B981), Color(0xFF34D399)],
                onTap: () => widget.onSelectTab(2),
              ),
              _buildMenuCard(
                icon: Icons.menu_book,
                title: '단어장',
                subtitle: '새로운 단어와 표현을 학습해요',
                colors: const [Color(0xFF3B82F6), Color(0xFF06B6D4)],
                onTap: () => widget.onSelectTab(3),
              ),
              _buildMenuCard(
                icon: Icons.psychology,
                title: '심리 분석',
                subtitle: 'AI가 관심사와 감정을 분석해줘요',
                colors: const [Color(0xFFF59E0B), Color(0xFFEF4444)],
                onTap: () => widget.onSelectTab(4),
              ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }
}
