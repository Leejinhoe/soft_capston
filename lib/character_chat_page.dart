import 'dart:async';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import 'main.dart';
import 'models/app_state.dart';
import 'models/story_model.dart';
import 'services/api_service.dart';
import 'services/db_service.dart';

enum _VoiceConversationPhase { idle, listening, thinking, speaking }

class CharacterChatPage extends StatefulWidget {
  final StorySession story;

  const CharacterChatPage({super.key, required this.story});

  @override
  State<CharacterChatPage> createState() => _CharacterChatPageState();
}

class _CharacterChatPageState extends State<CharacterChatPage> {
  static const _initialSuggestions = [
    '모험에서 가장 기억나는 순간은 뭐야?',
    '그때 어떤 기분이었어?',
    '나에게 해 주고 싶은 말이 있어?',
  ];

  final TextEditingController _messageController = TextEditingController();
  final ScrollController _messageScrollController = ScrollController();
  final AudioPlayer _voiceReplyPlayer = AudioPlayer();
  final AudioRecorder _voiceRecorder = AudioRecorder();
  final BytesBuilder _voicePcm = BytesBuilder(copy: false);
  final Map<String, List<CharacterChatMessage>> _conversations = {};
  final Map<String, List<String>> _suggestions = {};

  List<StoryCharacter> _characters = const [];
  StoryCharacter? _selectedCharacter;
  bool _isLoadingCharacters = true;
  bool _isSending = false;
  bool _isRecordingVoice = false;
  bool _isTranscribingVoice = false;
  bool _isVoiceConversationActive = false;
  bool _voiceSpeechDetected = false;
  bool _isFinishingVoiceTurn = false;
  bool _resumeListeningAfterReply = false;
  int _voiceRecordSeconds = 0;
  Timer? _voiceRecordTimer;
  Timer? _voiceSilenceTimer;
  StreamSubscription<Uint8List>? _voiceRecordingSubscription;
  StreamSubscription<void>? _voiceReplyCompletionSubscription;
  _VoiceConversationPhase _voicePhase = _VoiceConversationPhase.idle;
  String? _notice;

  @override
  void initState() {
    super.initState();
    unawaited(_voiceReplyPlayer.setReleaseMode(ReleaseMode.stop));
    _voiceReplyCompletionSubscription = _voiceReplyPlayer.onPlayerComplete
        .listen((_) => _resumeVoiceListeningAfterReply());
    unawaited(_loadCharacters());
  }

  @override
  void dispose() {
    _messageController.dispose();
    _messageScrollController.dispose();
    _voiceRecordTimer?.cancel();
    _voiceSilenceTimer?.cancel();
    _voiceRecordingSubscription?.cancel();
    _voiceReplyCompletionSubscription?.cancel();
    _voiceRecorder.dispose();
    _voiceReplyPlayer.dispose();
    super.dispose();
  }

  Future<void> _loadCharacters({bool forceFallback = false}) async {
    setState(() {
      _isLoadingCharacters = true;
      _notice = null;
    });

    List<StoryCharacter> characters;
    try {
      if (forceFallback || widget.story.storyId.startsWith('mock_')) {
        throw const _UseLocalCharacters();
      }
      characters = await ApiService.discoverStoryCharacters(
        storyId: widget.story.storyId,
        storyTitle: widget.story.initialPrompt,
        storyText: widget.story.fullStoryText,
        age: widget.story.age,
      );
    } on _UseLocalCharacters {
      characters = _fallbackCharacters(widget.story);
      _notice = '임시 동화의 등장인물로 대화를 준비했어요.';
    } catch (_) {
      characters = _fallbackCharacters(widget.story);
      _notice = 'AI 서버에 연결하지 못해 동화 본문에서 찾은 캐릭터를 보여드려요.';
    }

    if (!mounted) return;
    setState(() {
      _characters = characters;
      _selectedCharacter = characters.isEmpty ? null : characters.first;
      _isLoadingCharacters = false;
      final selected = _selectedCharacter;
      if (selected != null) _ensureConversation(selected);
    });
    _scrollToLatest();
  }

  void _ensureConversation(StoryCharacter character) {
    _conversations.putIfAbsent(
      character.name,
      () => [
        CharacterChatMessage(
          role: 'character',
          content: character.greeting.isNotEmpty
              ? character.greeting
              : '안녕! 나는 ${character.name}이야. 우리 이야기에서 궁금했던 걸 편하게 물어봐.',
        ),
      ],
    );
    _suggestions.putIfAbsent(
      character.name,
      () => List<String>.from(_initialSuggestions),
    );
  }

