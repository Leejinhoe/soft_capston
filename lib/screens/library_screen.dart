import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/app_state.dart';
import 'story_screen.dart';

class LibraryScreen extends StatelessWidget {
  const LibraryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: const Text('📚 내 서재'),
        backgroundColor: AppColors.bg,
      ),
      body: state.completedStories.isEmpty
          ? _buildEmpty()
          : ListView.separated(
              padding: const EdgeInsets.all(20),
              itemCount: state.completedStories.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) {
                final story = state.completedStories[i];
                return GestureDetector(
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) =>
                          StoryScreen(preloadedStory: story),
                    ),
                  ),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: AppColors.card,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 52,
                          height: 52,
                          decoration: BoxDecoration(
                            color: AppColors.p700.withOpacity(0.3),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Center(
                            child: Text(
                              _genreEmoji(story.genre),
                              style: const TextStyle(fontSize: 26),
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                story.initialPrompt,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  _chip(story.genre, AppColors.p400),
                                  const SizedBox(width: 6),
                                  _chip('${story.chapters.length}챕터',
                                      AppColors.teal),
                                  const SizedBox(width: 6),
                                  _chip('선택 ${story.allChoicesMade.length}회',
                                      AppColors.pink),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const Icon(Icons.arrow_forward_ios_rounded,
                            color: AppColors.gray2, size: 14),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
          Text('📖', style: TextStyle(fontSize: 56)),
          SizedBox(height: 16),
          Text(
            '아직 읽은 동화가 없어요',
            style: TextStyle(
                color: Colors.white, fontSize: 16,
                fontWeight: FontWeight.w700),
          ),
          SizedBox(height: 8),
          Text(
            '동화를 만들어서 읽어보세요!',
            style: TextStyle(color: AppColors.gray, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label,
          style: TextStyle(color: color, fontSize: 10,
              fontWeight: FontWeight.w600)),
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
}
