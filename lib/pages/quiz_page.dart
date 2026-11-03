import 'dart:math';

import 'package:flutter/material.dart';
import '../core/api_client.dart';

const _bgColor = Color(0xFF070018);
const _cardColor = Color(0xFF140028);
const _purple = Color(0xFF8B5CF6);
const _pink = Color(0xFFEC4899);
const _correctColor = Color(0xFF22C55E);
const _wrongColor = Color(0xFFEF4444);

const _correctMessages = [
  '딩동댕! 정말 잘했어요 🎉',
  '우와, 맞았어요! 최고예요 ⭐',
  '정답이에요! 단어 박사님이네요 👏',
];
const _wrongMessages = [
  '괜찮아요, 다음엔 꼭 맞힐 수 있어요 💜',
  '아깝다! 같이 정답을 알아봐요 🌈',
  '틀려도 괜찮아요. 이렇게 배우는 거예요 😊',
];

/// 단어장 퀴즈: 다정한 뜻풀이를 보고 맞는 단어를 고릅니다.
/// 단어장으로 돌아갈 때 결과를 저장했으면 true를 돌려줍니다.
class QuizPage extends StatefulWidget {
  const QuizPage({super.key});

  @override
  State<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends State<QuizPage> {
  final _random = Random();

  bool _isLoading = true;
  String? _errorMessage;
  String _emptyMessage = '';
  List<Map<String, dynamic>> _questions = [];

  int _index = 0;
  String? _selected;
  String _feedback = '';
  final List<String> _correctIds = [];
  final List<String> _wrongIds = [];

  bool _finished = false;
  bool _resultSaved = false;

  @override
  void initState() {
    super.initState();
    _loadQuiz();
  }

  Future<void> _loadQuiz() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _emptyMessage = '';
      _questions = [];
      _index = 0;
      _selected = null;
      _feedback = '';
      _correctIds.clear();
      _wrongIds.clear();
      _finished = false;
    });

    try {
      final response = await ApiClient.get('/api/quiz');
      if (!mounted) return;
      if (response.statusCode != 200) {
        setState(() {
          _isLoading = false;
          _errorMessage = ApiClient.errorMessage(response, '퀴즈를 불러오지 못했어요.');
        });
        return;
      }
      final data = ApiClient.decode(response) as Map<String, dynamic>? ?? {};
      final questions = (data['questions'] as List? ?? [])
          .map((q) => Map<String, dynamic>.from(q as Map))
          .toList();
      setState(() {
        _questions = questions;
        _emptyMessage = data['message']?.toString() ?? '';
        _isLoading = false;
      });
    } catch (e) {
      debugPrint('퀴즈 조회 오류: $e');
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = '퀴즈를 불러오지 못했어요. 잠시 후 다시 해 주세요.';
      });
    }
  }

  void _choose(String choice) {
    if (_selected != null) return;
    final question = _questions[_index];
    final isCorrect = choice == question['answer'];
    final id = question['vocab_id'].toString();
    final messages = isCorrect ? _correctMessages : _wrongMessages;

    setState(() {
      _selected = choice;
      _feedback = messages[_random.nextInt(messages.length)];
      (isCorrect ? _correctIds : _wrongIds).add(id);
    });
  }

  Future<void> _next() async {
    if (_index + 1 < _questions.length) {
      setState(() {
        _index++;
        _selected = null;
        _feedback = '';
      });
      return;
    }
    setState(() => _finished = true);
    await _saveResult();
  }

  Future<void> _saveResult() async {
    try {
      final response = await ApiClient.post('/api/quiz/result', body: {
        'correct_vocab_ids': _correctIds,
        'wrong_vocab_ids': _wrongIds,
      });
      if (response.statusCode == 200) _resultSaved = true;
    } catch (e) {
      debugPrint('퀴즈 결과 저장 오류: $e');
    }
  }

  void _backToVocabulary() => Navigator.pop(context, _resultSaved);

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _backToVocabulary();
      },
      child: Scaffold(
        backgroundColor: _bgColor,
        appBar: AppBar(
          backgroundColor: _bgColor,
          foregroundColor: Colors.white,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            onPressed: _backToVocabulary,
          ),
          title: const Text(
            '🧩 단어 퀴즈',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 22),
          ),
        ),
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: _buildBody(),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator(color: _purple));
    }
    if (_errorMessage != null) {
      return _messageView(
        emoji: '😢',
        message: _errorMessage!,
        buttons: [
          _bigButton(label: '다시 해 보기', icon: Icons.refresh_rounded, onPressed: _loadQuiz),
        ],
      );
    }
    if (_questions.isEmpty) {
      return _messageView(
        emoji: '📚',
        message: '${_emptyMessage.isEmpty ? '단어를 먼저 저장해 보세요' : _emptyMessage}!\n'
            '동화를 읽다가 궁금한 단어를 눌러서 저장하면\n퀴즈를 풀 수 있어요.',
        buttons: [
          _bigButton(label: '단어장으로', icon: Icons.menu_book_rounded, onPressed: _backToVocabulary),
        ],
      );
    }
    if (_finished) return _resultView();
    return _questionView();
  }

  // 한 문제 화면
  Widget _questionView() {
    final question = _questions[_index];
    final choices = (question['choices'] as List).map((c) => c.toString()).toList();
    final answer = question['answer'].toString();
    final answered = _selected != null;
    final isCorrect = _selected == answer;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '${_index + 1}번째 문제 / 모두 ${_questions.length}문제',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white70, fontSize: 18),
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              value: (_index + (answered ? 1 : 0)) / _questions.length,
              minHeight: 10,
              backgroundColor: Colors.white10,
              color: _purple,
            ),
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(26),
            decoration: BoxDecoration(
              color: _cardColor,
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: _purple.withOpacity(0.5), width: 2),
            ),
            child: Column(
              children: [
                const Text(
                  '이 뜻을 가진 단어는 무엇일까요?',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.purpleAccent, fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),
                Text(
                  question['definition'].toString(),
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white, fontSize: 24, height: 1.5, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          ...choices.map((choice) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: _choiceButton(choice, answer),
              )),
          if (answered) ...[
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: (isCorrect ? _correctColor : _wrongColor).withOpacity(0.15),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Column(
                children: [
                  Text(
                    _feedback,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                  if (!isCorrect) ...[
                    const SizedBox(height: 8),
                    Text(
                      '정답은 "$answer"였어요.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70, fontSize: 19),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 18),
            _bigButton(
              label: _index + 1 < _questions.length ? '다음 문제' : '결과 보기',
              icon: Icons.arrow_forward_rounded,
              onPressed: _next,
            ),
          ],
        ],
      ),
    );
  }

  Widget _choiceButton(String choice, String answer) {
    final answered = _selected != null;
    Color background = _cardColor;
    Color border = Colors.white24;
    IconData? icon;

    if (answered && choice == answer) {
      background = _correctColor.withOpacity(0.25);
      border = _correctColor;
      icon = Icons.check_circle_rounded;
    } else if (answered && choice == _selected) {
      background = _wrongColor.withOpacity(0.25);
      border = _wrongColor;
      icon = Icons.cancel_rounded;
    }

    return SizedBox(
      height: 72,
      child: ElevatedButton(
        onPressed: answered ? () {} : () => _choose(choice),
        style: ElevatedButton.styleFrom(
          backgroundColor: background,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(22),
            side: BorderSide(color: border, width: 2),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, color: border, size: 30),
              const SizedBox(width: 10),
            ],
            Flexible(
              child: Text(
                choice,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 마지막 점수 화면
  Widget _resultView() {
    final total = _questions.length;
    final score = _correctIds.length;
    final String emoji;
    final String praise;
    if (score == total) {
      emoji = '🏆';
      praise = '모두 맞혔어요! 정말 대단해요!';
    } else if (score * 2 >= total) {
      emoji = '🌟';
      praise = '아주 잘했어요! 조금만 더 하면 단어 박사예요!';
    } else {
      emoji = '💜';
      praise = '끝까지 풀어서 정말 멋져요!\n다시 풀면 더 많이 맞힐 수 있어요.';
    }

    return _messageView(
      emoji: emoji,
      title: '$total문제 중 $score문제 맞혔어요!',
      message: praise,
      buttons: [
        _bigButton(label: '다시 풀기', icon: Icons.refresh_rounded, onPressed: _loadQuiz),
        const SizedBox(height: 14),
        _bigButton(
          label: '단어장으로',
          icon: Icons.menu_book_rounded,
          onPressed: _backToVocabulary,
          outlined: true,
        ),
      ],
    );
  }

  Widget _messageView({
    required String emoji,
    String? title,
    required String message,
    required List<Widget> buttons,
  }) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 30),
          Text(emoji, textAlign: TextAlign.center, style: const TextStyle(fontSize: 80)),
          const SizedBox(height: 20),
          if (title != null) ...[
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 14),
          ],
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white70, fontSize: 21, height: 1.5),
          ),
          const SizedBox(height: 36),
          ...buttons,
        ],
      ),
    );
  }

  Widget _bigButton({
    required String label,
    required IconData icon,
    required VoidCallback onPressed,
    bool outlined = false,
  }) {
    return Container(
      height: 64,
      decoration: BoxDecoration(
        gradient: outlined ? null : const LinearGradient(colors: [_purple, _pink]),
        borderRadius: BorderRadius.circular(22),
        border: outlined ? Border.all(color: _purple, width: 2) : null,
      ),
      child: ElevatedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon, size: 28),
        label: Text(label, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          shadowColor: Colors.transparent,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
      ),
    );
  }
}
