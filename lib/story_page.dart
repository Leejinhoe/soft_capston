import 'dart:async';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import 'app_theme.dart';
import 'character_chat_page.dart';
import 'letter_page.dart';
import 'main_screen.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'models/story_video.dart';
import 'psych_page.dart';
import 'services/api_service.dart';
import 'services/db_service.dart';
import 'utils/korean_word_normalizer.dart';
import 'widgets/story_cast_widget.dart';
import 'widgets/story_character_animation.dart';
import 'widgets/story_video_player.dart';

enum _NarrationTarget { currentChapter, fullStory }

const _voiceSampleScript =
    '안녕하세요. 저는 따뜻한 목소리로 동화를 읽어요. '
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
  Timer? _journeyVideoStatusPoller;
  int _ttsRequestNumber = 0;

  bool _ttsReady = false;
  bool _ttsInitializing = true;
  bool _ttsSpeaking = false;
  bool _isRecordingVoice = false;
  bool _voiceRecordStarting = false;
  bool _voiceSaving = false;
  int _voiceRevision = 0;
  int _voiceRecordSeconds = 0;
  Uint8List? _recordedVoiceWav;
  List<Map<String, String>> _voiceSamples = [];
  String _selectedVoiceId = 'default';
  String _ttsStatus = '낭독 준비 중';
  bool _assemblingVideo = false;
  _NarrationTarget? _activeNarrationTarget;

  @override
  void initState() {
    super.initState();
    _initTts();
    _restoreVoiceSample();
    _startJourneyVideoStatusPolling();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final state = context.read<AppState>();
      final story = widget.preloadedStory ?? state.currentStory;
      if (story != null) {
        state.restoreMediaJobs(story);
        if (story.hasReachedEnding && story.dbStoryId != null) {
          unawaited(state.refreshStoryJourneyVideoStatus(story));
        }
      }
    });
  }

  void _startJourneyVideoStatusPolling() {
    _journeyVideoStatusPoller?.cancel();
    _journeyVideoStatusPoller = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!mounted) return;
      final state = context.read<AppState>();
      final story = widget.preloadedStory ?? state.currentStory;
      if (story == null || !story.hasReachedEnding || story.dbStoryId == null) {
        return;
      }
      if (story.assembledVideoStatus == 'completed' ||
          story.assembledVideoStatus == 'failed') {
        _journeyVideoStatusPoller?.cancel();
        return;
      }
      unawaited(state.refreshStoryJourneyVideoStatus(story));
    });
  }

  Future<void> _restoreVoiceSample() async {
    final userId = context.read<AppState>().currentUserId;
    if (userId == null || userId.isEmpty) return;
    final revision = _voiceRevision;
    try {
      final data = await DbService.listVoiceSamples();
      final samples = (data['items'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => {'id': '${item['id']}', 'name': '${item['name']}'})
          .toList();
      final selected = data['selected_id']?.toString() ?? 'default';
      final wav = selected == 'default'
          ? null
          : await DbService.loadVoiceSampleById(selected);
      if (!mounted ||
          revision != _voiceRevision ||
          context.read<AppState>().currentUserId != userId) {
        return;
      }
      setState(() {
        _voiceSamples = samples;
        _selectedVoiceId = selected;
        _recordedVoiceWav = wav;
        _ttsStatus = wav == null ? '기본 목소리를 사용해요.' : '저장한 목소리를 불러왔어요.';
      });
    } catch (_) {
      if (mounted && revision == _voiceRevision) {
        setState(() => _ttsStatus = '저장한 목소리를 불러오지 못했어요.');
      }
    }
  }

  @override
  void dispose() {
    _ttsRequestNumber++;
    _journeyVideoStatusPoller?.cancel();
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
    if (_voiceRecordStarting || _isRecordingVoice) return;
    _voiceRevision++;
    var step = 'permission';
    setState(() {
      _voiceRecordStarting = true;
      _ttsStatus = '마이크 권한을 확인하고 있어요. 브라우저의 권한 요청을 확인해 주세요.';
    });
    try {
      if (!await _voiceRecorder.hasPermission()) {
        throw Exception('마이크 권한이 필요해요. 브라우저 또는 기기 설정에서 허용해 주세요.');
      }

      if (!mounted) return;
      step = 'stop_player';
      setState(() => _ttsStatus = '마이크를 준비하고 있어요...');
      await _stopTts();
      if (!mounted) return;
      setState(() => _ttsStatus = '마이크를 켜고 있어요...');
      step = 'start_stream';
      _voicePcm.clear();
      _voiceRecordSeconds = 0;
      final stream = await _voiceRecorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 24000,
          numChannels: 1,
        ),
      );
      if (!mounted) {
        await _voiceRecorder.stop();
        return;
      }
      _voiceRecordingSubscription = stream.listen(
        _voicePcm.add,
        onError: (Object error) {
          debugPrint('[voice_record] stream_error: ${error.runtimeType}');
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
      debugPrint(
        '[voice_record] start_failed step=$step type=${error.runtimeType}',
      );
      if (!mounted) return;
      setState(() {
        _isRecordingVoice = false;
        _ttsStatus = '녹음을 시작하지 못했어요: $error';
      });
    } finally {
      if (mounted) setState(() => _voiceRecordStarting = false);
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
        _voiceSaving = true;
        _ttsStatus = '목소리를 계정에 저장하고 있어요.';
      });
      try {
        final name = '내 목소리 ${_voiceSamples.length + 1}';
        final id = await DbService.addVoiceSample(wav, name);
        await DbService.selectVoiceSample(id);
        if (mounted) {
          setState(() {
            _voiceSamples = [
              ..._voiceSamples,
              {'id': id, 'name': name},
            ];
            _selectedVoiceId = id;
            _ttsStatus = '목소리를 저장했어요. 다음에도 사용할 수 있어요.';
          });
        }
      } catch (_) {
        if (mounted) {
          setState(() => _ttsStatus = '목소리 저장에 실패했어요. 이번 화면에서만 사용할 수 있어요.');
        }
      } finally {
        if (mounted) setState(() => _voiceSaving = false);
      }
    } catch (error) {
      debugPrint('[voice_record] stop_failed type=${error.runtimeType}');
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

  Future<void> _deleteVoiceSample() async {
    if (_voiceSaving || _selectedVoiceId == 'default') return;
    setState(() => _voiceSaving = true);
    try {
      final deletedId = _selectedVoiceId;
      await DbService.deleteVoiceSampleById(deletedId);
      if (!mounted) return;
      _voiceRevision++;
      setState(() {
        _recordedVoiceWav = null;
        _voiceSamples.removeWhere((sample) => sample['id'] == deletedId);
        _selectedVoiceId = 'default';
        _ttsStatus = '저장한 목소리를 삭제했어요.';
      });
    } catch (_) {
      if (mounted) setState(() => _ttsStatus = '목소리를 삭제하지 못했어요. 다시 시도해 주세요.');
    } finally {
      if (mounted) setState(() => _voiceSaving = false);
    }
  }

  Future<void> _selectVoiceSample(String id) async {
    if (_voiceSaving || _isRecordingVoice) return;
    final revision = ++_voiceRevision;
    setState(() => _voiceSaving = true);
    try {
      final wav = id == 'default'
          ? null
          : await DbService.loadVoiceSampleById(id);
      await DbService.selectVoiceSample(id);
      if (!mounted || revision != _voiceRevision) return;
      setState(() {
        _selectedVoiceId = id;
        _recordedVoiceWav = wav;
        _ttsStatus = wav == null ? '기본 목소리를 사용해요.' : '선택한 목소리를 사용해요.';
      });
    } catch (_) {
      if (mounted) setState(() => _ttsStatus = '목소리를 선택하지 못했어요.');
    } finally {
      if (mounted) setState(() => _voiceSaving = false);
    }
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
        voiceGender: 'female',
      );
      if (!mounted || requestNumber != _ttsRequestNumber) return;
      setState(() {
        _ttsStatus = '음성이 도착했어요. 재생을 시작합니다';
      });
      await _narrationPlayer.play(BytesSource(audioBytes));
      if (!mounted || requestNumber != _ttsRequestNumber) return;
      setState(() {
        _ttsSpeaking = true;
        final scope = target == _NarrationTarget.fullStory ? '전체 이야기' : '현재 장';
        _ttsStatus = _recordedVoiceWav == null
            ? '$scope을 읽는 중'
            : '내 목소리로 $scope을 읽는 중';
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
        backgroundColor: AppColors.pageBackground,
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
        backgroundColor: AppColors.pageBackground,
        appBar: AppBar(
          backgroundColor: AppColors.pageBackground,
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
      backgroundColor: AppColors.pageBackground,
      bottomNavigationBar: HyeonlimBottomNav(
        selectedIndex: 1,
        onTap: (index) {
          if (index == 1) return;
          state.selectMainTab(index);
          Navigator.of(context).popUntil((route) => route.isFirst);
        },
      ),
      body: Stack(
        children: [
          _buildBackground(),
          SafeArea(
            child: Column(
              children: [
                _buildHeader(context, story),
                Expanded(
                  child: CustomScrollView(
                    controller: _scrollCtrl,
                    slivers: [
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(24, 20, 24, 16),
                        sliver: SliverToBoxAdapter(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                story.initialPrompt.trim().isEmpty
                                    ? '나의 동화'
                                    : story.initialPrompt,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 28,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 8),
                              const Text(
                                '💡 궁금한 단어를 터치해 보세요!',
                                style: TextStyle(
                                  color: Colors.purpleAccent,
                                  fontSize: 13,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 16),
                              _buildChapterInfo(story),
                              if (story.effectiveStoryCast.isNotEmpty) ...[
                                const SizedBox(height: 10),
                                StoryCastWidget(
                                  members: story.effectiveStoryCast,
                                ),
                              ],
                              const SizedBox(height: 16),
                              _buildTtsPanel(story),
                              if (story.candidateVocab.isNotEmpty) ...[
                                const SizedBox(height: 16),
                                _buildDifficultWordGuide(story),
                              ],
                            ],
                          ),
                        ),
                      ),
                      SliverPadding(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        sliver: SliverList(
                          delegate: SliverChildBuilderDelegate(
                            (context, index) => _buildChapterCard(
                              context,
                              state,
                              story,
                              story.chapters[index],
                              story.chapters.length,
                            ),
                            childCount: story.chapters.length,
                          ),
                        ),
                      ),
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
                        sliver: SliverList(
                          delegate: SliverChildListDelegate([
                            if (state.isLoading) _buildLoadingCard(),
                            if (!state.isLoading &&
                                widget.preloadedStory == null) ...[
                              const SizedBox(height: 24),
                              if (story.choices.isNotEmpty)
                                _buildChoices(context, story, state)
                              else
                                _buildStoryCompleteCard(context, state),
                            ],
                            if (!state.isLoading &&
                                widget.preloadedStory != null &&
                                story.hasReachedEnding) ...[
                              const SizedBox(height: 24),
                              _buildStoryCompleteCard(context, state),
                            ],
                            if (story.vocab.isNotEmpty) ...[
                              const SizedBox(height: 24),
                              _buildVocabSection(story.vocab),
                            ],
                          ]),
                        ),
                      ),
                    ],
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
            radius: 1,
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
          GestureDetector(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => PsychPage(story: story)),
            ),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
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
          IconButton(
            tooltip: '등장인물과 대화',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => CharacterChatPage(
                  story: story,
                  speakerWav: _recordedVoiceWav,
                ),
              ),
            ),
            icon: const Icon(Icons.forum_outlined),
            color: AppColors.p300,
          ),
          IconButton(
            tooltip: '주인공에게 편지 쓰기',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => LetterPage(story: story)),
            ),
            icon: const Icon(Icons.mail_outline_rounded),
            color: AppColors.pink2,
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
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _selectedVoiceId,
            dropdownColor: AppColors.card,
            decoration: const InputDecoration(labelText: '목소리 선택'),
            items: [
              const DropdownMenuItem(value: 'default', child: Text('기본 목소리')),
              ..._voiceSamples.map(
                (sample) => DropdownMenuItem(
                  value: sample['id'],
                  child: Text(sample['name'] ?? '녹음'),
                ),
              ),
            ],
            onChanged: _voiceSaving || _isRecordingVoice
                ? null
                : (value) {
                    if (value != null) unawaited(_selectVoiceSample(value));
                  },
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
                  onPressed:
                      _ttsInitializing || _voiceRecordStarting || _voiceSaving
                      ? null
                      : _toggleVoiceRecording,
                  icon: Icon(
                    _isRecordingVoice
                        ? Icons.stop_circle_outlined
                        : Icons.mic_none_rounded,
                    size: 18,
                  ),
                  label: Text(
                    _voiceRecordStarting
                        ? '마이크 준비 중'
                        : (_isRecordingVoice ? '녹음 완료' : '내 목소리'),
                  ),
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
          if (_selectedVoiceId != 'default' && !_isRecordingVoice)
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: _voiceSaving ? null : _deleteVoiceSample,
                icon: const Icon(Icons.delete_outline, size: 18),
                label: const Text('저장한 목소리 삭제'),
              ),
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
                  '궁금한 단어를 눌러 뜻을 알아봐요',
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
    final spans = <InlineSpan>[];
    var cursor = 0;
    final candidates = _findVocabMatches(text, story.candidateVocab);
    for (final match in RegExp(r'[가-힣]+').allMatches(text)) {
      if (match.start > cursor) {
        spans.add(TextSpan(text: text.substring(cursor, match.start)));
      }
      final word = match.group(0)!;
      _VocabTextMatch? candidate;
      for (final item in candidates) {
        if (item.start < match.end && item.end > match.start) {
          candidate = item;
          break;
        }
      }
      final suggested = candidate?.word;
      final saved =
          suggested != null &&
          story.vocab.any((item) => item.hard == suggested.hard);
      spans.add(
        WidgetSpan(
          alignment: PlaceholderAlignment.baseline,
          baseline: TextBaseline.alphabetic,
          child: GestureDetector(
            onTap: () => _showContextWordSheet(
              context,
              state,
              story,
              word,
              text,
              match.start,
              suggested,
            ),
            child: Text(
              word,
              style: TextStyle(
                color: Colors.white,
                fontSize: 15,
                height: 1.8,
                fontWeight: suggested != null
                    ? FontWeight.w600
                    : FontWeight.normal,
                decoration: suggested != null
                    ? TextDecoration.underline
                    : TextDecoration.none,
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

  Future<void> _showContextWordSheet(
    BuildContext context,
    AppState state,
    StorySession story,
    String word,
    String text,
    int offset,
    VocabWord? suggested,
  ) async {
    final lookupWord = KoreanWordNormalizer.lookupWord(suggested?.hard ?? word);
    final sentence = _sentenceAroundOffset(text, offset);
    final lookup = ApiService.explainWord(
      word: lookupWord,
      sentence: sentence,
      age: story.age,
    );
    await showModalBottomSheet<void>(
      context: context,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: FutureBuilder<String>(
            future: lookup,
            builder: (builderContext, snapshot) {
              final meaning = snapshot.data;
              final alreadySaved = story.vocab.any(
                (item) => item.hard == lookupWord,
              );
              final canSave =
                  suggested != null || (meaning != null && meaning.isNotEmpty);
              return Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    lookupWord,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (suggested != null) ...[
                    Text(
                      '쉬운 뜻: ${suggested.easy}',
                      style: const TextStyle(
                        color: AppColors.teal,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      suggested.definition,
                      style: const TextStyle(
                        color: Colors.white70,
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  if (snapshot.connectionState != ConnectionState.done)
                    const Row(
                      children: [
                        CircularProgressIndicator(),
                        SizedBox(width: 16),
                        Expanded(child: Text('이야기에 맞는 뜻을 생각하고 있어요.')),
                      ],
                    )
                  else if (snapshot.hasError)
                    const Text(
                      'AI 문맥 설명을 불러오지 못했어요. 잠시 후 다시 눌러 주세요.',
                      style: TextStyle(color: Colors.white60),
                    )
                  else if (meaning != null && meaning.isNotEmpty)
                    Text('이야기 속 뜻: $meaning'),
                  if (canSave || alreadySaved) ...[
                    const SizedBox(height: 20),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: () async {
                          if (alreadySaved) {
                            Navigator.pop(sheetContext);
                            return;
                          }
                          final item =
                              suggested?.copyWith(
                                definition: meaning ?? suggested.definition,
                              ) ??
                              VocabWord(
                                hard: lookupWord,
                                easy: meaning!,
                                definition: meaning,
                              );
                          final ok = await state.saveVocabularyFromStory(
                            story,
                            item,
                          );
                          if (!sheetContext.mounted) return;
                          Navigator.pop(sheetContext);
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  ok ? '단어장에 저장했어요.' : '단어 저장에 실패했어요.',
                                ),
                              ),
                            );
                          }
                        },
                        icon: const Icon(Icons.bookmark_add_outlined),
                        label: Text(alreadySaved ? '단어장에 저장됨' : '단어장에 저장'),
                      ),
                    ),
                  ],
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  String _sentenceAroundOffset(String text, int offset) {
    const boundaries = '.!?。！？\n';
    var start = 0;
    for (var i = offset - 1; i >= 0; i--) {
      if (boundaries.contains(text[i])) {
        start = i + 1;
        break;
      }
    }
    var end = text.length;
    for (var i = offset.clamp(0, text.length); i < text.length; i++) {
      if (boundaries.contains(text[i])) {
        end = i + 1;
        break;
      }
    }
    return text.substring(start, end).trim();
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

  Widget _buildChapterCard(
    BuildContext context,
    AppState state,
    StorySession story,
    StoryChapter chapter,
    int totalChapters,
  ) {
    final isLatestChapter = identical(chapter, story.chapters.last);
    final remoteVideoUrl = _isRemoteMediaUrl(chapter.videoUrl)
        ? chapter.videoUrl!.trim()
        : null;
    final characterKey = story.selectedHeroCharacterKey;
    final selectedVideo = remoteVideoUrl != null || chapter.choiceMade == null
        ? null
        : StoryVideoCatalog.forChapter(
            text: chapter.text,
            choice: chapter.choiceMade,
            chapter: chapter.chapter,
            genre: story.genre,
            characterKey: characterKey,
          );
    final supportsLocalMotion =
        characterKey != null &&
        StoryCharacterAnimation.supports(
          characterKey: characterKey,
          storyText: chapter.text,
        );
    final isEnding = story.hasReachedEnding && isLatestChapter;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: AppColors.pageSurface,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: isEnding
              ? Colors.amberAccent.withValues(alpha: 0.7)
              : AppColors.border,
          width: isEnding ? 1.5 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.p700.withValues(alpha: 0.12),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: isEnding
                  ? Colors.amberAccent.withValues(alpha: 0.16)
                  : AppColors.p600.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Text(
              isEnding
                  ? '🌙 마지막 장면'
                  : '📖 장면 ${chapter.chapter} / $totalChapters',
              style: TextStyle(
                color: isEnding ? Colors.amberAccent : AppColors.p300,
                fontSize: 13,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(height: 14),
          if (chapter.imageBytes != null) ...[
            _buildStoryImage(chapter.imageBytes!),
          ] else if (_isRemoteMediaUrl(chapter.imageUrl)) ...[
            _buildNetworkStoryImage(chapter.imageUrl!),
          ] else if (chapter.imageUrl?.startsWith('mock://image/') == true) ...[
            _buildTemporaryStoryImage(chapter),
          ],
          if (chapter.imageBytes != null ||
              _isRemoteMediaUrl(chapter.imageUrl) ||
              chapter.imageUrl?.startsWith('mock://image/') == true) ...[
            const SizedBox(height: 16),
          ],
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
          if (chapter.mediaStatus == 'partial' ||
              chapter.mediaStatus == 'failed') ...[
            const SizedBox(height: 14),
            _buildMediaRetryBanner(state, story, chapter),
          ],
          if (remoteVideoUrl != null) ...[
            const SizedBox(height: 16),
            _buildArchivedVideoButton(context, videoUrl: remoteVideoUrl),
          ] else if (chapter.videoUrl?.startsWith('mock://video/') == true) ...[
            const SizedBox(height: 16),
            _buildTemporaryVideoCard(chapter),
          ],
          if (isLatestChapter && !story.hasReachedEnding) ...[
            const SizedBox(height: 16),
            _buildStoryVideoGuide(story),
          ],
          if (selectedVideo != null || supportsLocalMotion) ...[
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: OutlinedButton.icon(
                onPressed: () => showDialog<void>(
                  context: context,
                  builder: (_) => Dialog(
                    backgroundColor: AppColors.card2,
                    insetPadding: const EdgeInsets.all(20),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 720),
                      child: selectedVideo != null
                          ? StoryVideoPlayer(
                              clip: selectedVideo,
                              autoplay: true,
                            )
                          : StoryCharacterAnimation(
                              characterKey: characterKey!,
                              storyText: chapter.text,
                              genre: story.genre,
                            ),
                    ),
                  ),
                ),
                icon: const Icon(Icons.play_circle_outline_rounded, size: 18),
                label: const Text('캐릭터 움직임 보기'),
              ),
            ),
          ],
          if (chapter.choiceMade != null) ...[
            const SizedBox(height: 18),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    AppColors.p500.withValues(alpha: 0.16),
                    AppColors.pink.withValues(alpha: 0.12),
                  ],
                ),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: AppColors.p400.withValues(alpha: 0.25),
                ),
              ),
              child: Row(
                children: [
                  const Text('✨', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      '내가 고른 길 · ${chapter.choiceMade}',
                      style: const TextStyle(
                        color: AppColors.p300,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStoryImage(Uint8List bytes) {
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
                    cacheWidth: 640,
                    filterQuality: FilterQuality.low,
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
                    headers: DbService.mediaHeaders,
                    cacheWidth: 640,
                    filterQuality: FilterQuality.low,
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

  Widget _buildArchivedVideoButton(
    BuildContext context, {
    required String videoUrl,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.card2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.p400.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.movie_creation_outlined,
            color: AppColors.p300,
            size: 22,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '이 장면만 보는 미리보기',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          IconButton(
            tooltip: '이 장면만 보기',
            onPressed: () {
              showDialog<void>(
                context: context,
                builder: (dialogContext) => Dialog(
                  backgroundColor: AppColors.card2,
                  insetPadding: const EdgeInsets.all(20),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 720),
                    child: StoryVideoPlayer.network(
                      videoUrl: videoUrl,
                      httpHeaders: DbService.mediaHeaders,
                      autoplay: true,
                    ),
                  ),
                ),
              );
            },
            icon: const Icon(Icons.play_arrow_rounded),
            color: AppColors.p300,
          ),
        ],
      ),
    );
  }

  Widget _buildMediaRetryBanner(
    AppState state,
    StorySession story,
    StoryChapter chapter,
  ) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 10, 8, 10),
      decoration: BoxDecoration(
        color: AppColors.pink.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.pink.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded, color: AppColors.pink2),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              chapter.mediaError ?? '영상 생성에 실패했습니다.',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 11,
                height: 1.35,
              ),
            ),
          ),
          IconButton(
            tooltip: chapter.mediaStatus == 'partial' ? '영상 다시 생성' : '삽화 다시 생성',
            onPressed: chapter.mediaStatus == 'running'
                ? null
                : () => chapter.mediaStatus == 'partial'
                      ? state.generateVideoForChapter(story, chapter)
                      : state.retryMediaForChapter(story, chapter),
            icon: const Icon(Icons.refresh_rounded),
            color: AppColors.p300,
          ),
        ],
      ),
    );
  }

  Widget _buildStoryVideoGuide(StorySession story) {
    final imageCount = story.chapters
        .where(
          (chapter) =>
              chapter.imageBytes != null ||
              _isRemoteMediaUrl(chapter.imageUrl) ||
              chapter.imageUrl?.startsWith('mock://image/') == true,
        )
        .length;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.p600.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.p400.withValues(alpha: 0.36)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.p500.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.movie_creation_outlined,
              color: AppColors.p300,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '전체 동화 영상',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  '현재 ${story.chapters.length}장면 · 삽화 $imageCount장\n'
                  '이야기를 완성하면 모든 장면의 삽화를 순서대로 이어 붙여요.',
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
    final options = story.choices.map((choice) {
      for (final option in story.choiceOptions) {
        if (option.text == choice) return option;
      }
      return ChoiceOption(text: choice);
    }).toList();

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
        ...options.asMap().entries.map((entry) {
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
              '이야기 저장하고 나가기',
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

  Future<void> _requestStoryJourneyVideo(
    AppState state,
    StorySession story,
  ) async {
    if (story.dbStoryId == null || story.dbStoryId!.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('동화 저장이 끝나면 영상 작업을 요청할 수 있어요.')),
      );
      return;
    }
    setState(() => _assemblingVideo = true);
    final queued = await state.retryStoryJourneyVideo(story);
    if (!mounted) return;
    setState(() => _assemblingVideo = false);
    if (queued && story.assembledVideoStatus != 'completed') {
      _startJourneyVideoStatusPolling();
    }
    final message = !queued
        ? state.errorMessage ?? '영상 작업을 요청하지 못했어요.'
        : story.assembledVideoStatus == 'waiting_for_images'
        ? '삽화가 준비되면 영상 합성을 시작해요.'
        : story.assembledVideoStatus == 'completed'
        ? '동화 영상이 준비됐어요.'
        : '영상 작업을 대기열에 넣었어요. 이 화면에서 진행 상태를 확인할 수 있어요.';
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  Widget _buildJourneyVideoStatus(AppState state, StorySession story) {
    final status = story.assembledVideoStatus;
    final videoUrl = story.assembledVideoUrl;
    if (status == 'completed' && videoUrl != null && videoUrl.isNotEmpty) {
      return Column(
        children: [
          Text(
            '전체 동화 영상 · ${story.chapters.length}장면',
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          StoryVideoPlayer.network(
            videoUrl: videoUrl,
            title: story.initialPrompt,
            description: '저장된 삽화를 순서대로 이어 붙이고 장면 전환만 더한 영상이에요.',
            httpHeaders: DbService.mediaHeaders,
          ),
          const SizedBox(height: 12),
        ],
      );
    }

    if (status == 'pending' ||
        status == 'running' ||
        status == 'waiting_for_images') {
      final label = status == 'waiting_for_images'
          ? '삽화를 준비하고 있어요. 준비되면 영상 합성을 시작해요.'
          : status == 'pending'
          ? '영상 생성 대기 중이에요.'
          : '동화 영상을 만들고 있어요.';
      return Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (status != 'waiting_for_images') ...[
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              const SizedBox(width: 10),
            ],
            Flexible(
              child: Text(
                label,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.gray, fontSize: 12),
              ),
            ),
          ],
        ),
      );
    }

    if (story.dbStoryId == null) {
      return const Padding(
        padding: EdgeInsets.only(bottom: 12),
        child: Text(
          '동화를 저장하고 있어요. 저장이 끝나면 영상 생성 상태를 확인할 수 있어요.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.gray, fontSize: 12),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        children: [
          if (status == 'failed')
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                story.assembledVideoError ?? '영상 합성에 실패했어요.',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.orangeAccent,
                  fontSize: 12,
                ),
              ),
            )
          else
            const Text(
              '동화 전체 삽화를 모아 영상을 자동 생성합니다.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.gray, fontSize: 12),
            ),
          OutlinedButton.icon(
            onPressed: _assemblingVideo
                ? null
                : () => _requestStoryJourneyVideo(state, story),
            icon: _assemblingVideo
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(
                    status == 'failed'
                        ? Icons.refresh_rounded
                        : Icons.movie_outlined,
                  ),
            label: Text(
              _assemblingVideo
                  ? '영상 작업 요청 중...'
                  : status == 'failed'
                  ? '다시 시도'
                  : '전체 동화 영상 만들기',
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStoryCompleteCard(BuildContext context, AppState state) {
    final story = widget.preloadedStory ?? state.currentStory;
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
          if (story != null) _buildJourneyVideoStatus(state, story),
          if (widget.preloadedStory == null)
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
