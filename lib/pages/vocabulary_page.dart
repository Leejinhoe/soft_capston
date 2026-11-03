import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../widgets/custom_bottom_nav.dart';
import 'quiz_page.dart';

class VocabularyPage extends StatefulWidget {
  final String displayName;

  const VocabularyPage({
    super.key,
    required this.displayName,
  });

  @override
  State<VocabularyPage> createState() => _VocabularyPageState();
}

class _VocabularyPageState extends State<VocabularyPage> {
  List<dynamic> myVocabList = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    fetchMyVocabularies();
  }

  // 📥 DB에서 내 저장 단어 목록 실시간 조회
  Future<void> fetchMyVocabularies() async {
    try {
      final response = await ApiClient.get('/api/vocabularies/me');

      if (!mounted) return;
      if (response.statusCode == 200) {
        final List<dynamic> data = ApiClient.decode(response) ?? [];
        setState(() {
          myVocabList = data;
          isLoading = false;
        });
      } else {
        setState(() => isLoading = false);
      }
    } catch (e) {
      debugPrint('단어장 조회 오류: $e');
      setState(() => isLoading = false);
    }
  }

  // 🧩 퀴즈 화면으로 이동 (돌아오면 외운 단어 표시를 새로 불러옴)
  Future<void> openQuiz() async {
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const QuizPage()),
    );
    if (mounted) fetchMyVocabularies();
  }

  // 🗑️ 내 단어 삭제 (한 번 더 물어본 뒤 삭제)
  Future<void> deleteVocabulary(String id, String word) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF1A0B3A),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        title: const Text('단어를 지울까요?', style: TextStyle(color: Colors.white)),
        content: Text(
          '"$word" 단어를 단어장에서 지워요.',
          style: const TextStyle(color: Colors.white70, fontSize: 16),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('그냥 둘래요', style: TextStyle(color: Colors.white70)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('지울래요', style: TextStyle(color: Color(0xFFEF4444))),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      final response = await ApiClient.delete('/api/vocabularies/$id');
      if (!mounted) return;
      if (response.statusCode == 200) {
        setState(() => myVocabList.removeWhere((v) => v['id'] == id));
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('"$word" 단어를 지웠어요.')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ApiClient.errorMessage(response, '단어를 지우지 못했어요.'))),
        );
      }
    } catch (e) {
      debugPrint('단어 삭제 오류: $e');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('단어를 지우지 못했어요. 잠시 후 다시 해 주세요.')),
      );
    }
  }

  // 📖 단어 카드 위젯 ('쉬운 뜻' 영역 삭제 및 레이아웃 정리)
  Widget vocabCard({
    required String word,
    required String definition,
    required String storyTitle,
    required Color color,
    required bool isMastered,
    required VoidCallback onDelete,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(26),
        border: Border.all(
          color: isMastered ? const Color(0xFFF59E0B).withOpacity(0.6) : Colors.white10,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: color.withOpacity(0.2),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(
              Icons.menu_book,
              color: color,
              size: 28,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        word,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    if (isMastered) ...[
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF59E0B).withOpacity(0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Text(
                          '⭐ 외웠어요',
                          style: TextStyle(
                            color: Color(0xFFF59E0B),
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                    const Spacer(),
                    IconButton(
                      onPressed: onDelete,
                      tooltip: '단어 지우기',
                      visualDensity: VisualDensity.compact,
                      icon: const Icon(Icons.delete_outline_rounded, color: Colors.white38),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.purple.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    storyTitle,
                    style: const TextStyle(color: Colors.purpleAccent, fontSize: 11),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  definition,
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 15,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = [
      Colors.purpleAccent,
      Colors.lightBlueAccent,
      Colors.greenAccent,
      Colors.orangeAccent,
      Colors.pinkAccent,
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'vocabulary',
        displayName: widget.displayName,
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: fetchMyVocabularies,
          color: const Color(0xFF8B5CF6),
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 10),
                Text(
                  '📚 ${widget.displayName}님의 단어장',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '동화에서 내가 저장한 단어들을 살펴보고 복습해보세요!',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 24),

                // 🧩 퀴즈 풀기 버튼
                Container(
                  width: double.infinity,
                  height: 64,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                    ),
                    borderRadius: BorderRadius.circular(22),
                  ),
                  child: ElevatedButton.icon(
                    onPressed: openQuiz,
                    icon: const Icon(Icons.extension_rounded, size: 28),
                    label: const Text(
                      '퀴즈 풀기',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(22),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 30),

                if (isLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(40),
                      child: CircularProgressIndicator(color: Color(0xFF8B5CF6)),
                    ),
                  )
                else if (myVocabList.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 60),
                      child: Column(
                        children: const [
                          Icon(Icons.bookmark_border_rounded, size: 60, color: Colors.white24),
                          SizedBox(height: 16),
                          Text(
                            '아직 저장된 단어가 없어요.\n동화를 읽다가 궁금한 단어를 터치해서 저장해보세요!',
                            textAlign: TextAlign.center,
                            style: TextStyle(color: Colors.white38, fontSize: 16, height: 1.5),
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  ...myVocabList.asMap().entries.map((entry) {
                    final index = entry.key;
                    final vocab = entry.value;
                    return vocabCard(
                      word: vocab['word'] ?? '',
                      definition: vocab['definition'] ?? '',
                      storyTitle: vocab['source_story_title'] ?? '동화',
                      color: colors[index % colors.length],
                      isMastered: vocab['is_mastered'] == true,
                      onDelete: () => deleteVocabulary(
                        vocab['id']?.toString() ?? '',
                        vocab['word'] ?? '',
                      ),
                    );
                  }).toList(),

                const SizedBox(height: 100),
              ],
            ),
          ),
        ),
      ),
    );
  }
}