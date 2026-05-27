import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'main.dart';
import 'models/app_state.dart';
import 'story_page.dart';

class CreatePage extends StatefulWidget {
  final String? preselectedGenre;
  const CreatePage({super.key, this.preselectedGenre});

  @override
  State<CreatePage> createState() => _CreatePageState();
}

class _CreatePageState extends State<CreatePage> {
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
        MaterialPageRoute(builder: (_) => const StoryPage()),
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

  Future<void> _startTemporaryStory() async {
    final prompt = _promptCtrl.text.trim().isEmpty
        ? '반짝이는 숲속에서 작은 비밀을 발견하는 이야기'
        : _promptCtrl.text.trim();

    final state = context.read<AppState>();
    final ok = await state.startTemporaryStory(
      genre: _selectedGenre,
      age: _selectedAge,
      prompt: prompt,
    );

    if (!mounted) return;

    if (ok) {
      Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const StoryPage()),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(state.errorMessage ?? '임시 동화를 만들지 못했어요'),
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
      backgroundColor: const Color(0xFF070018),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 10),
              const Text(
                '어떤 이야기를 원하시나요?',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 34,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 30),
              _sectionLabel('장르 선택'),
              const SizedBox(height: 16),
              _buildGenreSelector(),
              const SizedBox(height: 34),
              _sectionLabel('주인공 설정'),
              const SizedBox(height: 12),
              _buildPromptInput(),
              const SizedBox(height: 16),
              _buildSuggestions(),
              const SizedBox(height: 30),
              _sectionLabel('아이 연령대'),
              const SizedBox(height: 12),
              _buildAgeSelector(),
              const SizedBox(height: 40),
              _buildStartButton(isLoading),
              const SizedBox(height: 12),
              _buildTemporaryButton(isLoading),
              const SizedBox(height: 80),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionLabel(String text) => Text(
        text,
        style: const TextStyle(
          color: Colors.white70,
          fontSize: 18,
          fontWeight: FontWeight.w500,
        ),
      );

  Widget _buildGenreSelector() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: _genres.map((g) {
          final label = g['label'] as String;
          final isSelected = _selectedGenre == label;
          return GestureDetector(
            onTap: () => setState(() => _selectedGenre = label),
            child: Container(
              margin: const EdgeInsets.only(right: 10),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
              decoration: BoxDecoration(
                color: isSelected
                    ? const Color(0xFF8B5CF6)
                    : const Color(0xFF1A0B3A),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(g['emoji'] as String),
                  const SizedBox(width: 6),
                  Text(
                    label,
                    style: TextStyle(
                      color: isSelected ? Colors.white : Colors.white70,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildAgeSelector() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A0B3A),
        borderRadius: BorderRadius.circular(20),
      ),
      child: DropdownButton<String>(
        value: _selectedAge,
        dropdownColor: const Color(0xFF1A0B3A),
        isExpanded: true,
        underline: const SizedBox(),
        style: const TextStyle(color: Colors.white),
        items: _ages.map((age) {
          return DropdownMenuItem(
            value: age['label'] as String,
            child: Text('${age['emoji']} ${age['sub']}'),
          );
        }).toList(),
        onChanged: (value) {
          if (value == null) return;
          setState(() => _selectedAge = value);
        },
      ),
    );
  }

  Widget _buildPromptInput() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1A0B3A),
        borderRadius: BorderRadius.circular(20),
      ),
      child: TextField(
        controller: _promptCtrl,
        maxLines: 3,
        style: const TextStyle(color: Colors.white, fontSize: 14),
        decoration: const InputDecoration(
          hintText: '예: 용감한 꼬마 마법사',
          hintStyle: TextStyle(color: Colors.white38, fontSize: 13),
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
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF140028),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white10),
                ),
                child: Text(
                  s,
                  style:
                      const TextStyle(color: Colors.purpleAccent, fontSize: 11),
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
          padding: const EdgeInsets.symmetric(vertical: 20),
          backgroundColor: const Color(0xFF8B5CF6),
          disabledBackgroundColor: const Color(0xFF1A0B3A),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
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
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w700),
                  ),
                ],
              )
            : const Text(
                '✨ 동화 시작하기',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w700),
              ),
      ),
    );
  }

  Widget _buildTemporaryButton(bool isLoading) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OutlinedButton.icon(
          onPressed: isLoading ? null : _startTemporaryStory,
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.white,
            side: const BorderSide(color: Colors.white10),
            padding: const EdgeInsets.symmetric(vertical: 15),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
          ),
          icon: const Icon(Icons.bolt_rounded, size: 18),
          label: const Text(
            '임시 생성으로 바로 보기',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          '서버 연결이 안 될 때도 앱 흐름을 확인할 수 있도록 로컬 예시 동화를 바로 만들어요.',
          textAlign: TextAlign.center,
          style: TextStyle(
            color: AppColors.gray,
            fontSize: 11,
            height: 1.5,
          ),
        ),
      ],
    );
  }
}
