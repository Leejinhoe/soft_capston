import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../main.dart';
import '../models/app_state.dart';
import 'story_screen.dart';

class CreateScreen extends StatefulWidget {
  final String? preselectedGenre;
  const CreateScreen({super.key, this.preselectedGenre});

  @override
  State<CreateScreen> createState() => _CreateScreenState();
}

class _CreateScreenState extends State<CreateScreen> {
  final _promptCtrl = TextEditingController();
  String _selectedGenre = '판타지';
  String _selectedAge = '초등_저학년';

  static const _genres = [
    {'emoji': '🏰', 'label': '판타지'},
    {'emoji': '🗺️', 'label': '모험'},
    {'emoji': '🤝', 'label': '우정'},
    {'emoji': '🌿', 'label': '자연'},
    {'emoji': '🐾', 'label': '동물'},
    {'emoji': '🔍', 'label': '미스터리'},
  ];

  static const _ages = [
    {'label': '유아', 'sub': '4-6세', 'emoji': '🍼'},
    {'label': '초등_저학년', 'sub': '7-9세', 'emoji': '📚'},
    {'label': '초등_고학년', 'sub': '10-12세', 'emoji': '🎒'},
  ];

  static const _suggestions = [
    '용을 친구로 사귄 소년의 이야기',
    '별에서 온 작은 왕자 이야기',
    '마법 빗자루를 찾아서',
    '숲속 동물들을 구해줘',
    '바닷속 왕국 탐험',
    '시간 여행하는 시계',
  ];

  @override
  void initState() {
    super.initState();
    if (widget.preselectedGenre != null) {
      _selectedGenre = widget.preselectedGenre!;
    }
  }

  @override
  void dispose() {
    _promptCtrl.dispose();
    super.dispose();
  }

  Future<void> _startStory() async {
    final prompt = _promptCtrl.text.trim();
    if (prompt.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('어떤 동화를 원하는지 알려주세요!'),
          backgroundColor: AppColors.p600,
        ),
      );
      return;
    }

    final state = context.read<AppState>();
    final ok = await state.startStory(
      genre: _selectedGenre,
      age: _selectedAge,
      prompt: prompt,
    );

    if (!mounted) return;

    if (ok) {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const StoryScreen()),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(state.errorMessage ?? '오류가 발생했어요'),
          backgroundColor: Colors.red.shade700,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final isLoading = state.isLoading;

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: const Text('동화 만들기 🪄'),
        backgroundColor: AppColors.bg,
        leading: Navigator.canPop(context)
            ? IconButton(
                icon: const Icon(Icons.arrow_back_ios_rounded),
                onPressed: () => Navigator.pop(context),
              )
            : null,
      ),
      body: Stack(
        children: [
          // 배경 그라디언트
          Positioned.fill(
            child: Container(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0, -0.8),
                  radius: 0.8,
                  colors: [Color(0xFF1a0940), Color(0xFF06041A)],
                ),
              ),
            ),
          ),
          SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _sectionLabel('📖 장르 선택'),
                const SizedBox(height: 12),
                _buildGenreSelector(),
                const SizedBox(height: 24),
                _sectionLabel('👶 연령 선택'),
                const SizedBox(height: 12),
                _buildAgeSelector(),
                const SizedBox(height: 24),
                _sectionLabel('💭 어떤 동화를 원하나요?'),
                const SizedBox(height: 12),
                _buildPromptInput(),
                const SizedBox(height: 16),
                _buildSuggestions(),
                const SizedBox(height: 32),
                _buildStartButton(isLoading),
                const SizedBox(height: 80),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionLabel(String text) => Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 14,
          fontWeight: FontWeight.w700,
        ),
      );

  Widget _buildGenreSelector() {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: _genres.map((g) {
        final label = g['label'] as String;
        final isSelected = _selectedGenre == label;
        return GestureDetector(
          onTap: () => setState(() => _selectedGenre = label),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: isSelected
                  ? AppColors.p600.withOpacity(0.3)
                  : AppColors.card,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: isSelected ? AppColors.p500 : AppColors.border,
                width: isSelected ? 1.5 : 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(g['emoji'] as String,
                    style: const TextStyle(fontSize: 16)),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    color: isSelected ? AppColors.p300 : AppColors.gray,
                    fontSize: 13,
                    fontWeight: isSelected
                        ? FontWeight.w600
                        : FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildAgeSelector() {
    return Row(
      children: _ages.map((a) {
        final label = a['label'] as String;
        final isSelected = _selectedAge == label;
        return Expanded(
          child: GestureDetector(
            onTap: () => setState(() => _selectedAge = label),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: isSelected
                    ? AppColors.p600.withOpacity(0.25)
                    : AppColors.card,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: isSelected ? AppColors.p500 : AppColors.border,
                  width: isSelected ? 1.5 : 1,
                ),
              ),
              child: Column(
                children: [
                  Text(a['emoji'] as String,
                      style: const TextStyle(fontSize: 22)),
                  const SizedBox(height: 4),
                  Text(
                    a['sub'] as String,
                    style: TextStyle(
                      color: isSelected ? AppColors.p300 : AppColors.gray,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildPromptInput() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: TextField(
        controller: _promptCtrl,
        maxLines: 4,
        style: const TextStyle(color: Colors.white, fontSize: 14),
        decoration: const InputDecoration(
          hintText: '예: 마법 학교에 다니는 소녀가 용과 친구가 되는 이야기',
          hintStyle: TextStyle(color: AppColors.gray2, fontSize: 13),
          border: InputBorder.none,
          contentPadding: EdgeInsets.all(16),
        ),
      ),
    );
  }

  Widget _buildSuggestions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '추천 주제',
          style: TextStyle(color: AppColors.gray, fontSize: 12),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: _suggestions.map((s) {
            return GestureDetector(
              onTap: () => _promptCtrl.text = s,
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.card2,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColors.border),
                ),
                child: Text(
                  s,
                  style: const TextStyle(
                      color: AppColors.p400, fontSize: 11),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildStartButton(bool isLoading) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: isLoading ? null : _startStory,
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 16),
          backgroundColor: AppColors.p600,
          disabledBackgroundColor: AppColors.p700,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          elevation: 0,
        ),
        child: isLoading
            ? const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  ),
                  SizedBox(width: 12),
                  Text(
                    '동화 생성 중... (1-2분)',
                    style: TextStyle(color: Colors.white, fontSize: 15,
                        fontWeight: FontWeight.w700),
                  ),
                ],
              )
            : const Text(
                '✨ 동화 시작하기',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700),
              ),
      ),
    );
  }
}
