import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'models/app_state.dart';
import 'models/story_model.dart';

class VocabPage extends StatefulWidget {
  const VocabPage({super.key});

  @override
  State<VocabPage> createState() => _VocabPageState();
}

class _VocabPageState extends State<VocabPage> {
  final TextEditingController _searchController = TextEditingController();
  String _query = '';
  final Set<String> _deletingVocabIds = {};

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  String _sourceStoryTitle(AppState state, VocabWord vocab) {
    final savedTitle = vocab.sourceStoryTitle?.trim();
    if (savedTitle != null && savedTitle.isNotEmpty) {
      return savedTitle;
    }

    bool containsWord(List<VocabWord> vocabList) {
      return vocabList.any(
        (item) =>
            item.hard == vocab.hard &&
            item.easy == vocab.easy &&
            item.definition == vocab.definition,
      );
    }

    if (state.currentStory != null && containsWord(state.currentStory!.vocab)) {
      return state.currentStory!.initialPrompt;
    }

    for (final story in state.completedStories) {
      if (containsWord(story.vocab)) {
        return story.initialPrompt;
      }
    }
    return 'AI 동화';
  }

  Widget _vocabCard({
    required VocabWord vocab,
    required String sourceStoryTitle,
    required Color color,
    required VoidCallback? onDelete,
    required bool isDeleting,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(26),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Icon(Icons.menu_book, color: color, size: 30),
          ),
          const SizedBox(width: 18),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  vocab.hard,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  vocab.easy,
                  style: TextStyle(
                    color: color,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  vocab.definition,
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 15,
                    height: 1.6,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  '$sourceStoryTitle 에서 저장됨',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.white38, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          isDeleting
              ? const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : IconButton(
                  onPressed: onDelete,
                  icon: const Icon(Icons.delete_outline),
                  color: Colors.white38,
                  tooltip: '단어 삭제',
                ),
        ],
      ),
    );
  }

  String _vocabKey(VocabWord vocab) =>
      vocab.id ?? '${vocab.hard}|${vocab.easy}|${vocab.definition}';

  Future<void> _deleteVocab(AppState state, VocabWord vocab) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF140028),
        title: const Text('단어를 삭제할까요?', style: TextStyle(color: Colors.white)),
        content: Text(
          '"${vocab.hard}" 단어장 항목을 삭제합니다.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('삭제', style: TextStyle(color: Colors.pinkAccent)),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final key = _vocabKey(vocab);
    setState(() => _deletingVocabIds.add(key));
    final deleted = await state.deleteVocabulary(vocab);
    if (!mounted) return;
    setState(() => _deletingVocabIds.remove(key));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          deleted
              ? '단어를 삭제했어요.'
              : '삭제 실패: ${state.errorMessage ?? '알 수 없는 오류'}',
        ),
      ),
    );
  }

  void _openQuiz(List<VocabWord> vocabs) {
    if (vocabs.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('퀴즈를 만들려면 단어가 2개 이상 필요해요.')),
      );
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => VocabQuizPage(vocabs: vocabs)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final displayName = state.currentDisplayName;
    final allVocabs = state.allVocabulary;
    final filteredVocabs = allVocabs.where((vocab) {
      if (_query.trim().isEmpty) return true;
      return vocab.easy.contains(_query) ||
          vocab.hard.contains(_query) ||
          vocab.definition.contains(_query);
    }).toList();
    const colors = [
      Colors.purpleAccent,
      Colors.lightBlueAccent,
      Colors.greenAccent,
      Colors.orangeAccent,
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 10),
              Text(
                '📚 $displayName님의 단어장',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 34,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      '동화 속 새로운 표현을 배워보세요',
                      style: TextStyle(color: Colors.white70, fontSize: 16),
                    ),
                  ),
                  ElevatedButton.icon(
                    onPressed: () => _openQuiz(allVocabs),
                    icon: const Icon(Icons.quiz_outlined, size: 18),
                    label: const Text('퀴즈'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF7C3AED),
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 22),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF140028),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Colors.white10),
                ),
                child: TextField(
                  controller: _searchController,
                  onChanged: (value) => setState(() => _query = value.trim()),
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    icon: Icon(Icons.search, color: Colors.white54, size: 20),
                    hintText: '단어 검색...',
                    hintStyle: TextStyle(color: Colors.white38),
                    border: InputBorder.none,
                  ),
                ),
              ),
              const SizedBox(height: 22),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () => context.read<AppState>().loadUserData(),
                  child: filteredVocabs.isEmpty
                      ? ListView(
                          physics: const AlwaysScrollableScrollPhysics(),
                          children: [
                            const SizedBox(height: 140),
                            Text(
                              allVocabs.isEmpty
                                  ? '아직 저장된 단어가 없어요.\n동화를 읽고 어려운 단어를 모아보세요.'
                                  : '검색 결과가 없어요.',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 15,
                                height: 1.6,
                              ),
                            ),
                          ],
                        )
                      : ListView.builder(
                          physics: const AlwaysScrollableScrollPhysics(),
                          itemCount: filteredVocabs.length,
                          itemBuilder: (context, index) {
                            final vocab = filteredVocabs[index];
                            return _vocabCard(
                              vocab: vocab,
                              sourceStoryTitle: _sourceStoryTitle(state, vocab),
                              color: colors[index % colors.length],
                              isDeleting:
                                  _deletingVocabIds.contains(_vocabKey(vocab)),
                              onDelete: () => _deleteVocab(state, vocab),
                            );
                          },
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class VocabQuizPage extends StatefulWidget {
  final List<VocabWord> vocabs;

  const VocabQuizPage({super.key, required this.vocabs});

  @override
  State<VocabQuizPage> createState() => _VocabQuizPageState();
}

class _VocabQuizPageState extends State<VocabQuizPage> {
  late final List<VocabWord> _questions;
  late List<String> _currentOptions;
  int _currentIndex = 0;
  int _score = 0;
  String? _selectedAnswer;
  bool _answered = false;

  @override
  void initState() {
    super.initState();
    final shuffled = List<VocabWord>.from(widget.vocabs)..shuffle();
    _questions = shuffled.take(min(10, shuffled.length)).toList();
    _currentOptions = _buildOptionsFor(_currentQuestion);
  }

  VocabWord get _currentQuestion => _questions[_currentIndex];

  List<String> _buildOptionsFor(VocabWord question) {
    final options = <String>{question.easy};
    final others = widget.vocabs
        .where((word) => word.easy != question.easy)
        .map((word) => word.easy)
        .where((easy) => easy.trim().isNotEmpty)
        .toList()
      ..shuffle();
    options.addAll(others.take(3));
    return options.toList()..shuffle();
  }

  void _selectAnswer(String answer) {
    if (_answered) return;
    setState(() {
      _selectedAnswer = answer;
      _answered = true;
      if (answer == _currentQuestion.easy) {
        _score += 1;
      }
    });
  }

  void _next() {
    if (_currentIndex >= _questions.length - 1) {
      _showResult();
      return;
    }
    setState(() {
      _currentIndex += 1;
      _selectedAnswer = null;
      _answered = false;
      _currentOptions = _buildOptionsFor(_currentQuestion);
    });
  }

  void _restart() {
    setState(() {
      _questions.shuffle();
      _currentIndex = 0;
      _score = 0;
      _selectedAnswer = null;
      _answered = false;
      _currentOptions = _buildOptionsFor(_currentQuestion);
    });
  }

  void _showResult() {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF140028),
        title: const Text('퀴즈 완료!', style: TextStyle(color: Colors.white)),
        content: Text(
          '$_score / ${_questions.length}개를 맞혔어요.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pop(context);
            },
            child: const Text('나가기'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _restart();
            },
            child: const Text('다시 풀기'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final question = _currentQuestion;
    final options = _currentOptions;
    final progress = (_currentIndex + 1) / _questions.length;

    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF070018),
        title: const Text('단어 퀴즈'),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              LinearProgressIndicator(
                value: progress,
                color: const Color(0xFF7C3AED),
                backgroundColor: Colors.white10,
              ),
              const SizedBox(height: 18),
              Text(
                '${_currentIndex + 1} / ${_questions.length}',
                style: const TextStyle(color: Colors.white54),
              ),
              const SizedBox(height: 28),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF7C3AED), Color(0xFFEC4899)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(28),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '이 단어의 쉬운 뜻은?',
                      style: TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      question.hard,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 34,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      question.definition,
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 14,
                        height: 1.5,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              ...options.map((option) {
                final isCorrect = option == question.easy;
                final isSelected = option == _selectedAnswer;
                final color = !_answered
                    ? const Color(0xFF140028)
                    : isCorrect
                        ? const Color(0xFF064E3B)
                        : isSelected
                            ? const Color(0xFF7F1D1D)
                            : const Color(0xFF140028);
                return Container(
                  width: double.infinity,
                  margin: const EdgeInsets.only(bottom: 12),
                  child: OutlinedButton(
                    onPressed: () => _selectAnswer(option),
                    style: OutlinedButton.styleFrom(
                      backgroundColor: color,
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: Colors.white12),
                      padding: const EdgeInsets.all(16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        option,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                );
              }),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _answered ? _next : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF7C3AED),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  child: Text(
                    _currentIndex >= _questions.length - 1 ? '결과 보기' : '다음 문제',
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
