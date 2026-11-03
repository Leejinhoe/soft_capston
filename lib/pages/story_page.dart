import 'dart:async';

import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/story_genres.dart';
import 'package:just_audio/just_audio.dart';

import '../widgets/custom_bottom_nav.dart';

/// 분기형 동화: 첫 장면 → 선택지 고르기 → … → 결말 (백엔드 branching.py)
/// resumeStoryId를 주면 마이페이지에서 "이어하기"로 연 것 (만들던 동화를 불러옴)
class StoryPage extends StatefulWidget {
  final String displayName;
  final String? resumeStoryId;

  const StoryPage({
    super.key,
    required this.displayName,
    this.resumeStoryId,
  });

  @override
  State<StoryPage> createState() => _StoryPageState();
}

const _choiceColors = [
  [Color(0xFFF472B6), Color(0xFFFB7185)], // 분홍
  [Color(0xFF60A5FA), Color(0xFF818CF8)], // 파랑
  [Color(0xFF34D399), Color(0xFF2DD4BF)], // 초록
];
const _choiceEmojis = ['🌸', '🌊', '🍀'];

const _sceneLoadingMessages = [
  '이야기 요정이 다음 장면을 쓰고 있어요 ✏️',
  '별님이 반짝반짝 생각 중이에요 ✨',
  '책장을 사르륵 넘기는 중이에요 📖',
  '두근두근, 무슨 일이 생길까요? 💓',
];
const _endingLoadingMessages = [
  '따뜻한 결말을 준비하고 있어요 🌙',
  '이야기에 어울리는 제목을 짓고 있어요 🏷️',
  '배울 단어를 골라 담고 있어요 🧺',
  '포근한 이불을 덮어 주는 중이에요 🛏️',
];

class _StoryPageState extends State<StoryPage> {
  final TextEditingController promptController = TextEditingController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final ScrollController _scrollController = ScrollController();

  String selectedGenre = '판타지';
  String selectedAge = '5-7세';

  bool isPlayingTTS = false; // 🔊 TTS 재생 상태 관리
  bool isSharing = false;

  // 진행 중인 동화 상태 (서버 응답 그대로)
  String storyId = ''; // 생성 즉시 저장된 동화 id (커뮤니티 공유 시 원본 연결용)
  String storyTitle = '';
  String status = ''; // in_progress / completed
  int maxScenes = 8;
  List<Map<String, dynamic>> scenes = [];
  List<dynamic> vocabList = [];

  // 생성 중 로딩
  bool isBusy = false;
  bool isOpening = false; // 이어하기로 불러오는 중
  List<String> _loadingMessages = _sceneLoadingMessages;
  int _loadingIndex = 0;
  Timer? _loadingTimer;

  final List<String> genres = kStoryGenres;

  final List<String> ages = [
    '5-7세',
    '8-10세',
    '11-13세',
  ];

  bool get hasStory => scenes.isNotEmpty;
  bool get isCompleted => status == 'completed';
  String get storyText =>
      scenes.map((s) => (s['text'] ?? '').toString()).join('\n\n');

