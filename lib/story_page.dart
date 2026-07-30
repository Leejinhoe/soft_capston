import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:percent_indicator/percent_indicator.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import 'main.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'psych_page.dart';
import 'services/db_service.dart';
import 'widgets/story_cast_widget.dart';

enum _NarrationTarget { currentChapter, fullStory }

const _voiceSampleScript = '안녕하세요. 저는 따뜻한 목소리로 동화를 읽어요. '
    '별빛이 반짝이는 숲에서 작은 토끼가 용기를 냈어요. '
    '친구와 함께라면 어려운 길도 즐겁게 갈 수 있어요.';

class _VocabTextMatch {
  final int start;
  final int end;
  final VocabWord word;

  const _VocabTextMatch({
    required this.start,
    required this.end,
    required this.word,
  });
}

class StoryPage extends StatefulWidget {
  final StorySession? preloadedStory;
  const StoryPage({super.key, this.preloadedStory});

  @override
  State<StoryPage> createState() => _StoryPageState();
}

class _StoryPageState extends State<StoryPage> {
  bool _showVocab = false;
  final _scrollCtrl = ScrollController();
  final AudioPlayer _narrationPlayer = AudioPlayer();
  final AudioRecorder _voiceRecorder = AudioRecorder();
  StreamSubscription<void>? _ttsCompletionSubscription;
  StreamSubscription<Uint8List>? _voiceRecordingSubscription;
  final BytesBuilder _voicePcm = BytesBuilder(copy: false);
  Timer? _voiceRecordingTimer;
  int _ttsRequestNumber = 0;

  bool _ttsReady = false;
  bool _ttsInitializing = true;
  bool _ttsSpeaking = false;
  bool _isRecordingVoice = false;
  int _voiceRecordSeconds = 0;
  Uint8List? _recordedVoiceWav;
  String _ttsStatus = '낭독 준비 중';
  _NarrationTarget? _activeNarrationTarget;

  @override
  void initState() {
    super.initState();
    _initTts();
  }