  void _selectCharacter(StoryCharacter character) {
    if (_isSending ||
        _isVoiceConversationActive ||
        character.name == _selectedCharacter?.name) {
      return;
    }
    setState(() {
      _selectedCharacter = character;
      _ensureConversation(character);
      _notice = null;
    });
    _scrollToLatest();
  }

  Future<String?> _sendMessage([String? preset]) async {
    final character = _selectedCharacter;
    final message = (preset ?? _messageController.text).trim();
    if (character == null || message.isEmpty || _isSending) return null;

    final conversation = _conversations[character.name]!;
    setState(() {
      conversation.add(CharacterChatMessage(role: 'user', content: message));
      _messageController.clear();
      _isSending = true;
      _notice = null;
    });
    _scrollToLatest();

    CharacterChatReply result;
    try {
      result = await ApiService.chatWithStoryCharacter(
        storyId: widget.story.storyId,
        storyTitle: widget.story.initialPrompt,
        storyText: widget.story.fullStoryText,
        age: widget.story.age,
        userName: context.read<AppState>().currentDisplayName,
        character: character,
        messages: List<CharacterChatMessage>.from(conversation),
        userMessage: message,
      );
    } catch (_) {
      result = _fallbackReply(character, message);
      _notice = '서버 답장을 받지 못해 캐릭터의 임시 답변을 보여드려요.';
    }

    if (!mounted || _selectedCharacter?.name != character.name) return null;
    setState(() {
      conversation.add(
        CharacterChatMessage(role: 'character', content: result.reply),
      );
      _suggestions[character.name] = result.suggestedReplies.isNotEmpty
          ? result.suggestedReplies
          : List<String>.from(_initialSuggestions);
      _isSending = false;
    });
    _scrollToLatest();
    return result.reply;
  }

  String get _voiceTime {
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
      for (var index = 0; index < value.length; index++) {
        header.setUint8(offset + index, value.codeUnitAt(index));
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

  Future<void> _toggleVoiceConversation() async {
    if (_isVoiceConversationActive) {
      await _endVoiceConversation();
    } else {
      await _beginVoiceConversation();
    }
  }

  Future<void> _beginVoiceConversation() async {
    if (_isSending || _isTranscribingVoice) return;
    try {
      if (!await _voiceRecorder.hasPermission()) {
        throw Exception('마이크 권한이 필요해요. 브라우저 또는 기기 설정에서 허용해 주세요.');
      }
      await _voiceReplyPlayer.stop();
      if (!mounted) return;
      setState(() {
        _isVoiceConversationActive = true;
        _voicePhase = _VoiceConversationPhase.listening;
        _notice = '음성 대화를 시작했어요. 말하면 자동으로 보내 드려요.';
      });
      unawaited(_warmUpVoiceServices());
      await _startListeningForVoiceTurn();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _isVoiceConversationActive = false;
        _voicePhase = _VoiceConversationPhase.idle;
        _notice = '음성 대화를 시작하지 못했어요: $error';
      });
    }
  }

  Future<void> _warmUpVoiceServices() async {
    try {
      await Future.wait([
        ApiService.warmUpKoreanSpeech(),
        DbService.warmUpNarration(),
      ]);
    } catch (_) {
      // The actual turn surfaces a detailed error if either remote model is unavailable.
    }
  }