  @override
  void initState() {
    super.initState();
    _audioPlayer.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed) {
        if (mounted) {
          setState(() {
            isPlayingTTS = false;
          });
        }
      }
    });
    final resumeId = widget.resumeStoryId;
    if (resumeId != null && resumeId.isNotEmpty) _loadStory(resumeId);
  }

  @override
  void dispose() {
    _loadingTimer?.cancel();
    _audioPlayer.dispose();
    promptController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ---------- 서버 응답 반영 ----------
  void _applyState(dynamic data) {
    if (data is! Map) return;
    setState(() {
      storyId = (data['story_id'] ?? '').toString();
      storyTitle = (data['title'] ?? '').toString();
      status = (data['status'] ?? '').toString();
      maxScenes = (data['max_scenes'] as num?)?.toInt() ?? 8;
      scenes = ((data['scenes'] as List?) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      vocabList = (data['vocab_list'] as List?) ?? [];
      final age = (data['age'] ?? '').toString();
      if (ages.contains(age)) selectedAge = age;
      final topic = (data['topic'] ?? '').toString();
      if (topic.isNotEmpty) promptController.text = topic;
    });
  }

  void _startLoading(List<String> messages) {
    _loadingTimer?.cancel();
    setState(() {
      isBusy = true;
      _loadingMessages = messages;
      _loadingIndex = 0;
    });
    _loadingTimer = Timer.periodic(const Duration(milliseconds: 2200), (_) {
      if (mounted) setState(() => _loadingIndex++);
    });
    _scrollToBottom();
  }

  void _stopLoading() {
    _loadingTimer?.cancel();
    _loadingTimer = null;
    if (mounted) setState(() => isBusy = false);
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 500),
        curve: Curves.easeOut,
      );
    });
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  /// 장면 만들기 API 공통: 성공하면 화면 갱신, 409(이미 넘어감)면 서버 상태로 다시 맞춤
  Future<void> _runStep(String path, Map<String, dynamic> body,
      {required List<String> messages}) async {
    if (isBusy) return;
    _startLoading(messages);
    try {
      final response = await ApiClient.post(path, body: body);
      if (!mounted) return;
      if (response.statusCode == 200) {
        _applyState(ApiClient.decode(response));
      } else {
        _toast(ApiClient.errorMessage(response));
        if (response.statusCode == 409 && storyId.isNotEmpty) {
          await _loadStory(storyId, quiet: true);
        }
      }
    } catch (e) {
      debugPrint('동화 생성 오류: $e');
      _toast('서버에 연결하지 못했어요. 잠시 후 다시 눌러 주세요.');
    } finally {
      _stopLoading();
      _scrollToBottom();
    }
  }

  // ✨ 동화 시작: 첫 장면 + 선택지 3개
  Future<void> startStory() async {
    if (promptController.text.trim().isEmpty) {
      _toast('동화 주제를 입력해주세요.');
      return;
    }
    await _audioPlayer.stop();
    setState(() {
      isPlayingTTS = false;
      storyId = '';
      scenes = [];
      vocabList = [];
      status = '';
    });
    await _runStep(
      '/api/stories/branching/start',
      {
        'prompt': promptController.text.trim(),
        'genre': selectedGenre,
        'age': selectedAge,
      },
      messages: _sceneLoadingMessages,
    );
  }

  // 🧭 선택지 고르기 → 다음 장면 (8번째 자리면 서버가 결말로 마무리)
  Future<void> chooseOption(int index) async {
    final willEnd = scenes.length + 1 >= maxScenes;
    await _runStep(
      '/api/stories/$storyId/choose',
      {'scene_number': scenes.length, 'choice_index': index},
      messages: willEnd ? _endingLoadingMessages : _sceneLoadingMessages,
    );
  }

  // 🌙 이야기 마무리하기
  Future<void> finishStory() async {
    await _runStep(
      '/api/stories/$storyId/finish',
      {'scene_number': scenes.length},
      messages: _endingLoadingMessages,
    );
  }

  // 📂 이어하기 / 다시 맞추기
  Future<void> _loadStory(String id, {bool quiet = false}) async {
    if (!quiet) setState(() => isOpening = true);
    try {
      final response = await ApiClient.get('/api/stories/$id/branching');
      if (!mounted) return;
      if (response.statusCode == 200) {
        _applyState(ApiClient.decode(response));
        _scrollToBottom();
      } else {
        _toast(ApiClient.errorMessage(response));
      }
    } catch (e) {
      _toast('서버에 연결하지 못했어요.');
    } finally {
      if (mounted && !quiet) setState(() => isOpening = false);
    }
  }

  // 🆕 새 동화 만들기 (만들던 동화는 서버에 저장돼 있어서 마이페이지에서 이어할 수 있음)
  Future<void> resetStory() async {
    final wasInProgress = hasStory && !isCompleted;
    await _audioPlayer.stop();
    setState(() {
      storyId = '';
      storyTitle = '';
      status = '';
      scenes = [];
      vocabList = [];
      isPlayingTTS = false;
    });
    if (wasInProgress) {
      _toast('만들던 동화는 마이페이지 "내가 만든 동화"에서 이어할 수 있어요 📚');
    }
  }

  // 🔊 백엔드 DB에 단어 저장 API 호출
  Future<void> saveVocabularyToDB(Map<String, dynamic> wordItem) async {
    try {
      final title = storyTitle.isNotEmpty
          ? storyTitle
          : (promptController.text.isEmpty ? '신비한 동화 이야기' : promptController.text);
      final response = await ApiClient.post(
        '/api/vocabularies/add',
        body: {
          'hard': wordItem['hard'],
          'easy': '',
          // 문맥에 맞춘 사전식 뜻 + 고른 사전 원문 뜻 (비어 있으면 서버가 문장으로 다시 찾음)
          'definition': wordItem['definition'] ?? '',
          'dict_definition': wordItem['dict_definition'] ?? '',
          'sentence': wordItem['sentence'] ?? '',
          // "뜻이 여러 가지예요" 상태면 서버가 저장할 때 다시 고릅니다.
          'ambiguous': wordItem['ambiguous'] == true,
          'source_story_title': title,
          'origin_story_id':
              storyId.isNotEmpty ? storyId : '650000000000000000000001',
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('\'${wordItem['hard']}\' 단어가 내 단어장에 저장되었습니다! ✨'),
              backgroundColor: const Color(0xFF8B5CF6),
            ),
          );
        }
      } else {
        throw Exception('서버 응답 오류 (${response.statusCode})');
      }
    } catch (e) {
      debugPrint('단어 저장 오류: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('단어장에 등록 완료 (\'${wordItem['hard']}\')'),
          ),
        );
      }
    }
  }

  // 🌐 커뮤니티 공유: 완료된 동화(story_id)를 복사해 게시글로 올리고, 원본과 연결해 둡니다.
  Future<void> shareStoryToCommunity() async {
    if (storyId.isEmpty || isSharing || !isCompleted) return;
    setState(() => isSharing = true);
    try {
      final response = await ApiClient.post(
        '/api/community/posts',
        body: {'story_id': storyId},
      );
      if (!mounted) return;
      final ok = response.statusCode == 200;
      final data = ApiClient.decode(response);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(ok
              ? (data['already_shared'] == true
                  ? '이미 커뮤니티에 올린 동화예요 😊'
                  : '커뮤니티에 동화가 공유되었어요! 🌐')
              : ApiClient.errorMessage(response)),
          backgroundColor: ok ? const Color(0xFF8B5CF6) : null,
        ),
      );
    } catch (e) {
      debugPrint('커뮤니티 공유 오류: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('서버에 연결하지 못했어요.')),
        );
      }
    } finally {
      if (mounted) setState(() => isSharing = false);
    }
  }

  // 🔍 본문 클릭 단어 + 포함된 문장 전체를 백엔드로 전달해 실시간 사전 조회
  Future<void> fetchAndShowVocabDialog(String targetWord, String fullSentence) async {
    final cleanWord = targetWord.replaceAll(RegExp(r'[^\w\s가-힣]'), '');
    if (cleanWord.trim().isEmpty) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(
        child: CircularProgressIndicator(color: Color(0xFF8B5CF6)),
      ),
    );

    try {
      final response = await ApiClient.post(
        '/api/vocabularies/search-context',
        body: {
          'word': cleanWord,
          'sentence': fullSentence,
          'age': selectedAge,
        },
      );

      if (mounted) Navigator.pop(context); // 로딩 닫기

      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        showVocabularyDialog({
          'hard': data['hard'] ?? cleanWord,
          'definition': data['definition'] ?? '',
          'dict_definition': data['dict_definition'] ?? '',
          'ambiguous': data['ambiguous'] == true,
          'sentence': fullSentence,
        });
      } else {
        _showLookupError();
      }
    } catch (e) {
      if (mounted) Navigator.pop(context); // 로딩 닫기
      _showLookupError();
    }
  }

  void _showLookupError() {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('뜻을 불러오지 못했어요. 잠시 후 다시 눌러 주세요.')),
    );
  }

  // 📖 단어 팝업 사전 다이얼로그 (쉬운 뜻 항목 완전 제거)
  void showVocabularyDialog(Map<String, dynamic> wordItem) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1F0B38),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
            side: const BorderSide(color: Color(0xFF8B5CF6), width: 1.5),
          ),
          title: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.purple.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.menu_book,
                  color: Colors.purpleAccent,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                wordItem['hard'] ?? '',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 22,
                ),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '단어 뜻풀이',
                style: TextStyle(
                  color: Colors.white54,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                wordItem['definition'] ?? '',
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 16,
                  height: 1.5,
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text(
                '닫기',
                style: TextStyle(color: Colors.white54),
              ),
            ),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF8B5CF6),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 10,
                ),
              ),
              onPressed: () {
                Navigator.of(context).pop();
                saveVocabularyToDB(wordItem);
              },
              icon: const Icon(Icons.bookmark_add, color: Colors.white, size: 18),
              label: const Text(
                '내 단어장 저장',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  // 🔊 TTS 음성 재생 및 버튼 상태 제어 함수
  Future<void> playTTS() async {
    if (storyText.isEmpty) return;

    if (isPlayingTTS) {
      await _audioPlayer.stop();
      setState(() {
        isPlayingTTS = false;
      });
      return;
    }

    setState(() {
      isPlayingTTS = true;
    });

    try {
      await _audioPlayer.setAudioSource(
        AudioSource.uri(
          ApiClient.uri('/api/tts'),
        ),
      );
      await _audioPlayer.play();
    } catch (e) {
      debugPrint('TTS 재생 오류: $e');
      if (mounted) {
        setState(() {
          isPlayingTTS = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('음성 재생 실패: 백엔드 서버를 확인해 주세요.'),
          ),
        );
      }
    }
  }

  // 📖 문장 단위 문맥을 유지하는 클릭 가능 본문 위젯 생성
  Widget buildClickableStoryText(String fullText) {
    final lines = fullText.split('\n');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: lines.map((line) {
        if (line.trim().isEmpty) {
          return const SizedBox(height: 12);
        }

        final words = line.split(' ');

        return Wrap(
          spacing: 6,
          runSpacing: 8,
          children: words.map((word) {
            return GestureDetector(
              onTap: () => fetchAndShowVocabDialog(word, line),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
                child: Text(
                  word,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    height: 1.5,
                    decoration: TextDecoration.underline,
                    decorationColor: Color(0x668B5CF6),
                  ),
                ),
              ),
            );
          }).toList(),
        );
      }).toList(),
    );
  }

  // 💡 AI 능동 추천 주요 단어 렌더링
  Widget buildVocabulary() {
    if (vocabList.isEmpty) {
      return const SizedBox();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '추천 주요 단어',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 16),
        ...vocabList.map((word) {
          return Container(
            margin: const EdgeInsets.only(bottom: 14),
            decoration: BoxDecoration(
              color: const Color(0xFF140028),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: Colors.white10,
              ),
            ),
            child: ListTile(
              onTap: () => showVocabularyDialog(word),
              leading: Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: Colors.purple.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.menu_book,
                  color: Colors.purpleAccent,
                ),
              ),
              title: Text(
                word['hard'] ?? '',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  word['definition'] ?? '',
                  style: const TextStyle(
                    color: Colors.white70,
                    height: 1.4,
                  ),
                ),
              ),
              trailing: IconButton(
                icon: const Icon(Icons.bookmark_add_outlined, color: Colors.purpleAccent),
                onPressed: () => saveVocabularyToDB(word),
              ),
            ),
          );
        }).toList(),
      ],
    );
  }

  Widget buildGenreChip(String genre) {
    final bool isSelected = selectedGenre == genre;

    return GestureDetector(
      onTap: () {
        setState(() {
          selectedGenre = genre;
        });
      },
      child: Container(
        margin: const EdgeInsets.only(right: 10),
        padding: const EdgeInsets.symmetric(
          horizontal: 18,
          vertical: 12,
        ),
        decoration: BoxDecoration(
          color: isSelected
              ? const Color(0xFF8B5CF6)
              : const Color(0xFF1A0B3A),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: Colors.white10,
          ),
        ),
        child: Text(
          genre,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.white70,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }

  // ---------- 장면 화면 ----------
  Widget _sceneCard(Map<String, dynamic> scene, int number) {
    final isEnding = scene['is_ending'] == true;
    final choices = ((scene['choices'] as List?) ?? []).cast<dynamic>();
    final rawIndex = scene['chosen_index'];
    final int chosenIndex = rawIndex is int ? rawIndex : -1;
    final chosen = (chosenIndex >= 0 && chosenIndex < choices.length)
        ? choices[chosenIndex].toString()
        : '';
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isEnding ? const Color(0xFFFBBF24) : Colors.white10,
          width: isEnding ? 1.5 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(
              color: isEnding
                  ? const Color(0xFFFBBF24).withOpacity(0.18)
                  : Colors.purple.withOpacity(0.22),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Text(
              isEnding ? '🌙 마지막 장면' : '📖 장면 $number',
              style: TextStyle(
                color: isEnding ? const Color(0xFFFBBF24) : Colors.purpleAccent,
                fontSize: 13,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(height: 14),
          buildClickableStoryText((scene['text'] ?? '').toString()),
          if (chosen.isNotEmpty) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: _choiceColors[chosenIndex % _choiceColors.length]
                      .map((c) => c.withOpacity(0.25))
                      .toList(),
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                '${_choiceEmojis[chosenIndex % _choiceEmojis.length]} 내가 고른 길: $chosen',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _loadingCard() {
    final message = _loadingMessages[_loadingIndex % _loadingMessages.length];
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.symmetric(vertical: 34, horizontal: 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            const Color(0xFF8B5CF6).withOpacity(0.25),
            const Color(0xFFEC4899).withOpacity(0.25),
          ],
        ),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        children: [
          const SizedBox(
            width: 42,
            height: 42,
            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 4),
          ),
          const SizedBox(height: 18),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 400),
            child: Text(
              message,
              key: ValueKey(message),
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _choiceButton(int index, String label) {
    final colors = _choiceColors[index % _choiceColors.length];
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(22),
          onTap: isBusy ? null : () => chooseOption(index),
          child: Ink(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: colors),
              borderRadius: BorderRadius.circular(22),
              boxShadow: [
                BoxShadow(
                  color: colors.first.withOpacity(0.35),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                Text(_choiceEmojis[index % _choiceEmojis.length],
                    style: const TextStyle(fontSize: 28)),
                const SizedBox(width: 14),
                Expanded(
                  child: Text(
                    label,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      height: 1.3,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _choicesArea() {
    final last = scenes.last;
    final choices = ((last['choices'] as List?) ?? []).map((e) => e.toString()).toList();
    final willEnd = scenes.length + 1 >= maxScenes;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          willEnd ? '마지막 선택이에요! 어떻게 할까요? 🌟' : '다음엔 어떻게 될까요? 골라 보세요! 🧭',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 22,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          '장면 ${scenes.length} / $maxScenes',
          style: const TextStyle(color: Colors.white54, fontSize: 14),
        ),
        const SizedBox(height: 16),
        for (var i = 0; i < choices.length; i++) _choiceButton(i, choices[i]),
        const SizedBox(height: 4),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFFFBBF24),
              side: const BorderSide(color: Color(0xFFFBBF24), width: 2),
              padding: const EdgeInsets.symmetric(vertical: 18),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
            ),
            onPressed: isBusy ? null : finishStory,
            icon: const Text('🌙', style: TextStyle(fontSize: 22)),
            label: const Text(
              '이야기 마무리하기',
              style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
            ),
          ),
        ),
      ],
    );
  }

  Widget _completedArea() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Center(
          child: Text(
            '✨ 끝 ✨',
            style: TextStyle(
              color: Color(0xFFFBBF24),
              fontSize: 26,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        const SizedBox(height: 18),
        // 🔊 동화 듣기 + 🌐 커뮤니티 공유 버튼 (한 줄에 나란히)
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: isPlayingTTS
                      ? const Color(0xFF5B21B6)
                      : const Color(0xFF8B5CF6),
                  padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: playTTS,
                icon: Icon(
                  isPlayingTTS ? Icons.pause_circle_filled : Icons.volume_up_rounded,
                  color: Colors.white,
                ),
                label: Text(
                  isPlayingTTS ? '동화 읽어주는 중...' : '동화 듣기',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF8B5CF6),
                  padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: (storyId.isEmpty || isSharing) ? null : shareStoryToCommunity,
                icon: const Icon(Icons.share, color: Colors.white),
                label: const Text(
                  '커뮤니티에 이 동화 공유하기',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 30),
        buildVocabulary(),
      ],
    );
  }

  Widget _storyView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                isCompleted && storyTitle.isNotEmpty
                    ? storyTitle
                    : (promptController.text.trim().isEmpty
                        ? '나의 동화'
                        : promptController.text.trim()),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            TextButton.icon(
              onPressed: isBusy ? null : resetStory,
              icon: const Icon(Icons.add_circle_outline, color: Colors.purpleAccent),
              label: const Text('새 동화',
                  style: TextStyle(color: Colors.purpleAccent, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
        const SizedBox(height: 6),
        const Text(
          '💡 궁금한 단어를 터치해 보세요!',
          style: TextStyle(
            color: Colors.purpleAccent,
            fontSize: 13,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 16),
        for (var i = 0; i < scenes.length; i++) _sceneCard(scenes[i], i + 1),
        if (isBusy)
          _loadingCard()
        else if (isCompleted)
          _completedArea()
        else
          _choicesArea(),
      ],
    );
  }

  Widget _setupForm() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '어떤 이야기를 원하시나요?',
          style: TextStyle(
            color: Colors.white,
            fontSize: 34,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          '첫 장면을 만들고, 다음 이야기는 직접 골라 가며 만들어요!',
          style: TextStyle(color: Colors.white54, fontSize: 15),
        ),
        const SizedBox(height: 30),
        const Text(
          '장르 선택',
          style: TextStyle(color: Colors.white70, fontSize: 18),
        ),
        const SizedBox(height: 16),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: genres.map((genre) => buildGenreChip(genre)).toList(),
          ),
        ),
        const SizedBox(height: 34),
        const Text(
          '주인공 설정',
          style: TextStyle(color: Colors.white70, fontSize: 18),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: promptController,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            hintText: '예: 용감한 꼬마 마법사',
            hintStyle: const TextStyle(color: Colors.white38),
            filled: true,
            fillColor: const Color(0xFF1A0B3A),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(20),
              borderSide: BorderSide.none,
            ),
          ),
        ),
        const SizedBox(height: 30),
        const Text(
          '아이 연령대',
          style: TextStyle(color: Colors.white70, fontSize: 18),
        ),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: const Color(0xFF1A0B3A),
            borderRadius: BorderRadius.circular(20),
          ),
          child: DropdownButton<String>(
            value: selectedAge,
            dropdownColor: const Color(0xFF1A0B3A),
            isExpanded: true,
            underline: const SizedBox(),
            style: const TextStyle(color: Colors.white),
            items: ages
                .map((age) => DropdownMenuItem(value: age, child: Text(age)))
                .toList(),
            onChanged: (value) {
              setState(() {
                selectedAge = value!;
              });
            },
          ),
        ),
        const SizedBox(height: 40),
        if (isBusy)
          _loadingCard()
        else
          GestureDetector(
            onTap: startStory,
            child: Container(
              width: double.infinity,
              height: 72,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                ),
                borderRadius: BorderRadius.circular(24),
              ),
              child: const Center(
                child: Text(
                  '동화 시작하기 ✨',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final name = widget.displayName.trim();
    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF070018),
        elevation: 0,
        foregroundColor: Colors.white,
        title: Text(
          name.isEmpty ? '나의 동화' : '$name님의 동화',
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'story',
        displayName: widget.displayName,
      ),
      body: isOpening
          ? const Center(child: CircularProgressIndicator(color: Colors.purpleAccent))
          : SingleChildScrollView(
              controller: _scrollController,
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  hasStory ? _storyView() : _setupForm(),
                  const SizedBox(height: 80),
                ],
              ),
            ),
    );
  }
}
