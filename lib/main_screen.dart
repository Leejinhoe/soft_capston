import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'community_page.dart';
import 'create_page.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'notice_page.dart';
import 'profile_page.dart';
import 'psych_page.dart';
import 'story_page.dart';
import 'vocab_page.dart';

class FeaturedStory {
  final String emoji;
  final String title;
  final String tag;

  const FeaturedStory({
    required this.emoji,
    required this.title,
    required this.tag,
  });
}

const List<FeaturedStory> _featuredStories = [
  FeaturedStory(emoji: '🐉', title: '용감한 꼬마 드래곤', tag: '모험'),
  FeaturedStory(emoji: '🚀', title: '우주로 간 토끼', tag: 'SF'),
  FeaturedStory(emoji: '🦊', title: '여우 마법사의 비밀', tag: '판타지'),
  FeaturedStory(emoji: '👑', title: '황금 사과를 찾아서', tag: '전래동화'),
  FeaturedStory(emoji: '🧜‍♀️', title: '바다 탐험대', tag: '모험'),
];

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;

  void _selectTab(int index) => setState(() => _selectedIndex = index);

  @override
  Widget build(BuildContext context) {
    final displayName = context.watch<AppState>().currentDisplayName;
    final pages = [
      HomePage(displayName: displayName, onSelectTab: _selectTab),
      const CreatePage(),
      const CommunityPage(),
      const VocabPage(),
      const PsychPage(),
      const ProfilePage(),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      body: IndexedStack(index: _selectedIndex, children: pages),
      bottomNavigationBar: HyeonlimBottomNav(
        selectedIndex: _selectedIndex,
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
        color: Color(0xFF140028),
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
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
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
                        fontSize: 10,
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
  final String displayName;
  final ValueChanged<int> onSelectTab;

  const HomePage({
    super.key,
    required this.displayName,
    required this.onSelectTab,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final ScrollController _recommendScrollController = ScrollController();

  @override
  void dispose() {
    _recommendScrollController.dispose();
    super.dispose();
  }

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

  Widget _buildFeaturedStoryCard(FeaturedStory story) {
    return Container(
      width: 140,
      margin: const EdgeInsets.only(right: 16),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 100,
            width: double.infinity,
            decoration: const BoxDecoration(
              color: Color(0xFF0D0520),
              borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
            ),
            alignment: Alignment.center,
            child: Text(story.emoji, style: const TextStyle(fontSize: 45)),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _chip('#${story.tag}', Colors.purpleAccent),
                const SizedBox(height: 8),
                Text(
                  story.title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCreatedStoryCard(StorySession story) {
    return InkWell(
      onTap: () {
        final state = context.read<AppState>();
        if (!story.hasReachedEnding && story.choices.isNotEmpty) {
          state.resumeStory(story);
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const StoryPage()),
          );
          return;
        }
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => StoryPage(preloadedStory: story)),
        );
      },
      borderRadius: BorderRadius.circular(24),
      child: Container(
        width: 190,
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: const Color(0xFF140028),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: Colors.white10),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _genreEmoji(story.genre),
              style: const TextStyle(fontSize: 30),
            ),
            const SizedBox(height: 12),
            Text(
              story.initialPrompt,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _chip('#${story.genre}', Colors.purpleAccent),
                _chip('${story.chapters.length}챕터', Colors.lightBlueAccent),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  String _genreEmoji(String genre) {
    return const {
          '판타지': '🏰',
          '모험': '🗺️',
          '우정': '🤝',
          '자연': '🌿',
          '동물': '🐾',
          '미스터리': '🔍',
        }[genre] ??
        '📖';
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final user = widget.displayName.trim().isEmpty ? '사용자' : widget.displayName;

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
                            color: const Color(0xFF140028),
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
              if (state.completedStories.isNotEmpty) ...[
                const SizedBox(height: 18),
                const Text(
                  '내가 만든 동화',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: state.completedStories
                        .map(
                          (story) => Padding(
                            padding: const EdgeInsets.only(right: 14),
                            child: _buildCreatedStoryCard(story),
                          ),
                        )
                        .toList(),
                  ),
                ),
              ],
              const SizedBox(height: 30),
              const Text(
                '추천 동화',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              Scrollbar(
                controller: _recommendScrollController,
                thumbVisibility: true,
                thickness: 4,
                radius: const Radius.circular(10),
                child: SingleChildScrollView(
                  controller: _recommendScrollController,
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: _featuredStories
                        .map(_buildFeaturedStoryCard)
                        .toList(),
                  ),
                ),
              ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }
}