  Future<void> _startListeningForVoiceTurn() async {
    if (!_isVoiceConversationActive ||
        _isRecordingVoice ||
        _isFinishingVoiceTurn ||
        !mounted) {
      return;
    }
    try {
      _voicePcm.clear();
      _voiceSpeechDetected = false;
      _voiceRecordSeconds = 0;
      _voiceSilenceTimer?.cancel();
      _voiceSilenceTimer = null;
      await _voiceRecordingSubscription?.cancel();
      final stream = await _voiceRecorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 24000,
          numChannels: 1,
        ),
      );
      _voiceRecordingSubscription = stream.listen(
        _handleVoiceChunk,
        onError: (_) => unawaited(
          _endVoiceConversation(notice: '마이크 입력이 끊겨 음성 대화를 종료했어요.'),
        ),
      );
      _voiceRecordTimer?.cancel();
      _voiceRecordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted || !_isRecordingVoice) return;
        if (_voiceRecordSeconds >= 45) {
          if (_voiceSpeechDetected) {
            unawaited(_finishVoiceTurn());
          } else {
            unawaited(
              _endVoiceConversation(
                notice: '말소리를 듣지 못해 음성 대화를 마쳤어요. 다시 눌러 시작할 수 있어요.',
              ),
            );
          }
          return;
        }
        setState(() {
          _voiceRecordSeconds++;
          _notice = _voiceSpeechDetected
              ? '듣고 있어요. 말을 마치면 자동으로 보낼게요. ($_voiceTime / 00:45)'
              : '듣고 있어요. 편하게 말씀해 주세요. ($_voiceTime / 00:45)';
        });
      });
      if (!mounted || !_isVoiceConversationActive) return;
      setState(() {
        _isRecordingVoice = true;
        _voicePhase = _VoiceConversationPhase.listening;
        _notice = '듣고 있어요. 편하게 말씀해 주세요.';
      });
    } catch (error) {
      await _endVoiceConversation(notice: '마이크를 다시 시작하지 못했어요: $error');
    }
  }

  void _handleVoiceChunk(Uint8List chunk) {
    if (!_isRecordingVoice || _isFinishingVoiceTurn) return;
    _voicePcm.add(chunk);
    if (_hasSpeechEnergy(chunk)) {
      _voiceSpeechDetected = true;
      _voiceSilenceTimer?.cancel();
      _voiceSilenceTimer = null;
      return;
    }
    if (_voiceSpeechDetected && _voiceSilenceTimer == null) {
      _voiceSilenceTimer = Timer(const Duration(milliseconds: 1100), () {
        _voiceSilenceTimer = null;
        unawaited(_finishVoiceTurn());
      });
    }
  }

  bool _hasSpeechEnergy(Uint8List pcm) {
    if (pcm.length < 4) return false;
    var total = 0;
    var samples = 0;
    for (var index = 0; index + 1 < pcm.length; index += 16) {
      var sample = pcm[index] | (pcm[index + 1] << 8);
      if (sample >= 0x8000) sample -= 0x10000;
      total += sample.abs();
      samples++;
    }
    return samples > 0 && total / samples >= 420;
  }

  Future<void> _finishVoiceTurn() async {
    if (!_isRecordingVoice || _isFinishingVoiceTurn) return;
    _isFinishingVoiceTurn = true;
    var resumeListening = false;
    _voiceRecordTimer?.cancel();
    _voiceRecordTimer = null;
    _voiceSilenceTimer?.cancel();
    _voiceSilenceTimer = null;
    try {
      await _voiceRecorder.stop();
      await _voiceRecordingSubscription?.cancel();
      _voiceRecordingSubscription = null;
      final pcm = _voicePcm.takeBytes();
      const minimumBytes = 24000;
      if (!_voiceSpeechDetected || pcm.length < minimumBytes) {
        if (mounted && _isVoiceConversationActive) {
          setState(() {
            _isRecordingVoice = false;
            _notice = '말소리를 충분히 듣지 못했어요. 다시 말씀해 주세요.';
          });
          resumeListening = true;
        }
        return;
      }
      final wav = _pcm16ToWav(pcm);
      if (!mounted) return;
      setState(() {
        _isRecordingVoice = false;
        _isTranscribingVoice = true;
        _voicePhase = _VoiceConversationPhase.thinking;
        _notice = '말한 내용을 이해하고 있어요...';
      });
      final transcript = await ApiService.transcribeKoreanSpeech(wav);
      if (!mounted || !_isVoiceConversationActive) return;
      setState(() => _notice = '“$transcript”라고 말했어요. 캐릭터가 답하는 중이에요...');
      final reply = await _sendMessage(transcript);
      if (reply == null || !mounted || !_isVoiceConversationActive) return;
      setState(() {
        _voicePhase = _VoiceConversationPhase.speaking;
        _resumeListeningAfterReply = true;
        _notice = '캐릭터가 내 목소리로 답하고 있어요...';
      });
      final audio = await DbService.synthesizeNarration(reply, speakerWav: wav);
      if (!mounted || !_isVoiceConversationActive) return;
      await _voiceReplyPlayer.play(BytesSource(audio));
    } catch (error) {
      if (!mounted) return;
      setState(() => _notice = '음성 대화 오류: $error');
      if (_isVoiceConversationActive) {
        resumeListening = true;
      }
    } finally {
      _isFinishingVoiceTurn = false;
      if (mounted) setState(() => _isTranscribingVoice = false);
      if (resumeListening && _isVoiceConversationActive) {
        unawaited(_startListeningForVoiceTurn());
      }
    }
  }

  void _resumeVoiceListeningAfterReply() {
    if (!_isVoiceConversationActive || !_resumeListeningAfterReply) return;
    _resumeListeningAfterReply = false;
    unawaited(_startListeningForVoiceTurn());
  }

  Future<void> _endVoiceConversation({String? notice}) async {
    _isVoiceConversationActive = false;
    _resumeListeningAfterReply = false;
    _voiceRecordTimer?.cancel();
    _voiceRecordTimer = null;
    _voiceSilenceTimer?.cancel();
    _voiceSilenceTimer = null;
    if (_isRecordingVoice) {
      await _voiceRecorder.stop();
    }
    await _voiceRecordingSubscription?.cancel();
    _voiceRecordingSubscription = null;
    await _voiceReplyPlayer.stop();
    _voicePcm.clear();
    if (!mounted) return;
    setState(() {
      _isRecordingVoice = false;
      _isTranscribingVoice = false;
      _voicePhase = _VoiceConversationPhase.idle;
      _notice = notice ?? '음성 대화를 마쳤어요.';
    });
  }

  CharacterChatReply _fallbackReply(StoryCharacter character, String message) {
    final normalized = message.replaceAll(RegExp(r'\s+'), ' ');
    late String reply;
    if (RegExp(r'기분|마음|무서|두려').hasMatch(normalized)) {
      reply =
          '솔직히 조금 떨렸지만 혼자가 아니라는 생각에 힘이 났어. '
          '우리 이야기에서 용기를 낼 수 있었던 건 곁에 있는 친구들의 마음 덕분이야.';
    } else if (RegExp(r'왜|이유|어째서').hasMatch(normalized)) {
      reply =
          '그때는 내가 소중하게 생각하는 것을 지키고 싶었어. '
          '서두르기보다 친구들의 이야기를 듣고 움직이는 게 좋은 방법이라는 것도 배웠지.';
    } else if (RegExp(r'친구|좋아|고마').hasMatch(normalized)) {
      reply = '그렇게 말해 줘서 정말 고마워! 너도 내 이야기 속에 함께 있었다면 든든한 친구가 되었을 거야.';
    } else {
      reply =
          '${character.name}인 내가 듣기에도 참 재미있는 질문이야. '
          '나는 ${character.personality.replaceAll(RegExp(r'[.!?]+$'), '')} 마음으로 그 순간을 지나왔어. '
          '너라면 우리 이야기에서 어떤 길을 골랐을지 궁금해!';
    }
    return CharacterChatReply(
      reply: reply,
      suggestedReplies: const [
        '다시 모험한다면 무엇을 하고 싶어?',
        '가장 고마웠던 친구는 누구야?',
        '나도 용기를 내려면 어떻게 해야 해?',
      ],
    );
  }

  void _resetCurrentConversation() {
    final character = _selectedCharacter;
    if (character == null || _isSending || _isVoiceConversationActive) return;
    setState(() {
      _conversations.remove(character.name);
      _suggestions.remove(character.name);
      _ensureConversation(character);
      _notice = '${character.name}와 새 대화를 시작했어요.';
    });
    _scrollToLatest();
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_messageScrollController.hasClients) return;
      _messageScrollController.animateTo(
        _messageScrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 320),
        curve: Curves.easeOutCubic,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final character = _selectedCharacter;
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: _isVoiceConversationActive
          ? null
          : AppBar(
              titleSpacing: 0,
              title: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('이야기 속 친구와 대화'),
                  Text(
                    widget.story.initialPrompt,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.gray,
                      fontSize: 10,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
              actions: [
                IconButton(
                  tooltip: '현재 대화 새로 시작',
                  onPressed: character == null
                      ? null
                      : _resetCurrentConversation,
                  icon: const Icon(Icons.refresh_rounded),
                ),
              ],
            ),
      body: Stack(
        children: [
          const Positioned.fill(child: _ChatBackground()),
          SafeArea(
            top: false,
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 920),
                child: _isLoadingCharacters
                    ? _buildLoadingCharacters()
                    : Column(
                        children: [
                          _buildCharacterPicker(),
                          if (_notice != null) _buildNotice(_notice!),
                          Expanded(
                            child: character == null
                                ? _buildNoCharacter()
                                : _buildConversation(character),
                          ),
                          if (character != null) _buildComposer(character),
                        ],
                      ),
              ),
            ),
          ),
          if (_isVoiceConversationActive && character != null)
            Positioned.fill(
              child: _VoiceConversationOverlay(
                character: character,
                phase: _voicePhase,
                status: _notice,
                onEnd: _toggleVoiceConversation,
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildLoadingCharacters() {
    return Center(
      child: Container(
        margin: const EdgeInsets.all(24),
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 26),
        decoration: BoxDecoration(
          color: AppColors.card.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: AppColors.border),
        ),
        child: const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: AppColors.p400, strokeWidth: 2),
            SizedBox(height: 18),
            Text(
              '동화 속 친구들을 만나고 있어요...',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCharacterPicker() {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 12),
      decoration: BoxDecoration(
        color: AppColors.bg2.withValues(alpha: 0.92),
        border: const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.groups_2_rounded, color: AppColors.p300, size: 18),
              SizedBox(width: 8),
              Text(
                '누구와 이야기할까요?',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 105,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _characters.length,
              separatorBuilder: (_, _) => const SizedBox(width: 10),
              itemBuilder: (context, index) {
                final character = _characters[index];
                return _buildCharacterCard(character);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCharacterCard(StoryCharacter character) {
    final selected = character.name == _selectedCharacter?.name;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _selectCharacter(character),
        borderRadius: BorderRadius.circular(18),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          width: 170,
          padding: const EdgeInsets.all(11),
          decoration: BoxDecoration(
            gradient: selected
                ? const LinearGradient(
                    colors: [Color(0xFF5B21B6), Color(0xFF9D3F78)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  )
                : null,
            color: selected ? null : AppColors.card,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? AppColors.p300 : Colors.white12,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: AppColors.p600.withValues(alpha: 0.28),
                      blurRadius: 16,
                      offset: const Offset(0, 6),
                    ),
                  ]
                : null,
          ),
          child: Row(
            children: [
              Container(
                width: 43,
                height: 43,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: selected ? 0.16 : 0.08),
                  shape: BoxShape.circle,
                ),
                child: Text(
                  character.avatarEmoji,
                  style: const TextStyle(fontSize: 24),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      character.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      character.role,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.72),
                        fontSize: 10,
                        height: 1.25,
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

  Widget _buildNotice(String message) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: const Color(0xFF2B2348).withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.p500.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.info_outline_rounded,
            color: AppColors.p300,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(color: AppColors.p300, fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConversation(StoryCharacter character) {
    final messages = _conversations[character.name] ?? const [];
    return Column(
      children: [
        Container(
          width: double.infinity,
          margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: const Color(0xFF191334).withValues(alpha: 0.88),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.white10),
          ),
          child: Row(
            children: [
              Text(character.avatarEmoji, style: const TextStyle(fontSize: 29)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${character.name} · ${character.role}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      character.personality,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.gray,
                        fontSize: 11,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                decoration: BoxDecoration(
                  color: AppColors.teal.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const Text(
                  '동화 기억 중',
                  style: TextStyle(
                    color: AppColors.teal,
                    fontSize: 9,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            controller: _messageScrollController,
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 18),
            itemCount: messages.length + (_isSending ? 1 : 0),
            itemBuilder: (context, index) {
              if (_isSending && index == messages.length) {
                return _buildTypingBubble(character);
              }
              return _buildMessageBubble(character, messages[index]);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildMessageBubble(
    StoryCharacter character,
    CharacterChatMessage message,
  ) {
    final isUser = message.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (!isUser) ...[
              Container(
                width: 32,
                height: 32,
                alignment: Alignment.center,
                decoration: const BoxDecoration(
                  color: Color(0xFF2A2050),
                  shape: BoxShape.circle,
                ),
                child: Text(
                  character.avatarEmoji,
                  style: const TextStyle(fontSize: 18),
                ),
              ),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: Container(
                constraints: const BoxConstraints(maxWidth: 600),
                padding: const EdgeInsets.symmetric(
                  horizontal: 15,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  gradient: isUser
                      ? const LinearGradient(
                          colors: [AppColors.p600, Color(0xFF9D3F78)],
                        )
                      : null,
                  color: isUser ? null : const Color(0xFF211A40),
                  borderRadius: BorderRadius.only(
                    topLeft: const Radius.circular(18),
                    topRight: const Radius.circular(18),
                    bottomLeft: Radius.circular(isUser ? 18 : 5),
                    bottomRight: Radius.circular(isUser ? 5 : 18),
                  ),
                  border: isUser ? null : Border.all(color: Colors.white10),
                ),
                child: Text(
                  message.content,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    height: 1.52,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypingBubble(StoryCharacter character) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: Color(0xFF2A2050),
                shape: BoxShape.circle,
              ),
              child: Text(
                character.avatarEmoji,
                style: const TextStyle(fontSize: 18),
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFF211A40),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(color: Colors.white10),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      color: AppColors.p300,
                      strokeWidth: 2,
                    ),
                  ),
                  SizedBox(width: 9),
                  Text(
                    '이야기를 떠올리는 중...',
                    style: TextStyle(color: AppColors.gray, fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String get _voicePhaseLabel {
    switch (_voicePhase) {
      case _VoiceConversationPhase.listening:
        return '듣고 있어요';
      case _VoiceConversationPhase.thinking:
        return '말을 이해하고 답을 생각하고 있어요';
      case _VoiceConversationPhase.speaking:
        return '캐릭터가 답하고 있어요';
      case _VoiceConversationPhase.idle:
        return '';
    }
  }

  IconData get _voicePhaseIcon {
    switch (_voicePhase) {
      case _VoiceConversationPhase.listening:
        return Icons.graphic_eq_rounded;
      case _VoiceConversationPhase.thinking:
        return Icons.auto_awesome_rounded;
      case _VoiceConversationPhase.speaking:
        return Icons.volume_up_rounded;
      case _VoiceConversationPhase.idle:
        return Icons.mic_rounded;
    }
  }

  Widget _buildComposer(StoryCharacter character) {
    final suggestions = _suggestions[character.name] ?? _initialSuggestions;
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
      decoration: BoxDecoration(
        color: AppColors.bg2.withValues(alpha: 0.98),
        border: const Border(top: BorderSide(color: AppColors.border)),
        boxShadow: const [
          BoxShadow(
            color: Colors.black38,
            blurRadius: 20,
            offset: Offset(0, -5),
          ),
        ],
      ),
      child: Column(
        children: [
          SizedBox(
            height: 34,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: suggestions.length,
              separatorBuilder: (_, _) => const SizedBox(width: 7),
              itemBuilder: (context, index) {
                final suggestion = suggestions[index];
                return ActionChip(
                  onPressed: _isSending || _isVoiceConversationActive
                      ? null
                      : () => _sendMessage(suggestion),
                  avatar: const Icon(
                    Icons.auto_awesome_rounded,
                    color: AppColors.p300,
                    size: 13,
                  ),
                  label: Text(suggestion),
                  labelStyle: const TextStyle(
                    color: AppColors.p300,
                    fontSize: 10,
                  ),
                  backgroundColor: const Color(0xFF241B45),
                  disabledColor: const Color(0xFF19152D),
                  side: BorderSide(
                    color: AppColors.p500.withValues(alpha: 0.25),
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(999),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 10),
          if (_isVoiceConversationActive) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
              decoration: BoxDecoration(
                color: AppColors.pink.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(13),
                border: Border.all(
                  color: AppColors.pink.withValues(alpha: 0.38),
                ),
              ),
              child: Row(
                children: [
                  Icon(_voicePhaseIcon, color: AppColors.pink2, size: 18),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _voicePhaseLabel,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const Text(
                    '자동 대화',
                    style: TextStyle(
                      color: AppColors.pink2,
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: _messageController,
                  enabled: !_isSending && !_isVoiceConversationActive,
                  minLines: 1,
                  maxLines: 4,
                  maxLength: 300,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _sendMessage(),
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: '${character.name}에게 궁금한 것을 물어보세요',
                    hintStyle: const TextStyle(
                      color: AppColors.gray2,
                      fontSize: 12,
                    ),
                    counterText: '',
                    filled: true,
                    fillColor: const Color(0xFF17122F),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 13,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(17),
                      borderSide: BorderSide.none,
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(17),
                      borderSide: const BorderSide(color: AppColors.p500),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 9),
              IconButton.filled(
                tooltip: _isVoiceConversationActive
                    ? '음성 대화 끝내기'
                    : '음성으로 캐릭터와 대화하기',
                onPressed: _isVoiceConversationActive
                    ? _toggleVoiceConversation
                    : (_isSending || _isTranscribingVoice
                          ? null
                          : _toggleVoiceConversation),
                style: IconButton.styleFrom(
                  backgroundColor: _isVoiceConversationActive
                      ? AppColors.pink
                      : const Color(0xFF2B2352),
                  disabledBackgroundColor: AppColors.card2,
                  minimumSize: const Size(48, 48),
                ),
                icon: Icon(
                  _isVoiceConversationActive
                      ? Icons.call_end_rounded
                      : Icons.mic_rounded,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 7),
              IconButton.filled(
                tooltip: '메시지 보내기',
                onPressed: _isSending || _isVoiceConversationActive
                    ? null
                    : () => _sendMessage(),
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.p600,
                  disabledBackgroundColor: AppColors.card2,
                  minimumSize: const Size(48, 48),
                ),
                icon: const Icon(
                  Icons.arrow_upward_rounded,
                  color: Colors.white,
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            _isVoiceConversationActive
                ? '말을 멈추면 자동 전송되고, 답변이 끝나면 다시 듣습니다.'
                : '음성 대화는 서버 한국어 인식 후 동화 기반 AI 역할극으로 이어집니다.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.gray2, fontSize: 9),
          ),
        ],
      ),
    );
  }

  Widget _buildNoCharacter() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('📖', style: TextStyle(fontSize: 44)),
            const SizedBox(height: 12),
            const Text(
              '동화 속 친구를 찾지 못했어요.',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: () => _loadCharacters(forceFallback: true),
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('다시 찾아보기'),
            ),
          ],
        ),
      ),
    );
  }

  List<StoryCharacter> _fallbackCharacters(StorySession story) {
    final text = story.fullStoryText;
    final counts = <String, int>{};
    final patterns = [
      RegExp(r'([가-힣]{1,8}?)(?:이|가|은|는)\s*(?:말했|물었|대답|외쳤|웃었|생각했|고개를)'),
      RegExp(r'[“"]([가-힣]{1,8}?)(?:아|야)[,!?.…]'),
    ];
    const ignored = {
      '그때',
      '오늘',
      '마음',
      '친구',
      '모두',
      '누구',
      '주변',
      '이야기',
      '아이',
      '사람',
    };
    for (final pattern in patterns) {
      for (final match in pattern.allMatches(text)) {
        final name = match.group(1)?.trim() ?? '';
        if (name.length < 2 || ignored.contains(name)) continue;
        counts.update(name, (value) => value + 1, ifAbsent: () => 1);
      }
    }

    final names = counts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final selectedNames = names.take(4).map((entry) => entry.key).toList();
    if (selectedNames.isEmpty) {
      selectedNames.addAll(_knownCharacterNames(text));
    }
    if (selectedNames.isEmpty) selectedNames.add('이야기 속 주인공');

    return selectedNames.asMap().entries.map((entry) {
      final name = entry.value;
      final role = _roleFor(name, text, isFirst: entry.key == 0);
      return StoryCharacter(
        name: name,
        role: role,
        personality: entry.key == 0
            ? '용기 있게 길을 찾고 친구의 마음을 소중히 여겨요.'
            : '이야기 속 경험을 기억하며 다정하게 이야기해요.',
        greeting: '안녕! 나는 $name이야. 우리 동화에서 궁금했던 장면이 있니?',
        avatarEmoji: _emojiFor(name, role),
      );
    }).toList();
  }

  List<String> _knownCharacterNames(String text) {
    const known = {
      '별이': '별이',
      '토끼': '작은 토끼',
      '여우': '여우 친구',
      '요정': '숲의 요정',
      '공주': '공주',
      '왕자': '왕자',
      '용': '용 친구',
      '부엉이': '부엉이',
      '나비': '별나비',
    };
    return known.entries
        .where((entry) => text.contains(entry.key))
        .map((entry) => entry.value)
        .take(4)
        .toList();
  }

  String _roleFor(String name, String text, {required bool isFirst}) {
    if (name.contains('공주')) return '도움을 기다리던 공주';
    if (name.contains('용')) return '이야기의 용';
    if (name.contains('요정')) return '마법을 아는 안내자';
    if (name.contains('여우') || name.contains('친구')) return '함께한 동료';
    if (text.contains('$name에게 도움')) return '도움을 준 친구';
    return isFirst ? '이야기의 주인공' : '이야기 속 친구';
  }

  String _emojiFor(String name, String role) {
    final value = '$name $role';
    if (value.contains('공주')) return '👑';
    if (value.contains('왕자')) return '🤴';
    if (value.contains('용')) return '🐉';
    if (value.contains('토끼')) return '🐰';
    if (value.contains('여우')) return '🦊';
    if (value.contains('요정')) return '🧚';
    if (value.contains('부엉이')) return '🦉';
    if (value.contains('나비')) return '🦋';
    if (value.contains('별')) return '⭐';
    return role.contains('주인공') ? '🧒' : '✨';
  }
}

class _ChatBackground extends StatelessWidget {
  const _ChatBackground();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF08051B), Color(0xFF120B2B), Color(0xFF09061D)],
        ),
      ),
    );
  }
}

class _VoiceConversationOverlay extends StatefulWidget {
  const _VoiceConversationOverlay({
    required this.character,
    required this.phase,
    required this.status,
    required this.onEnd,
  });

  final StoryCharacter character;
  final _VoiceConversationPhase phase;
  final String? status;
  final VoidCallback onEnd;

  @override
  State<_VoiceConversationOverlay> createState() =>
      _VoiceConversationOverlayState();
}

class _VoiceConversationOverlayState extends State<_VoiceConversationOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1050),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  bool get _isListening => widget.phase == _VoiceConversationPhase.listening;
  bool get _isThinking => widget.phase == _VoiceConversationPhase.thinking;
  bool get _isSpeaking => widget.phase == _VoiceConversationPhase.speaking;

  Color get _accent {
    if (_isListening) return const Color(0xFFFB7185);
    if (_isSpeaking) return const Color(0xFF64D8CB);
    return AppColors.p300;
  }

  IconData get _phaseIcon {
    if (_isListening) return Icons.mic_rounded;
    if (_isSpeaking) return Icons.record_voice_over_rounded;
    return Icons.auto_awesome_rounded;
  }

  String get _phaseTitle {
    if (_isListening) return '듣고 있어요';
    if (_isSpeaking) return '${widget.character.name}가 말하고 있어요';
    return '${widget.character.name}가 생각하고 있어요';
  }

  String get _phaseHint {
    if (_isListening) return '말을 멈추면 자동으로 메시지를 보낼게요.';
    if (_isSpeaking) return '답변이 끝나면 다시 자동으로 들을게요.';
    return '동화 속 기억을 떠올려 답을 만들고 있어요.';
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.25),
            radius: 1.2,
            colors: [Color(0xFF281B50), Color(0xFF100A25), Color(0xFF070411)],
          ),
        ),
        child: SafeArea(
          child: Stack(
            children: [
              Positioned(
                top: 12,
                left: 18,
                right: 18,
                child: Row(
                  children: [
                    Container(
                      width: 42,
                      height: 42,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.08),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white12),
                      ),
                      child: Text(
                        widget.character.avatarEmoji,
                        style: const TextStyle(fontSize: 22),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            widget.character.name,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            '음성 대화 중',
                            style: TextStyle(
                              color: AppColors.gray,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: '음성 대화 끝내기',
                      onPressed: widget.onEnd,
                      style: IconButton.styleFrom(
                        foregroundColor: Colors.white,
                        backgroundColor: Colors.white.withValues(alpha: 0.08),
                      ),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ],
                ),
              ),
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 480),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 28),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _buildPulseCore(),
                        const SizedBox(height: 28),
                        AnimatedDefaultTextStyle(
                          duration: const Duration(milliseconds: 240),
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: _isSpeaking ? 25 : 23,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.5,
                          ),
                          child: Text(_phaseTitle, textAlign: TextAlign.center),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          _phaseHint,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: AppColors.gray,
                            fontSize: 13,
                            height: 1.45,
                          ),
                        ),
                        const SizedBox(height: 24),
                        Container(
                          width: double.infinity,
                          constraints: const BoxConstraints(minHeight: 58),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 12,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.07),
                            borderRadius: BorderRadius.circular(18),
                            border: Border.all(color: Colors.white12),
                          ),
                          child: Center(
                            child: Text(
                              widget.status?.trim().isNotEmpty == true
                                  ? widget.status!
                                  : _phaseHint,
                              textAlign: TextAlign.center,
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 12,
                                height: 1.45,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              Positioned(
                left: 24,
                right: 24,
                bottom: 24,
                child: FilledButton.icon(
                  onPressed: widget.onEnd,
                  icon: const Icon(Icons.call_end_rounded),
                  label: const Text('음성 대화 끝내기'),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(54),
                    backgroundColor: const Color(0xFFCF4560),
                    foregroundColor: Colors.white,
                    textStyle: const TextStyle(fontWeight: FontWeight.w800),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPulseCore() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, _) {
        final pulse = _pulseController.value;
        return SizedBox(
          width: 286,
          height: 286,
          child: Stack(
            alignment: Alignment.center,
            children: [
              for (final ring in [0.62, 0.79, 0.96])
                Transform.scale(
                  scale: ring + pulse * 0.055,
                  child: Container(
                    width: 248,
                    height: 248,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: _accent.withValues(
                          alpha: _isThinking ? 0.1 : 0.08 + pulse * 0.1,
                        ),
                        width: 1.2,
                      ),
                    ),
                  ),
                ),
              AnimatedContainer(
                duration: const Duration(milliseconds: 260),
                width: _isSpeaking ? 142 : 130,
                height: _isSpeaking ? 142 : 130,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _accent.withValues(alpha: 0.2),
                  border: Border.all(
                    color: _accent.withValues(alpha: 0.8),
                    width: 2,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: _accent.withValues(alpha: 0.28 + pulse * 0.2),
                      blurRadius: 32 + pulse * 18,
                      spreadRadius: 3 + pulse * 3,
                    ),
                  ],
                ),
                child: Icon(_phaseIcon, color: Colors.white, size: 54),
              ),
              Positioned(bottom: 0, child: _buildWaveform(pulse)),
            ],
          ),
        );
      },
    );
  }

  Widget _buildWaveform(double pulse) {
    const baseHeights = [14.0, 24.0, 37.0, 50.0, 37.0, 24.0, 14.0];
    return SizedBox(
      height: 58,
      width: 150,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: List.generate(baseHeights.length, (index) {
          final direction = index.isEven ? pulse : 1 - pulse;
          final scale = _isThinking
              ? 0.34 + pulse * 0.12
              : 0.46 + direction * 0.72;
          return AnimatedContainer(
            duration: const Duration(milliseconds: 100),
            width: 7,
            height: baseHeights[index] * scale,
            margin: const EdgeInsets.symmetric(horizontal: 2.5),
            decoration: BoxDecoration(
              color: _accent.withValues(alpha: 0.72),
              borderRadius: BorderRadius.circular(999),
            ),
          );
        }),
      ),
    );
  }
}

class _UseLocalCharacters implements Exception {
  const _UseLocalCharacters();
}