  @override
  void dispose() {
    _ttsRequestNumber++;
    _ttsCompletionSubscription?.cancel();
    _voiceRecordingTimer?.cancel();
    _voiceRecordingSubscription?.cancel();
    _voiceRecorder.dispose();
    _narrationPlayer.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _initTts() async {
    try {
      await _narrationPlayer.setReleaseMode(ReleaseMode.stop);
      _ttsCompletionSubscription = _narrationPlayer.onPlayerComplete.listen((
        _,
      ) {
        if (!mounted) return;
        setState(() {
          _ttsSpeaking = false;
          _ttsStatus = '낭독이 끝났어요';
          _activeNarrationTarget = null;
        });
      });

      if (!mounted) return;
      setState(() {
        _ttsReady = true;
        _ttsInitializing = false;
        _ttsStatus = '자연스러운 한국어 낭독 준비 완료';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _ttsReady = false;
        _ttsInitializing = false;
        _ttsSpeaking = false;
        _ttsStatus = '서버 낭독을 준비하지 못했어요';
        _activeNarrationTarget = null;
      });
    }
  }

  String _cleanTtsText(String text) {
    return text
        .replaceAll(RegExp(r'[❤💖✨❤️]'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  String get _voiceRecordingTime {
    final minutes = (_voiceRecordSeconds ~/ 60).toString().padLeft(2, '0');
    final seconds = (_voiceRecordSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  Uint8List _pcm16ToWav(Uint8List pcm, {int sampleRate = 24000}) {
    const channels = 1;
    const bytesPerSample = 2;
    final wav = Uint8List(44 + pcm.length);
    final header = ByteData.sublistView(wav);

    void writeAscii(int offset, String value) {
      for (var i = 0; i < value.length; i++) {
        header.setUint8(offset + i, value.codeUnitAt(i));
      }
    }

    writeAscii(0, 'RIFF');
    header.setUint32(4, 36 + pcm.length, Endian.little);
    writeAscii(8, 'WAVE');
    writeAscii(12, 'fmt ');
    header.setUint32(16, 16, Endian.little);
    header.setUint16(20, 1, Endian.little);
    header.setUint16(22, channels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(28, sampleRate * channels * bytesPerSample, Endian.little);
    header.setUint16(32, channels * bytesPerSample, Endian.little);
    header.setUint16(34, bytesPerSample * 8, Endian.little);
    writeAscii(36, 'data');
    header.setUint32(40, pcm.length, Endian.little);
    wav.setRange(44, wav.length, pcm);
    return wav;
  }

  Future<void> _startVoiceRecording() async {
    try {
      if (!await _voiceRecorder.hasPermission()) {
        throw Exception('마이크 권한이 필요해요. 브라우저 또는 기기 설정에서 허용해 주세요.');
      }

      await _stopTts();
      _voicePcm.clear();
      _voiceRecordSeconds = 0;
      final stream = await _voiceRecorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 24000,
          numChannels: 1,
        ),
      );
      _voiceRecordingSubscription = stream.listen(
        _voicePcm.add,
        onError: (Object error) {
          if (!mounted) return;
          setState(() {
            _isRecordingVoice = false;
            _ttsStatus = '녹음 오류: $error';
          });
        },
      );
      _voiceRecordingTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted || !_isRecordingVoice) return;
        if (_voiceRecordSeconds >= 20) {
          unawaited(_stopVoiceRecording());
          return;
        }
        setState(() {
          _voiceRecordSeconds++;
          _ttsStatus = '내 목소리를 녹음하고 있어요 ($_voiceRecordingTime / 00:20)';
        });
      });

      if (!mounted) return;
      setState(() {
        _isRecordingVoice = true;
        _ttsStatus = '내 목소리를 녹음하고 있어요 (00:00 / 00:20)';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _isRecordingVoice = false;
        _ttsStatus = '녹음을 시작하지 못했어요: $error';
      });
    }
  }

  Future<void> _stopVoiceRecording() async {
    if (!_isRecordingVoice) return;
    _voiceRecordingTimer?.cancel();
    _voiceRecordingTimer = null;
    try {
      await _voiceRecorder.stop();
      await _voiceRecordingSubscription?.cancel();
      _voiceRecordingSubscription = null;
      final pcm = _voicePcm.takeBytes();
      const minimumBytes = 24000 * 2 * 3;
      if (pcm.length < minimumBytes) {
        throw Exception('목소리를 3초 이상 녹음해 주세요.');
      }
      final wav = _pcm16ToWav(pcm);
      if (!mounted) return;
      setState(() {
        _recordedVoiceWav = wav;
        _isRecordingVoice = false;
        _ttsStatus = '내 목소리 샘플이 준비됐어요. 낭독 버튼을 눌러 들어보세요.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _isRecordingVoice = false;
        _ttsStatus = '녹음을 저장하지 못했어요: $error';
      });
    }
  }

  Future<void> _toggleVoiceRecording() {
    return _isRecordingVoice ? _stopVoiceRecording() : _startVoiceRecording();
  }

  Future<void> _speakText(String text, _NarrationTarget target) async {
    final cleaned = _cleanTtsText(text);
    if (!_ttsReady || cleaned.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(cleaned.isEmpty ? '읽을 내용이 아직 없어요.' : '낭독을 준비하지 못했어요.'),
          backgroundColor: Colors.red.shade700,
        ),
      );
      return;
    }

    final requestNumber = ++_ttsRequestNumber;
    await _narrationPlayer.stop();
    if (!mounted) return;
    setState(() {
      _activeNarrationTarget = target;
      _ttsSpeaking = false;
      _ttsStatus = '자연스러운 목소리를 만들고 있어요';
    });

    try {
      final audioBytes = await DbService.synthesizeNarration(
        cleaned,
        speakerWav: _recordedVoiceWav,
      );
      if (!mounted || requestNumber != _ttsRequestNumber) return;
      await _narrationPlayer.play(BytesSource(audioBytes));
      if (!mounted || requestNumber != _ttsRequestNumber) return;
      setState(() {
        _ttsSpeaking = true;
        final scope = target == _NarrationTarget.fullStory ? '전체 이야기' : '현재 장';
        _ttsStatus =
            _recordedVoiceWav == null ? '$scope을 읽는 중' : '내 목소리로 $scope을 읽는 중';
      });
    } catch (error) {
      if (!mounted || requestNumber != _ttsRequestNumber) return;
      setState(() {
        _ttsSpeaking = false;
        _ttsStatus = '낭독 오류: $error';
        _activeNarrationTarget = null;
      });
    }
  }

