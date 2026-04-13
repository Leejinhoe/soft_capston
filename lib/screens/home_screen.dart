import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/app_state.dart';
import 'story_screen.dart';
import 'create_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  static const _genres = [
    {'emoji': '🏰', 'label': '판타지', 'color': Color(0xFF7C3AED)},
    {'emoji': '🗺️', 'label': '모험', 'color': Color(0xFF0EA5E9)},
    {'emoji': '🤝', 'label': '우정', 'color': Color(0xFFEC4899)},
    {'emoji': '🌿', 'label': '자연', 'color': Color(0xFF10B981)},
    {'emoji': '🐾', 'label': '동물', 'color': Color(0xFFF59E0B)},
    {'emoji': '🔍', 'label': '미스터리', 'color': Color(0xFF6366F1)},
  ];

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0, -0.6),
          radius: 1.2,
          colors: [Color(0xFF1a0a3a), Color(0xFF050214), Color(0xFF010108)],
          stops: [0.0, 0.5, 1.0],
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 8),
                    _buildBanner(context),
                    const SizedBox(height: 28),
                    _buildSectionTitle('장르 선택'),
                    const SizedBox(height: 12),
                    _buildGenreGrid(context),
                    const SizedBox(height: 28),
                    if (state.completedStories.isNotEmpty) ...[
                      _buildSectionTitle('최근 읽은 동화'),
                      const SizedBox(height: 12),
                      _buildRecentStories(context, state),
                      const SizedBox(height: 24),
                    ],
                    _buildTipsCard(),
                    const SizedBox(height: 100),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          ShaderMask(
            shaderCallback: (bounds) => const LinearGradient(
              colors: [AppColors.p400, AppColors.pink2],
            ).createShader(bounds),
            child: const Text(
              '✨ 동화 AI',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Colors.white,
              ),
            ),
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: const Icon(Icons.notifications_outlined,
                color: AppColors.gray, size: 20),
          ),
        ],
      ),
    );
  }

  Widget _buildBanner(BuildContext context) {
    return GestureDetector(
      onTap: () => _goToCreate(context, null),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF2D1563), Color(0xFF1E1645)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppColors.border),
          boxShadow: [
            BoxShadow(
              color: AppColors.p600.withOpacity(0.25),
              blurRadius: 24,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '새로운 모험을 시작해요!',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'AI가 나만의 특별한 동화를 만들어줘요',
                    style: TextStyle(
                      color: AppColors.p300.withOpacity(0.8),
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [AppColors.p600, AppColors.pink],
                      ),
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.p600.withOpacity(0.4),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: const Text(
                      '동화 만들기 🪄',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const Text('🧙‍♂️', style: TextStyle(fontSize: 56)),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        color: Colors.white,
        fontSize: 16,
        fontWeight: FontWeight.w700,
      ),
    );
  }

  Widget _buildGenreGrid(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 1.1,
      ),
      itemCount: _genres.length,
      itemBuilder: (context, i) {
        final g = _genres[i];
        return GestureDetector(
          onTap: () => _goToCreate(context, g['label'] as String),
          child: Container(
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(g['emoji'] as String,
                    style: const TextStyle(fontSize: 28)),
                const SizedBox(height: 6),
                Text(
                  g['label'] as String,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildRecentStories(BuildContext context, AppState state) {
    return SizedBox(
      height: 130,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: state.completedStories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 12),
        itemBuilder: (context, i) {
          final story = state.completedStories[i];
          return GestureDetector(
            onTap: () {
              // 완료된 이야기 다시 보기
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => StoryScreen(preloadedStory: story),
                ),
              );
            },
            child: Container(
              width: 160,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Text(_genreEmoji(story.genre),
                          style: const TextStyle(fontSize: 22)),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppColors.p700.withOpacity(0.5),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          story.genre,
                          style: const TextStyle(
                              color: AppColors.p300, fontSize: 10),
                        ),
                      ),
                    ],
                  ),
                  Text(
                    story.initialPrompt,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                  Text(
                    '${story.chapters.length}챕터 완료',
                    style: const TextStyle(color: AppColors.gray, fontSize: 10),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildTipsCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.teal.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.teal.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Text('💡', style: TextStyle(fontSize: 24)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                Text(
                  '더 재미있는 동화를 만들려면?',
                  style: TextStyle(
                      color: AppColors.teal,
                      fontSize: 13,
                      fontWeight: FontWeight.w700),
                ),
                SizedBox(height: 4),
                Text(
                  '주인공 이름, 좋아하는 장소, 친구 이름을 넣어보세요!',
                  style: TextStyle(color: AppColors.gray, fontSize: 11),
                ),
              ],
            ),
          ),
        ],
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
    }[genre] ?? '📖';
  }

  void _goToCreate(BuildContext context, String? genre) {
    // MainShell의 index를 2(만들기)로 변경
    // genre가 있으면 CreateScreen에 pre-fill
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => CreateScreen(preselectedGenre: genre)),
    );
  }
}
