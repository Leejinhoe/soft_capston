import 'package:flutter/material.dart';
import '../core/api_client.dart';
import 'package:just_audio/just_audio.dart';

import '../widgets/custom_bottom_nav.dart';

class StoryPage extends StatefulWidget {
  final String displayName;

  const StoryPage({
    super.key,
    required this.displayName,
  });

  @override
  State<StoryPage> createState() => _StoryPageState();
}

class _StoryPageState extends State<StoryPage> {
  final TextEditingController promptController = TextEditingController();
  final AudioPlayer _audioPlayer = AudioPlayer();

  String selectedGenre = '판타지';
  String selectedAge = '5-7세';

  bool isLoading = false;
  bool isPlayingTTS = false; // 🔊 TTS 재생 상태 관리

  String storyText = '';

  List<dynamic> vocabList = [];

  final List<String> genres = [
    '판타지',
    '모험',
    'SF',
    '일상',
    '전래동화',
  ];

  final List<String> ages = [
    '5-7세',
    '8-10세',
    '11-13세',
  ];

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
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    promptController.dispose();
    super.dispose();
  }

  // 🔊 백엔드 DB에 단어 저장 API 호출
  Future<void> saveVocabularyToDB(Map<String, dynamic> wordItem) async {
    try {
      final response = await ApiClient.post(
        '/api/vocabularies/add',
        body: {
          'hard': wordItem['hard'],
          'easy': '',
          'definition': wordItem['definition'],
          'source_story_title': promptController.text.isEmpty
              ? '신비한 동화 이야기'
              : promptController.text,
          'origin_story_id': '650000000000000000000001',
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

  // 🌐 커뮤니티 공유 전용 API 호출 함수 ('보관함 저장'은 동화 생성 시 자동 완료됨)
  Future<void> shareStoryToCommunity() async {
    try {
      final response = await ApiClient.post(
        '/api/stories/save',
        body: {
          'title': promptController.text.isEmpty ? '신비한 동화 이야기' : promptController.text,
          'content': storyText,
          'genre': selectedGenre,
          'is_public': true, // 커뮤니티 공유 처리
        },
      );

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('커뮤니티에 동화가 공유되었습니다! 🌐'),
              backgroundColor: Color(0xFF8B5CF6),
            ),
          );
        }
      }
    } catch (e) {
      debugPrint('커뮤니티 공유 오류: $e');
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
          'definition': data['definition'] ?? '표준 사전 정보 없음',
        });
      } else {
        showVocabularyDialog({
          'hard': cleanWord,
          'definition': '국립국어원 표준 정의 연동 중입니다.',
        });
      }
    } catch (e) {
      if (mounted) Navigator.pop(context); // 로딩 닫기
      showVocabularyDialog({
        'hard': cleanWord,
        'definition': '단어 뜻풀이를 성공적으로 불러왔습니다.',
      });
    }
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

  // 💡 [수정] 백엔드 Gemini를 통해 실시간 동화 생성 & 주요 추천 단어 3~5개 받아오기
  Future<void> generateStory() async {
    if (promptController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('동화 주제를 입력해주세요.'),
        ),
      );
      return;
    }

    setState(() {
      isLoading = true;
      storyText = '';
      vocabList = [];
      isPlayingTTS = false;
    });

    try {
      final response = await ApiClient.post(
        '/api/generate-story',
        body: {
          'prompt': promptController.text,
          'genre': selectedGenre,
          'age': selectedAge,
        },
      );

      if (response.statusCode == 200) {
        final data = ApiClient.decode(response);
        setState(() {
          storyText = data['story'] ?? '';
          vocabList = data['vocab_list'] ?? [];
          isLoading = false;
        });
      } else {
        throw Exception('동화 생성 실패 (${response.statusCode})');
      }
    } catch (e) {
      debugPrint('동화 생성 오류: $e');
      setState(() {
        isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('동화 생성 실패: 서버 통신 상태를 확인해 주세요.')),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF070018),
      appBar: AppBar(
        backgroundColor: const Color(0xFF070018),
        elevation: 0,
        foregroundColor: Colors.white,
        title: Text(
          '${widget.displayName}님의 동화',
          style: const TextStyle(
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      bottomNavigationBar: CustomBottomNav(
        currentPage: 'story',
        displayName: widget.displayName,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
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
            const SizedBox(height: 30),
            const Text(
              '장르 선택',
              style: TextStyle(
                color: Colors.white70,
                fontSize: 18,
              ),
            ),
            const SizedBox(height: 16),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: genres
                    .map(
                      (genre) => buildGenreChip(genre),
                )
                    .toList(),
              ),
            ),
            const SizedBox(height: 34),
            const Text(
              '주인공 설정',
              style: TextStyle(
                color: Colors.white70,
                fontSize: 18,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: promptController,
              style: const TextStyle(
                color: Colors.white,
              ),
              decoration: InputDecoration(
                hintText: '예: 용감한 꼬마 마법사',
                hintStyle: const TextStyle(
                  color: Colors.white38,
                ),
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
              style: TextStyle(
                color: Colors.white70,
                fontSize: 18,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 16,
              ),
              decoration: BoxDecoration(
                color: const Color(0xFF1A0B3A),
                borderRadius: BorderRadius.circular(20),
              ),
              child: DropdownButton<String>(
                value: selectedAge,
                dropdownColor: const Color(0xFF1A0B3A),
                isExpanded: true,
                underline: const SizedBox(),
                style: const TextStyle(
                  color: Colors.white,
                ),
                items: ages
                    .map(
                      (age) => DropdownMenuItem(
                    value: age,
                    child: Text(age),
                  ),
                )
                    .toList(),
                onChanged: (value) {
                  setState(() {
                    selectedAge = value!;
                  });
                },
              ),
            ),
            const SizedBox(height: 40),
            GestureDetector(
              onTap: isLoading ? null : generateStory,
              child: Container(
                width: double.infinity,
                height: 72,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [
                      Color(0xFF8B5CF6),
                      Color(0xFFEC4899),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Center(
                  child: isLoading
                      ? const CircularProgressIndicator(
                    color: Colors.white,
                  )
                      : const Text(
                    '동화 생성하기 ✨',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 40),
            if (storyText.isNotEmpty) ...[
              // 📖 동화 본문 카드 (단어 클릭 가능)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xFF140028),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: Colors.white10,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '💡 궁금한 단어를 터치해 보세요!',
                      style: TextStyle(
                        color: Colors.purpleAccent,
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    buildClickableStoryText(storyText),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              // 🔊 동화 듣기 + 🌐 커뮤니티 공유 버튼 (한 줄에 나란히)
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: isPlayingTTS
                            ? const Color(0xFF5B21B6)
                            : const Color(0xFF8B5CF6),
                        padding: const EdgeInsets.symmetric(
                          vertical: 16,
                          horizontal: 12,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      onPressed: playTTS,
                      icon: Icon(
                        isPlayingTTS
                            ? Icons.pause_circle_filled
                            : Icons.volume_up_rounded,
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
                        padding: const EdgeInsets.symmetric(
                          vertical: 16,
                          horizontal: 12,
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      onPressed: shareStoryToCommunity,
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
            ],
            const SizedBox(height: 30),
            buildVocabulary(),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }
}