  Future<void> _stopTts() async {
    _ttsRequestNumber++;
    await _narrationPlayer.stop();
    if (!mounted) return;
    setState(() {
      _ttsSpeaking = false;
      _ttsStatus = '낭독이 멈췄어요';
      _activeNarrationTarget = null;
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 600),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final story = widget.preloadedStory ?? state.currentStory;

    if (story == null) {
      return Scaffold(
        backgroundColor: AppColors.bg,
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text('📖', style: TextStyle(fontSize: 48)),
              const SizedBox(height: 16),
              const Text(
                '동화가 없어요',
                style: TextStyle(color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('돌아가기'),
              ),
            ],
          ),
        ),
      );
    }
    if (story.chapters.isEmpty) {
      return Scaffold(
        backgroundColor: AppColors.bg,
        appBar: AppBar(
          backgroundColor: AppColors.bg,
          foregroundColor: Colors.white,
          title: Text(story.initialPrompt),
        ),
        body: const Center(
          child: Text(
            '아직 생성된 장면이 없습니다.',
            style: TextStyle(color: Colors.white70),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Stack(
        children: [
          _buildBackground(),
          SafeArea(
            child: Column(
              children: [
                _buildHeader(context, story),
                Expanded(
                  child: SingleChildScrollView(
                    controller: _scrollCtrl,
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildChapterInfo(story),
                        if (story.effectiveStoryCast.isNotEmpty) ...[
                          const SizedBox(height: 10),
                          StoryCastWidget(members: story.effectiveStoryCast),
                        ],
                        const SizedBox(height: 16),
                        _buildTtsPanel(story),
                        const SizedBox(height: 16),
                        if (story.candidateVocab.isNotEmpty) ...[
                          _buildDifficultWordGuide(story),
                          const SizedBox(height: 16),
                        ],
                        _buildStoryEmotionGraph(story),
                        const SizedBox(height: 16),
                        ...story.chapters.map(
                          (chapter) => _buildChapterCard(
                            context,
                            state,
                            story,
                            chapter,
                            story.chapters.length,
                          ),
                        ),
                        if (state.isLoading) _buildLoadingCard(),
                        if (!state.isLoading &&
                            widget.preloadedStory == null) ...[
                          const SizedBox(height: 24),
                          if (story.choices.isNotEmpty)
                            _buildChoices(context, story, state)
                          else
                            _buildStoryCompleteCard(context, state),
                        ],
                        if (story.vocab.isNotEmpty) ...[
                          const SizedBox(height: 24),
                          _buildVocabSection(story.vocab),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBackground() {
    return Positioned.fill(
      child: Container(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.5),
            radius: 1.0,
            colors: [Color(0xFF160B3C), Color(0xFF06041A)],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, StorySession story) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: () {
              if (widget.preloadedStory != null) {
                Navigator.pop(context);
              } else {
                _showExitDialog(context);
              }
            },
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.arrow_back_ios_rounded,
                color: Colors.white,
                size: 16,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  story.initialPrompt,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  '${story.genre} · ${_ageLabel(story.age)}',
                  style: const TextStyle(color: AppColors.gray, fontSize: 11),
                ),
              ],
            ),
          ),
          if (widget.preloadedStory == null)
            GestureDetector(
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const PsychPage()),
              ),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: AppColors.pink.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: AppColors.pink.withValues(alpha: 0.4),
                  ),
                ),
                child: const Text(
                  '🧠 분석',
                  style: TextStyle(
                    color: AppColors.pink,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: story.fullStoryText));
              if (!context.mounted) return;
              ScaffoldMessenger.of(
                context,
              ).showSnackBar(const SnackBar(content: Text('전체 동화 내용을 복사했어요.')));
            },
            icon: const Icon(Icons.copy_rounded),
            color: AppColors.gray2,
            tooltip: '동화 복사',
          ),
        ],
      ),
    );
  }

