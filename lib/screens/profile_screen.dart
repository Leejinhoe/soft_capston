import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/app_state.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final totalStories = state.completedStories.length;
    final totalChoices = state.completedStories
        .fold(0, (sum, s) => sum + s.allChoicesMade.length);

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: const Text('👤 프로필'),
        backgroundColor: AppColors.bg,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.8),
            radius: 0.7,
            colors: [Color(0xFF1a0940), Color(0xFF06041A)],
          ),
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              const SizedBox(height: 12),
              // 아바타
              Container(
                width: 90,
                height: 90,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppColors.p600, AppColors.pink],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.p600.withOpacity(0.5),
                      blurRadius: 20,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: const Center(
                  child: Text('🧒', style: TextStyle(fontSize: 44)),
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                '동화 탐험가',
                style: TextStyle(
                    color: Colors.white, fontSize: 18,
                    fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 4),
              const Text(
                '나만의 이야기를 만들어요',
                style: TextStyle(color: AppColors.gray, fontSize: 13),
              ),
              const SizedBox(height: 24),

              // 통계
              Row(
                children: [
                  _statCard('읽은 동화', '$totalStories권', '📖'),
                  const SizedBox(width: 12),
                  _statCard('한 선택', '$totalChoices회', '🌟'),
                  const SizedBox(width: 12),
                  _statCard('배운 단어',
                      '${state.completedStories.fold(0, (s, st) => s + st.vocab.length)}개',
                      '📚'),
                ],
              ),
              const SizedBox(height: 24),

              // 서버 설정
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.card,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('⚙️ 서버 설정',
                        style: TextStyle(
                            color: Colors.white, fontSize: 14,
                            fontWeight: FontWeight.w700)),
                    const SizedBox(height: 12),
                    const Text(
                      'api_service.dart 의 baseUrl 을\n실제 서버 주소로 변경하세요',
                      style: TextStyle(
                          color: AppColors.gray, fontSize: 12,
                          height: 1.5),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppColors.bg,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Text(
                        'http://localhost:8000',
                        style: TextStyle(
                            color: AppColors.teal,
                            fontSize: 12,
                            fontFamily: 'monospace'),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 100),
            ],
          ),
        ),
      ),
    );
  }

  Widget _statCard(String label, String value, String emoji) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 24)),
            const SizedBox(height: 6),
            Text(
              value,
              style: const TextStyle(
                  color: Colors.white, fontSize: 18,
                  fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: const TextStyle(
                  color: AppColors.gray, fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }
}