  Widget _buildChapterInfo(StorySession story) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          _buildMetaBadge(
            'Chapter ${story.currentChapter}',
            AppColors.p700.withValues(alpha: 0.4),
            AppColors.p300,
          ),
          _buildMetaBadge(
            '선택 ${story.allChoicesMade.length}회',
            AppColors.teal.withValues(alpha: 0.15),
            AppColors.teal,
          ),
          if (story.chapters.last.storyEmotion != null)
            _buildMetaBadge(
              '현재 감정 ${story.chapters.last.storyEmotion!.primaryEmotionDisplay}',
              AppColors.pink.withValues(alpha: 0.15),
              AppColors.pink2,
            ),
        ],
      ),
    );
  }

  Widget _buildMetaBadge(String text, Color bg, Color fg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: TextStyle(color: fg, fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildTtsPanel(StorySession story) {
    final currentChapterText = story.chapters.last.text;
    final statusColor = _ttsStatus.startsWith('낭독 오류')
        ? AppColors.pink2
        : _ttsReady
            ? AppColors.teal
            : AppColors.gray;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🔊', style: TextStyle(fontSize: 18)),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  '동화 낭독',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              if (_isRecordingVoice)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.pink2.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Text(
                    '녹음 중',
                    style: TextStyle(
                      color: AppColors.pink2,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                )
              else if (_ttsSpeaking)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.teal.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Text(
                    '재생 중',
                    style: TextStyle(
                      color: AppColors.teal,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _ttsInitializing ? '낭독 엔진을 준비하고 있어요…' : _ttsStatus,
            style: TextStyle(
              color: statusColor,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
          if (_recordedVoiceWav == null || _isRecordingVoice) ...[
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.pink2.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: AppColors.pink2.withValues(alpha: 0.28),
                ),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.record_voice_over_outlined,
                    color: AppColors.pink2,
                    size: 20,
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          '따라 읽어보세요',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          _voiceSampleScript,
                          style: TextStyle(
                            color: AppColors.gray,
                            fontSize: 12,
                            height: 1.45,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: '문장 복사',
                    onPressed: () async {
                      await Clipboard.setData(
                        const ClipboardData(text: _voiceSampleScript),
                      );
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('따라 읽기 문장을 복사했어요.')),
                      );
                    },
                    icon: const Icon(Icons.copy_rounded, size: 18),
                    color: AppColors.pink2,
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _ttsInitializing
                      ? null
                      : () => _speakText(
                            currentChapterText,
                            _NarrationTarget.currentChapter,
                          ),
                  icon: const Icon(Icons.play_arrow_rounded, size: 18),
                  label: const Text('현재 장'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _ttsInitializing
                      ? null
                      : () => _speakText(
                            story.fullStoryText,
                            _NarrationTarget.fullStory,
                          ),
                  icon: const Icon(Icons.menu_book_rounded, size: 18),
                  label: const Text('전체'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.p300,
                    side: const BorderSide(color: AppColors.border),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _ttsInitializing ? null : _toggleVoiceRecording,
                  icon: Icon(
                    _isRecordingVoice
                        ? Icons.stop_circle_outlined
                        : Icons.mic_none_rounded,
                    size: 18,
                  ),
                  label: Text(_isRecordingVoice ? '녹음 완료' : '내 목소리'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.pink2,
                    side: BorderSide(
                      color: _recordedVoiceWav == null
                          ? AppColors.border
                          : AppColors.pink2,
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: TextButton.icon(
              onPressed: _ttsSpeaking || _activeNarrationTarget != null
                  ? _stopTts
                  : null,
              icon: const Icon(Icons.stop_rounded, size: 18),
              label: const Text('낭독 멈추기'),
              style: TextButton.styleFrom(
                foregroundColor: AppColors.pink2,
                padding: const EdgeInsets.symmetric(vertical: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDifficultWordGuide(StorySession story) {
    final wordsInStory = story.candidateVocab
        .where((word) => story.fullStoryText.contains(word.hard))
        .map((word) => word.hard)
        .toSet()
        .length;
    if (wordsInStory == 0) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.teal.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.teal.withValues(alpha: 0.32)),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppColors.teal.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              Icons.touch_app_rounded,
              color: AppColors.teal,
              size: 22,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '밑줄 친 단어를 눌러 저장해요',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '이야기 속 어려운 단어 $wordsInStory개를 발견했어요. 필요한 단어만 단어장에 담을 수 있어요.',
                  style: const TextStyle(
                    color: AppColors.gray,
                    fontSize: 11,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStoryEmotionGraph(StorySession story) {
    final emotions = _aggregateStoryEmotions(story);
    if (emotions.isEmpty) return const SizedBox.shrink();

    const colors = [
      AppColors.p500,
      AppColors.pink,
      AppColors.teal,
      Color(0xFFF59E0B),
      Color(0xFF10B981),
    ];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF8B5CF6), Color(0xFFEC4899)],
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(
                  Icons.insights_rounded,
                  color: Colors.white,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '감정 그래프',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    SizedBox(height: 3),
                    Text(
                      '지금까지 이야기와 선택에서 감지된 감정이에요',
                      style: TextStyle(color: Colors.white70, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ...emotions.asMap().entries.map((entry) {
            final color = colors[entry.key % colors.length];
            final item = entry.value;
            final label =
                item.labelDisplay.isNotEmpty ? item.labelDisplay : item.label;
            final percent = item.score.clamp(0.0, 1.0);
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        label,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        '${(percent * 100).toStringAsFixed(0)}%',
                        style: TextStyle(
                          color: color,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  LinearPercentIndicator(
                    percent: percent,
                    lineHeight: 8,
                    barRadius: const Radius.circular(4),
                    backgroundColor: color.withValues(alpha: 0.15),
                    progressColor: color,
                    padding: EdgeInsets.zero,
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  List<EmotionScoreItem> _aggregateStoryEmotions(StorySession story) {
    final totals = <String, double>{};
    final counts = <String, int>{};
    final indexes = <String, int>{};
    final displays = <String, String>{};

    void collect(EmotionAnalysis? analysis) {
      if (analysis == null) return;
      for (final item in analysis.topEmotions.take(5)) {
        final key =
            item.labelDisplay.isNotEmpty ? item.labelDisplay : item.label;
        totals[key] = (totals[key] ?? 0) + item.score;
        counts[key] = (counts[key] ?? 0) + 1;
        indexes[key] = item.labelIndex;
        displays[key] = key;
      }
    }

    for (final chapter in story.chapters) {
      collect(chapter.storyEmotion);
      collect(chapter.selectedChoiceEmotion);
    }
    for (final option in story.choiceOptions) {
      collect(option.emotion);
    }

    final result = totals.entries.map((entry) {
      final count = counts[entry.key] ?? 1;
      final score = (entry.value / count).clamp(0.0, 1.0);
      return EmotionScoreItem(
        labelIndex: indexes[entry.key] ?? -1,
        label: entry.key,
        labelDisplay: displays[entry.key] ?? entry.key,
        score: double.parse(score.toStringAsFixed(3)),
      );
    }).toList()
      ..sort((a, b) => b.score.compareTo(a.score));

    return result.take(5).toList();
  }

  Widget _buildInteractiveStoryText({
    required BuildContext context,
    required AppState state,
    required StorySession story,
    required String text,
  }) {
    const baseStyle = TextStyle(
      color: Colors.white,
      fontSize: 15,
      height: 1.8,
      letterSpacing: 0.2,
    );
    final matches = _findVocabMatches(text, story.candidateVocab);
    if (matches.isEmpty) {
      return Text(text, style: baseStyle);
    }

    final spans = <InlineSpan>[];
    var cursor = 0;
    for (final match in matches) {
      if (match.start > cursor) {
        spans.add(TextSpan(text: text.substring(cursor, match.start)));
      }
      final saved = _isVocabSaved(story, match.word);
      spans.add(
        WidgetSpan(
          alignment: PlaceholderAlignment.baseline,
          baseline: TextBaseline.alphabetic,
          child: GestureDetector(
            onTap: () => _showVocabSaveSheet(context, state, story, match.word),
            child: Text(
              text.substring(match.start, match.end),
              style: TextStyle(
                color: Colors.white,
                fontSize: 15,
                height: 1.8,
                fontWeight: FontWeight.w600,
                decoration: TextDecoration.underline,
                decorationColor: saved ? AppColors.teal : AppColors.p300,
                decorationThickness: 1.3,
              ),
            ),
          ),
        ),
      );
      cursor = match.end;
    }
    if (cursor < text.length) {
      spans.add(TextSpan(text: text.substring(cursor)));
    }

    return RichText(
      text: TextSpan(style: baseStyle, children: spans),
    );
  }

  List<_VocabTextMatch> _findVocabMatches(String text, List<VocabWord> vocab) {
    final candidates = <_VocabTextMatch>[];
    final seenWords = <String>{};
    for (final word in vocab) {
      final target = word.hard.trim();
      if (target.isEmpty || !seenWords.add(target)) continue;
      var start = text.indexOf(target);
      while (start >= 0) {
        candidates.add(
          _VocabTextMatch(start: start, end: start + target.length, word: word),
        );
        start = text.indexOf(target, start + target.length);
      }
    }
    candidates.sort((a, b) {
      final byStart = a.start.compareTo(b.start);
      if (byStart != 0) return byStart;
      return (b.end - b.start).compareTo(a.end - a.start);
    });

    final filtered = <_VocabTextMatch>[];
    var cursor = 0;
    for (final match in candidates) {
      if (match.start < cursor) continue;
      filtered.add(match);
      cursor = match.end;
    }
    return filtered;
  }

  bool _isVocabSaved(StorySession story, VocabWord word) {
    return story.vocab.any(
      (saved) =>
          saved.hard == word.hard &&
          saved.easy == word.easy &&
          saved.definition == word.definition,
    );
  }

  Future<void> _showVocabSaveSheet(
    BuildContext context,
    AppState state,
    StorySession story,
    VocabWord word,
  ) async {
    final alreadySaved = _isVocabSaved(story, word);
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColors.card,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 20, 22, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: AppColors.teal.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: const Icon(
                        Icons.auto_stories_rounded,
                        color: AppColors.teal,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            word.hard,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            '쉬운 뜻: ${word.easy}',
                            style: const TextStyle(
                              color: AppColors.teal,
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  word.definition,
                  style: const TextStyle(
                    color: AppColors.gray,
                    fontSize: 13,
                    height: 1.55,
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: () async {
                      if (alreadySaved) {
                        Navigator.pop(sheetContext);
                        return;
                      }

                      final ok = await state.saveVocabularyFromStory(
                        story,
                        word,
                      );
                      if (!sheetContext.mounted) return;
                      Navigator.pop(sheetContext);
                      if (!context.mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(
                            ok ? '"${word.hard}" 단어를 저장했어요.' : '단어 저장에 실패했어요.',
                          ),
                        ),
                      );
                    },
                    icon: Icon(
                      alreadySaved
                          ? Icons.check_circle_rounded
                          : Icons.bookmark_add_rounded,
                    ),
                    label: Text(alreadySaved ? '단어장에 저장됨' : '단어장에 저장'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          alreadySaved ? AppColors.teal : AppColors.p600,
                      foregroundColor: Colors.white,
                      elevation: 2,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildChapterCard(
    BuildContext context,
    AppState state,
    StorySession story,
    StoryChapter chapter,
    int totalChapters,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (chapter.choiceMade != null) ...[
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: AppColors.pink.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.pink.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Text('👉', style: TextStyle(fontSize: 14)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    chapter.choiceMade!,
                    style: const TextStyle(
                      color: AppColors.pink2,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ] else
          const SizedBox(height: 12),
        if (chapter.imageB64 != null) ...[
          _buildStoryImage(chapter.imageB64!),
          const SizedBox(height: 12),
        ] else if (_isRemoteMediaUrl(chapter.imageUrl)) ...[
          _buildNetworkStoryImage(chapter.imageUrl!),
          const SizedBox(height: 12),
        ] else if (chapter.imageUrl?.startsWith('mock://image/') == true) ...[
          _buildTemporaryStoryImage(chapter),
          const SizedBox(height: 12),
        ],
        if (_isRemoteMediaUrl(chapter.videoUrl)) ...[
          _buildGeneratedVideoCard(chapter.videoUrl!),
          const SizedBox(height: 12),
        ] else if (chapter.videoUrl?.startsWith('mock://video/') == true) ...[
          _buildTemporaryVideoCard(chapter),
          const SizedBox(height: 12),
        ],
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildInteractiveStoryText(
                context: context,
                state: state,
                story: story,
                text: chapter.text,
              ),
              if (chapter.selectedChoiceEmotion != null) ...[
                const SizedBox(height: 18),
                _buildEmotionPanel(
                  title: '선택한 감정',
                  subtitle: chapter.choiceMade ?? '',
                  analysis: chapter.selectedChoiceEmotion!,
                  accent: AppColors.pink,
                  emoji: '🎯',
                ),
              ],
              if (chapter.storyEmotion != null) ...[
                const SizedBox(height: 18),
                _buildEmotionPanel(
                  title: '이야기 감정',
                  subtitle: '이 장면의 분위기',
                  analysis: chapter.storyEmotion!,
                  accent: AppColors.teal,
                  emoji: '📈',
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStoryImage(String imageB64) {
    try {
      final bytes = base64Decode(imageB64);
      return Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 280),
          child: Container(
            decoration: BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.border),
              boxShadow: [
                BoxShadow(
                  color: AppColors.p700.withValues(alpha: 0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(16),
                  ),
                  child: AspectRatio(
                    aspectRatio: 1.0,
                    child: Image.memory(
                      bytes,
                      fit: BoxFit.contain,
                      gaplessPlayback: true,
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  child: Row(
                    children: [
                      const Text('🎨', style: TextStyle(fontSize: 12)),
                      const SizedBox(width: 6),
                      const Text(
                        'AI 삽화',
                        style: TextStyle(
                          color: AppColors.teal,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        'Dreamshaper 8',
                        style: TextStyle(
                          color: AppColors.gray.withValues(alpha: 0.6),
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (_) {
      return const SizedBox.shrink();
    }
  }

  bool _isRemoteMediaUrl(String? value) {
    final trimmed = value?.trim();
    if (trimmed == null || trimmed.isEmpty) return false;
    return trimmed.startsWith('http://') || trimmed.startsWith('https://');
  }

  Widget _buildNetworkStoryImage(String imageUrl) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 280),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
            boxShadow: [
              BoxShadow(
                color: AppColors.p700.withValues(alpha: 0.3),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ClipRRect(
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(16),
                ),
                child: AspectRatio(
                  aspectRatio: 1.0,
                  child: Image.network(
                    imageUrl,
                    fit: BoxFit.cover,
                    loadingBuilder: (context, child, loadingProgress) {
                      if (loadingProgress == null) return child;
                      return Container(
                        color: AppColors.card2,
                        alignment: Alignment.center,
                        child: const CircularProgressIndicator(
                          color: AppColors.p400,
                          strokeWidth: 2,
                        ),
                      );
                    },
                    errorBuilder: (context, error, stackTrace) {
                      return Container(
                        color: AppColors.card2,
                        alignment: Alignment.center,
                        padding: const EdgeInsets.all(20),
                        child: const Text(
                          '이미지를 불러오지 못했어요',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: AppColors.gray,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 8,
                ),
                child: Row(
                  children: [
                    const Text('🖼', style: TextStyle(fontSize: 12)),
                    const SizedBox(width: 6),
                    const Text(
                      '생성 이미지',
                      style: TextStyle(
                        color: AppColors.teal,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                    Flexible(
                      child: Text(
                        Uri.tryParse(imageUrl)?.host ?? 'remote',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.right,
                        style: TextStyle(
                          color: AppColors.gray.withValues(alpha: 0.6),
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTemporaryStoryImage(StoryChapter chapter) {
    final palette = [
      [AppColors.p700, AppColors.pink],
      [AppColors.teal, AppColors.p600],
      [const Color(0xFFFFB86B), AppColors.p700],
    ][chapter.chapter % 3];
    final symbols = ['🌙', '🗺️', '🌿', '🦊', '🔮', '🦋'];
    final symbol = symbols[chapter.chapter % symbols.length];

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 300),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppColors.border),
            boxShadow: [
              BoxShadow(
                color: palette.first.withValues(alpha: 0.35),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(18),
            child: AspectRatio(
              aspectRatio: 1,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            palette.first.withValues(alpha: 0.95),
                            palette.last.withValues(alpha: 0.72),
                            AppColors.card,
                          ],
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    top: 22,
                    right: 18,
                    child: Text(symbol, style: const TextStyle(fontSize: 58)),
                  ),
                  Positioned(
                    left: -26,
                    bottom: -18,
                    child: Container(
                      width: 140,
                      height: 140,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white.withValues(alpha: 0.12),
                      ),
                    ),
                  ),
                  Positioned(
                    left: 18,
                    right: 18,
                    bottom: 18,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 5,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.22),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            '임시 삽화 · ${chapter.chapter}장',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          chapter.text.split('\n').first,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            height: 1.35,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTemporaryVideoCard(StoryChapter chapter) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.p400.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.p600.withValues(alpha: 0.25),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              Icons.play_arrow_rounded,
              color: Colors.white,
              size: 30,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '임시 영상 콘티',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${chapter.chapter}장 장면을 짧은 애니메이션으로 만들 수 있는 자리예요.',
                  style: const TextStyle(
                    color: AppColors.gray,
                    fontSize: 11,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          const Icon(Icons.movie_creation_outlined, color: AppColors.p300),
        ],
      ),
    );
  }

  Widget _buildGeneratedVideoCard(String videoUrl) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.p400.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.p600.withValues(alpha: 0.25),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(
              Icons.movie_creation_outlined,
              color: Colors.white,
              size: 24,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '생성된 동영상',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  '앱 안의 플레이어는 아직 없어서 URL만 표시해요.',
                  style: TextStyle(
                    color: AppColors.gray,
                    fontSize: 11,
                    height: 1.35,
                  ),
                ),
                const SizedBox(height: 8),
                SelectableText(
                  videoUrl,
                  maxLines: 2,
                  style: const TextStyle(
                    color: AppColors.p300,
                    fontSize: 11,
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmotionPanel({
    required String title,
    required String subtitle,
    required EmotionAnalysis analysis,
    required Color accent,
    required String emoji,
  }) {
    final top = analysis.topEmotions.take(5).toList();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: accent.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(emoji, style: const TextStyle(fontSize: 16)),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.gray,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  analysis.primaryEmotionDisplay,
                  style: TextStyle(
                    color: accent,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ...top.map((item) => _buildEmotionBar(item, accent)),
        ],
      ),
    );
  }

  Widget _buildEmotionBar(EmotionScoreItem item, Color accent) {
    final percent = item.score.clamp(0.0, 1.0);
    final label = item.labelDisplay.isNotEmpty ? item.labelDisplay : item.label;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              Text(
                '${(percent * 100).toStringAsFixed(0)}%',
                style: TextStyle(
                  color: accent,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              minHeight: 8,
              value: percent,
              backgroundColor: accent.withValues(alpha: 0.12),
              valueColor: AlwaysStoppedAnimation<Color>(accent),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingCard() {
    return Column(
      children: [
        const SizedBox(height: 20),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            children: [
              const CircularProgressIndicator(
                color: AppColors.p400,
                strokeWidth: 2,
              ),
              const SizedBox(height: 14),
              Text(
                'AI가 이야기를 이어쓰고 있어요...',
                style: TextStyle(
                  color: AppColors.p300.withValues(alpha: 0.8),
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildChoices(
    BuildContext context,
    StorySession story,
    AppState state,
  ) {
    if (story.choices.isEmpty) return const SizedBox();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '어떻게 할까요?',
          style: TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 12),
        ...story.choiceOptions.asMap().entries.map((entry) {
          final i = entry.key;
          final option = entry.value;
          final choice = option.text;
          final colors = [AppColors.p600, AppColors.pink, AppColors.teal];
          final emojis = ['🌟', '💫', '✨'];
          final accent = colors[i % colors.length];
          final preview = option.emotion?.topEmotions.take(3).toList() ?? [];

          return Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: GestureDetector(
              onTap: state.isLoading
                  ? null
                  : () async {
                      await state.continueStory(choice);
                      _scrollToBottom();
                    },
              child: Opacity(
                opacity: state.isLoading ? 0.6 : 1,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: accent.withValues(alpha: 0.4)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            emojis[i % emojis.length],
                            style: const TextStyle(fontSize: 18),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              choice,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                          Icon(
                            Icons.arrow_forward_ios_rounded,
                            color: accent,
                            size: 14,
                          ),
                        ],
                      ),
                      if (preview.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: preview.map((emotion) {
                            return Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.06),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                '${emotion.labelDisplay} ${(emotion.score * 100).toStringAsFixed(0)}%',
                                style: TextStyle(
                                  color: accent,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          );
        }),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            onPressed: () => _finishStory(context, state),
            style: OutlinedButton.styleFrom(
              side: const BorderSide(color: AppColors.border),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
              ),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: const Text(
              '🎉 여기서 이야기 끝내기',
              style: TextStyle(color: AppColors.gray, fontSize: 13),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildVocabSection(List<VocabWord> vocab) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GestureDetector(
          onTap: () => setState(() => _showVocab = !_showVocab),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.teal.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.teal.withValues(alpha: 0.3)),
            ),
            child: Row(
              children: [
                const Text('📚', style: TextStyle(fontSize: 16)),
                const SizedBox(width: 8),
                Text(
                  '단어 학습 (${vocab.length}개)',
                  style: const TextStyle(
                    color: AppColors.teal,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                Icon(
                  _showVocab
                      ? Icons.keyboard_arrow_up_rounded
                      : Icons.keyboard_arrow_down_rounded,
                  color: AppColors.teal,
                ),
              ],
            ),
          ),
        ),
        if (_showVocab) ...[
          const SizedBox(height: 8),
          ...vocab.map(_buildVocabCard),
        ],
      ],
    );
  }

  Widget _buildVocabCard(VocabWord w) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                w.hard,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '→ ${w.easy}',
                style: const TextStyle(color: AppColors.teal, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              w.definition,
              style: const TextStyle(color: AppColors.gray, fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }

  void _finishStory(BuildContext context, AppState state) {
    state.finishCurrentStory();
    Navigator.pop(context);
  }

  Widget _buildStoryCompleteCard(BuildContext context, AppState state) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          const Text('🎉', style: TextStyle(fontSize: 34)),
          const SizedBox(height: 10),
          const Text(
            '이야기가 마무리되었어요',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            '지금까지의 모험을 저장하고 다음 이야기를 시작할 수 있어요.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.gray, fontSize: 12, height: 1.5),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => _finishStory(context, state),
              child: const Text('이야기 저장하고 나가기'),
            ),
          ),
        ],
      ),
    );
  }

  void _showExitDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('이야기를 그만할까요?', style: TextStyle(color: Colors.white)),
        content: const Text(
          '지금까지의 이야기가 저장됩니다.',
          style: TextStyle(color: AppColors.gray),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('계속 읽기', style: TextStyle(color: AppColors.p400)),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<AppState>().finishCurrentStory();
              Navigator.pop(context);
            },
            child: const Text('나가기', style: TextStyle(color: AppColors.pink)),
          ),
        ],
      ),
    );
  }

  String _ageLabel(String age) {
    return const {'유아': '4-6세', '초등_저학년': '7-9세', '초등_고학년': '10-12세'}[age] ??
        age;
  }
}
