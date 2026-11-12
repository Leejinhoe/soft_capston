import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/story_genres.dart';
import 'package:just_audio/just_audio.dart';

import '../widgets/custom_bottom_nav.dart';
import '../widgets/scene_video.dart';
import '../widgets/character_strip.dart';
import 'family_voice_page.dart';

/// 장면을 만든 엔진 → 화면에 작게 표시. 우리 팀 AI(Colab) 장면에만 보여 주고,
/// 다른 엔진으로 넘어간 건 아이 화면에 드러내지 않음 (서버 로그에만)
const Map<String, String> _engineLabels = {
  'colab': '🤖 우리 팀 AI',
};

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
// 선택지 버튼: 진한 그라데이션 대신 은은하게 (팀원 화면처럼 색 12% 배경 + 40% 얇은 테두리 + 흰 글자)
const _choiceBgAlpha = 0.12;
const _choiceBorderAlpha = 0.4;
const _finishColor = Color(0xFFFBBF24); // 이야기 마무리하기 (노랑, 같은 톤)

// 로딩 문구 (돌아가며 보여 줌). 우리 팀 AI가 쓸 때와 아닐 때 느낌만 다르게,
// 어느 쪽이든 엔진 이름이나 "대신", "쉬어서" 같은 말은 쓰지 않음
const _ourAiSceneMessages = [
  '✍️ 이야기 요정이 한 글자 한 글자 동화를 적고 있어요',
  '🤖 우리 팀 AI가 다음 장면을 쓰고 있어요',
  '📝 연필이 사각사각, 새 장면이 태어나는 중이에요',
  '🌱 이야기 씨앗이 쑥쑥 자라고 있어요',
  '💭 주인공이 다음에 무엇을 할지 곰곰이 생각 중이에요',
];
const _ourAiEndingMessages = [
  '✍️ 이야기 요정이 마지막 장면을 정성껏 적고 있어요',
  '🤖 우리 팀 AI가 따뜻한 결말을 쓰고 있어요',
  '🌙 이야기가 포근하게 끝나도록 마무리하고 있어요',
  '🏷️ 이야기에 어울리는 제목을 짓고 있어요',
  '🧺 배울 단어를 골라 담고 있어요',
];
const _gentleSceneMessages = [
  '🌟 곧 동화가 완성돼요, 조금만 기다려 주세요',
  '📖 책장을 사르륵 넘기는 중이에요',
  '✨ 별님이 반짝반짝 다음 이야기를 떠올리고 있어요',
  '💓 두근두근, 무슨 일이 생길까요?',
  '🎈 신나는 장면을 준비하고 있어요',
];
const _gentleEndingMessages = [
  '🌟 곧 동화가 완성돼요, 조금만 기다려 주세요',
  '🌙 따뜻한 결말을 준비하고 있어요',
  '🏷️ 이야기에 어울리는 제목을 짓고 있어요',
  '🧺 배울 단어를 골라 담고 있어요',
  '🛏️ 포근한 이불을 덮어 주는 중이에요',
];
// 엔진을 알기 전(요청 직후)
const _sceneLoadingMessages = _gentleSceneMessages;
const _endingLoadingMessages = _gentleEndingMessages;

class _StoryPageState extends State<StoryPage> {
  final Map<String, Future<Uint8List?>> _sceneImages = {};
  final Set<int> _generatingImages = {};
  final Set<int> _generatingVideos = {};

  // 🎬 팀원 미디어 기능(캐릭터 그림·영상)이 서버에 설정돼 있을 때만 버튼을 보여 줌 (GET /api/media/status)
  // 화면을 열 때마다 다시 물어봐서, 서버 .env에 키를 넣으면 다음부터 자동으로 보임
  bool _mediaImage = false;
  bool _mediaVideo = false;

  Future<void> _loadMediaStatus() async {
    try {
      final response = await ApiClient.get('/api/media/status');
      final data = ApiClient.decode(response);
      if (!mounted || response.statusCode != 200 || data is! Map) return;
      setState(() {
        _mediaImage = data['image'] == true;
        _mediaVideo = data['video'] == true;
      });
    } catch (_) {
      // 못 받으면 버튼을 숨긴 채로 둠
    }
  }

  Future<void> _assembleJourneyVideo() async {
    if (storyId.isEmpty || _assemblingVideo) return;
    setState(() => _assemblingVideo = true);
    try {
      final response = await ApiClient.post('/api/stories/$storyId/journey-video');
      if (!mounted) return;
      if (response.statusCode == 200) {
        _applyState(ApiClient.decode(response));
      } else {
        _toast(ApiClient.errorMessage(response, '동화 영상을 만들지 못했어요.'));
      }
    } catch (_) {
      _toast('서버에 연결하지 못했어요.');
    } finally {
      if (mounted) setState(() => _assemblingVideo = false);
    }
  }

  Future<void> _generateSceneVideo(int number) async {
    if (storyId.isEmpty || _generatingVideos.contains(number)) return;
    setState(() => _generatingVideos.add(number));
    try {
      final response = await ApiClient.post('/api/stories/$storyId/scenes/$number/video');
      if (!mounted) return;
      if (response.statusCode == 200) {
        _applyState(ApiClient.decode(response));
      } else {
        _toast(ApiClient.errorMessage(response, '영상을 생성하지 못했어요.'));
      }
    } catch (_) {
      _toast('서버에 연결하지 못했어요.');
    } finally {
      if (mounted) setState(() => _generatingVideos.remove(number));
    }
  }

  Future<void> _generateSceneImage(int number) async {
    if (storyId.isEmpty || _generatingImages.contains(number)) return;
    setState(() => _generatingImages.add(number));
    try {
      final response = await ApiClient.post('/api/stories/$storyId/scenes/$number/image');
      if (!mounted) return;
      if (response.statusCode == 200) {
        _applyState(ApiClient.decode(response));
      } else {
        _toast(ApiClient.errorMessage(response, '이미지를 생성하지 못했어요.'));
      }
    } catch (_) {
      _toast('서버에 연결하지 못했어요.');
    } finally {
      if (mounted) setState(() => _generatingImages.remove(number));
    }
  }

  Future<Uint8List?> _loadSceneImage(int number) async {
    final response = await ApiClient.get('/api/stories/$storyId/scenes/$number/image');
    return response.statusCode == 200 ? response.bodyBytes : null;
  }
  final TextEditingController promptController = TextEditingController();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final ScrollController _scrollController = ScrollController();

  String selectedGenre = '판타지';
  String selectedAge = '5-7세';
  String characterGender = 'male';
  String selectedCharacterKey = 'male_01';

  bool isPlayingTTS = false; // 🔊 TTS 재생 상태 관리
  bool isSharing = false;

  // 🔊 동화 듣기: 장면별로 읽기 (backend/voices.py)
  List<Map<String, dynamic>> voices = [
    {'id': 'default', 'name': '기본 목소리(기계음)', 'is_default': true},
  ];
  String selectedVoiceId = 'default';
  String voiceHint = '';
  int ttsScene = 0; // 지금 읽는 장면 번호 (0 = 안 읽는 중)
  bool ttsLoading = false;
  bool _ttsContinuous = false; // true면 장면이 끝나면 다음 장면으로
  int _ttsToken = 0; // 멈추거나 새로 누르면 바뀜 → 예전 요청 결과는 버림
  bool _fallbackToastShown = false;

  // 🎨 장면 그림 (backend/story_images.py)
  final Set<int> _imageLoading = {};
  bool _imageQueueRunning = false;

  // 진행 중인 동화 상태 (서버 응답 그대로)
  String storyId = ''; // 생성 즉시 저장된 동화 id (커뮤니티 공유 시 원본 연결용)
  String storyTitle = '';
  String assembledVideoUrl = '';
  bool _assemblingVideo = false;
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

  // ✍️ 스트리밍: 우리 팀 AI(Colab)가 쓰는 글을 받는 대로 한 글자씩 보여 주기 (backend/branching.py /stream)
  String _streamEngine = ''; // 지금 쓰고 있는 엔진 (colab / gemini / template)
  String _streamTarget = ''; // 서버가 보낸 지금까지의 본문
  int _streamShown = 0; // 화면에 보인 글자 수 (타자기 효과)
  String _streamStatus = ''; // "선택지를 준비하고 있어요" 같은 다음 단계 안내
  Timer? _typeTimer;

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
        _onSceneAudioDone();
      }
    });
    _loadVoices();
    _loadMediaStatus();
    final resumeId = widget.resumeStoryId;
    if (resumeId != null && resumeId.isNotEmpty) _loadStory(resumeId);
  }

  @override
  void dispose() {
    _loadingTimer?.cancel();
    _typeTimer?.cancel();
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
      assembledVideoUrl = (data['assembled_video_url'] ?? '').toString();
      status = (data['status'] ?? '').toString();
      final characterKey = data['character_key'];
      if (characterKey is String && RegExp(r'^(male|female)_0[1-8]$').hasMatch(characterKey)) {
        selectedCharacterKey = characterKey;
        characterGender = characterKey.split('_').first;
      }
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
    _requestImages();
  }

  // ---------- 🎨 장면 그림: 본문이 먼저 나오고, 그림은 따로 받아서 장면 위에 ----------
  bool _needsImage(Map<String, dynamic> s) =>
      (s['image_url'] == null || s['image_url'].toString().isEmpty) && s['image_failed'] != true;

  /// 그림 없는 장면을 하나씩 차례로 요청 (Colab GPU가 한 번에 하나씩 그리게)
  Future<void> _requestImages() async {
    if (_imageQueueRunning || storyId.isEmpty) return;
    _imageQueueRunning = true;
    try {
      while (mounted) {
        final id = storyId;
        final index = scenes.indexWhere(_needsImage);
        if (index < 0) break;
        final number = index + 1;
        setState(() => _imageLoading.add(number));
        String status = 'failed';
        String? url;
        for (var attempt = 0; attempt < 6; attempt++) {
          try {
            final response = await ApiClient.post('/api/stories/$id/scenes/$number/colab-image');
            final data = ApiClient.decode(response);
            status = response.statusCode == 200 && data is Map ? (data['status'] ?? 'failed').toString() : 'failed';
            url = data is Map ? data['image_url']?.toString() : null;
          } catch (_) {
            status = 'failed';
          }
          if (status != 'busy') break;
          await Future.delayed(const Duration(seconds: 6)); // 다른 요청이 그리는 중
        }
        if (!mounted) return;
        if (storyId != id) break; // 그사이 다른 동화로 바뀜
        setState(() {
          _imageLoading.remove(number);
          if (index < scenes.length) {
            if (status == 'ready' && url != null) {
              scenes[index]['image_url'] = url;
            } else {
              scenes[index]['image_failed'] = true; // 그림 없이 그냥 진행
            }
          }
        });
      }
    } finally {
      _imageQueueRunning = false;
      if (mounted) setState(() => _imageLoading.clear());
    }
  }

  // ---------- 🔊 목소리 목록 ----------
  Future<void> _loadVoices() async {
    try {
      final response = await ApiClient.get('/api/voices');
      if (!mounted || response.statusCode != 200) return;
      final data = ApiClient.decode(response);
      if (data is! Map) return;
      final list = ((data['voices'] as List?) ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (list.isEmpty) return;
      setState(() {
        voices = list;
        voiceHint = (data['hint'] ?? '').toString();
        if (!voices.any((v) => v['id'] == selectedVoiceId)) selectedVoiceId = 'default';
      });
    } catch (_) {}
  }

  Future<void> _openVoicePage() async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => const FamilyVoicePage()));
    _loadVoices();
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

  /// 장면 만들기 공통: 스트리밍(`path/stream`)을 먼저 쓰고, 스트리밍 연결이 안 되면 일반 API로
  Future<void> _runStep(String path, Map<String, dynamic> body,
      {required List<String> messages}) async {
    if (isBusy) return;
    _startLoading(messages);
    _resetStream();
    try {
      final handled = await _tryStream('$path/stream', body);
      if (!handled && mounted) {
        _resetStream();
        await _runPlain(path, body);
      }
    } finally {
      _typeTimer?.cancel();
      _typeTimer = null;
      _stopLoading();
      _scrollToBottom();
    }
  }

  void _resetStream() {
    _typeTimer?.cancel();
    _typeTimer = null;
    if (!mounted) return;
    setState(() {
      _streamEngine = '';
      _streamTarget = '';
      _streamShown = 0;
      _streamStatus = '';
    });
  }

  /// 타자기 효과: 서버가 보낸 글(_streamTarget)을 조금씩 따라가며 보여 줌 (많이 밀리면 빨리)
  void _startTyping() {
    _typeTimer ??= Timer.periodic(const Duration(milliseconds: 35), (_) {
      if (!mounted) return;
      final remain = _streamTarget.length - _streamShown;
      if (remain <= 0) return;
      setState(() => _streamShown += remain > 60 ? (remain / 20).ceil() : 1);
      if (_streamShown % 40 == 0) _scrollToBottom();
    });
  }

  /// true = 스트리밍으로 끝냄(성공이든 안내든), false = 스트리밍을 못 써서 일반 API로 다시
  Future<bool> _tryStream(String path, Map<String, dynamic> body) async {
    final NdjsonResponse response;
    try {
      response = await ApiClient.postNdjson(path, body: body);
    } catch (e) {
      debugPrint('스트리밍 연결 실패 → 일반 호출: $e');
      return false;
    }
    if (!mounted) return true;
    final error = response.error;
    if (error != null) {
      final code = response.statusCode;
      // 404/405: 예전 서버(스트리밍 없음), 5xx: 서버 문제 → 일반 API로 한 번 더
      if (code == 404 || code == 405 || code >= 500) return false;
      _toast(ApiClient.errorMessage(error));
      if (code == 409 && storyId.isNotEmpty) await _loadStory(storyId, quiet: true);
      return true;
    }
    try {
      await for (final event in response.events!) {
        if (!mounted) return true;
        switch (event['type']) {
          case 'engine':
            setState(() {
              _streamEngine = (event['engine'] ?? '').toString();
              _streamStatus = ''; // 앞 엔진의 안내는 지움 (엔진이 바뀐 건 화면에 말하지 않음)
            });
          case 'text':
            setState(() {
              _streamTarget = (event['text'] ?? '').toString();
              if (_streamShown > _streamTarget.length) _streamShown = _streamTarget.length;
            });
            _startTyping();
          case 'reset':
            _typeTimer?.cancel();
            _typeTimer = null;
            setState(() {
              _streamTarget = '';
              _streamShown = 0;
            });
          case 'status':
            setState(() => _streamStatus = (event['message'] ?? '').toString());
          case 'state':
            _applyState(event['state']);
            return true;
          case 'error':
            _toast((event['message'] ?? '문제가 생겼어요. 잠시 후 다시 눌러 주세요.').toString());
            if (event['status'] == 409 && storyId.isNotEmpty) await _loadStory(storyId, quiet: true);
            return true;
        }
      }
    } catch (e) {
      debugPrint('스트리밍 중 끊김: $e');
    }
    // 중간에 끊김: 서버는 끝까지 만들어 저장하니, 일반 API로 또 만들지 않고 저장될 때까지 기다렸다가 불러옴
    await _waitForSaved();
    return true;
  }

  Future<void> _waitForSaved() async {
    final id = storyId;
    final before = scenes.length;
    if (mounted) setState(() => _streamStatus = '연결이 잠깐 끊겼어요. 다 쓰면 불러올게요 📡');
    for (var i = 0; i < 30 && mounted; i++) {
      await Future.delayed(const Duration(seconds: 5));
      if (id.isEmpty) {
        // 첫 장면이면 동화 id를 몰라서 마이페이지에서 이어하기로 안내
        _toast('동화가 다 써지면 마이페이지 "내가 만든 동화"에서 이어할 수 있어요 📚');
        return;
      }
      try {
        final response = await ApiClient.get('/api/stories/$id/branching');
        final data = ApiClient.decode(response);
        if (response.statusCode == 200 && data is Map && ((data['scenes'] as List?)?.length ?? 0) > before) {
          _applyState(data);
          return;
        }
      } catch (_) {}
    }
    _toast('이야기를 불러오지 못했어요. 잠시 후 마이페이지에서 이어해 주세요.');
  }

  /// 일반 API (스트리밍을 못 쓸 때): 성공하면 화면 갱신, 409(이미 넘어감)면 서버 상태로 다시 맞춤
  Future<void> _runPlain(String path, Map<String, dynamic> body) async {
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
    }
  }

  // ✨ 동화 시작: 첫 장면 + 선택지 3개
  Future<void> startStory() async {
    if (promptController.text.trim().isEmpty) {
      _toast('동화 주제를 입력해주세요.');
      return;
    }
    await stopTTS();
    setState(() {
      storyId = '';
      assembledVideoUrl = '';
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
        'character_key': selectedCharacterKey,
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
    await stopTTS();
    setState(() {
      storyId = '';
      storyTitle = '';
      status = '';
      scenes = [];
      vocabList = [];
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

  // 🔊 동화 듣기: 장면 하나씩 서버(/api/tts)에서 오디오 주소를 받아 재생
  // 서버가 목소리+장면별로 파일을 저장해 두어서 다시 들을 때는 바로 나옴
  Future<void> stopTTS() async {
    _ttsToken++;
    _ttsContinuous = false;
    await _audioPlayer.stop();
    if (mounted) {
      setState(() {
        isPlayingTTS = false;
        ttsLoading = false;
        ttsScene = 0;
      });
    }
  }

  /// 처음부터 끝까지 이어서 듣기 (버튼을 다시 누르면 멈춤)
  Future<void> playTTS() async {
    if (storyText.isEmpty || storyId.isEmpty) return;
    if (isPlayingTTS || ttsLoading) {
      await stopTTS();
      return;
    }
    _ttsContinuous = true;
    _fallbackToastShown = false;
    await _playScene(1);
  }

  /// 장면 하나만 듣기 (장면 카드의 🔊)
  Future<void> playSceneTTS(int number) async {
    if (ttsScene == number && (isPlayingTTS || ttsLoading)) {
      await stopTTS();
      return;
    }
    await stopTTS();
    _ttsContinuous = false;
    _fallbackToastShown = false;
    await _playScene(number);
  }

  Future<Map?> _fetchTts(int number) async {
    final response = await ApiClient.post('/api/tts', body: {
      'story_id': storyId,
      'scene_number': number,
      'voice_id': selectedVoiceId,
    });
    if (response.statusCode == 404 && selectedVoiceId != 'default') {
      _loadVoices(); // 지워진 목소리
    }
    if (response.statusCode != 200) throw Exception(ApiClient.errorMessage(response));
    final data = ApiClient.decode(response);
    return data is Map ? data : null;
  }

  Future<void> _playScene(int number) async {
    final token = ++_ttsToken;
    setState(() {
      ttsScene = number;
      ttsLoading = true;
      isPlayingTTS = false;
    });
    try {
      final data = await _fetchTts(number);
      if (!mounted || token != _ttsToken) return;
      final url = (data?['audio_url'] ?? '').toString();
      if (url.isEmpty) throw Exception('오디오 주소가 없어요');
      final message = (data?['message'] ?? '').toString();
      if (data?['fallback'] == true && !_fallbackToastShown) {
        _fallbackToastShown = true;
        _toast(message.isNotEmpty ? message : '기본 목소리로 읽어 줄게요.');
      }
      await _audioPlayer.setAudioSource(AudioSource.uri(Uri.parse('$kApiBaseUrl$url')));
      if (!mounted || token != _ttsToken) return;
      setState(() {
        ttsLoading = false;
        isPlayingTTS = true;
      });
      // 다음 장면 오디오를 미리 만들어 두기 (서버에 저장되니 결과는 버려도 됨)
      if (_ttsContinuous && number < scenes.length) {
        _fetchTts(number + 1).catchError((_) => null);
      }
      await _audioPlayer.play();
    } catch (e) {
      debugPrint('TTS 재생 오류: $e');
      if (!mounted || token != _ttsToken) return;
      setState(() {
        isPlayingTTS = false;
        ttsLoading = false;
        ttsScene = 0;
      });
      _toast('목소리를 불러오지 못했어요. 잠시 후 다시 눌러 주세요.');
    }
  }

  void _onSceneAudioDone() {
    if (!mounted) return;
    final next = ttsScene + 1;
    if (_ttsContinuous && ttsScene > 0 && next <= scenes.length) {
      _playScene(next);
    } else {
      _ttsContinuous = false;
      setState(() {
        isPlayingTTS = false;
        ttsScene = 0;
      });
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
            return _StoryWord(
              word: word,
              onTap: () => fetchAndShowVocabDialog(word, line),
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
    final rawImageUrl = (scene['image_url'] ?? '').toString().trim();
    // 캐릭터 그림(팀원, GridFS)은 /api/media/images/… → 로그인 토큰으로 받아서 보여 줌.
    // Colab 그림(/static/…)은 _sceneImage가 그대로 보여 줌
    final imageUrl = rawImageUrl.startsWith('/api/media/images/') ? rawImageUrl : '';
    final videoUrl = (scene['video_url'] ?? '').toString().trim();
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
          Row(
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
              const SizedBox(width: 8),
              if (_engineLabels[scene['engine']] != null)
                Text(
                  _engineLabels[scene['engine']]!,
                  style: const TextStyle(color: Colors.white38, fontSize: 11),
                ),
              const Spacer(),
              _sceneListenButton(number),
            ],
          ),
          const SizedBox(height: 14),
          _sceneImage(scene, number),
          buildClickableStoryText((scene['text'] ?? '').toString()),
          if (imageUrl.isNotEmpty) ...[
            const SizedBox(height: 14),
            Center(
              child: FutureBuilder<Uint8List?>(
                future: _sceneImages.putIfAbsent(
                  '$storyId:$number:$imageUrl', () => _loadSceneImage(number)),
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const CircularProgressIndicator();
                  }
                  final bytes = snapshot.data;
                  if (bytes == null || bytes.isEmpty) {
                    return const Text('장면 이미지를 불러오지 못했어요.',
                        style: TextStyle(color: Colors.white70));
                  }
                  return Image.memory(bytes, height: 280, fit: BoxFit.contain);
                },
              ),
            ),
          ],
          if (_mediaImage && rawImageUrl.isEmpty && storyId.isNotEmpty && !_imageLoading.contains(number)) ...[
            const SizedBox(height: 12),
            TextButton.icon(
              onPressed: _generatingImages.contains(number) ? null : () => _generateSceneImage(number),
              icon: const Icon(Icons.image_outlined),
              label: Text(_generatingImages.contains(number) ? '이미지 생성 중' : '장면 이미지 만들기'),
            ),
          ],
          if (videoUrl.isNotEmpty && storyId.isNotEmpty)
            ExpansionTile(
              title: const Text('장면 영상', style: TextStyle(color: Colors.white)),
              children: [SceneVideo(storyId: storyId, sceneNumber: number)],
            ),
          if (_mediaVideo && videoUrl.isEmpty && imageUrl.isNotEmpty && storyId.isNotEmpty)
            TextButton.icon(
              onPressed: _generatingVideos.contains(number) ? null : () => _generateSceneVideo(number),
              icon: const Icon(Icons.movie_creation_outlined),
              label: Text(_generatingVideos.contains(number) ? '영상 생성 중' : '장면 영상 만들기'),
            ),
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

  Widget _sceneImage(Map<String, dynamic> scene, int number) {
    final url = (scene['image_url'] ?? '').toString();
    if (url.isNotEmpty && !url.startsWith('/api/media/')) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(18),
          child: AspectRatio(
            aspectRatio: 1,
            child: Image.network(
              '$kApiBaseUrl$url',
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => const SizedBox.shrink(),
              loadingBuilder: (context, child, progress) => progress == null
                  ? child
                  : Container(color: Colors.white10),
            ),
          ),
        ),
      );
    }
    if (_imageLoading.contains(number)) {
      return Container(
        width: double.infinity,
        height: 120,
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.05),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: Colors.white10),
        ),
        child: const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.purpleAccent)),
            SizedBox(height: 10),
            Text('🎨 그림 요정이 이 장면을 그리고 있어요',
                style: TextStyle(color: Colors.white60, fontSize: 13)),
          ],
        ),
      );
    }
    return const SizedBox.shrink();
  }

  Widget _sceneListenButton(int number) {
    final active = ttsScene == number;
    if (active && ttsLoading) {
      return const Padding(
        padding: EdgeInsets.all(10),
        child: SizedBox(
            width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.purpleAccent)),
      );
    }
    return IconButton(
      tooltip: active ? '그만 듣기' : '이 장면 듣기',
      visualDensity: VisualDensity.compact,
      onPressed: () => playSceneTTS(number),
      icon: Icon(
        active && isPlayingTTS ? Icons.stop_circle_outlined : Icons.volume_up_rounded,
        color: active ? Colors.amberAccent : Colors.white54,
      ),
    );
  }

  /// 어떤 목소리로 들을지 고르기 (맨 앞은 항상 기본 목소리)
  Widget _voicePicker() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A0B3A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: DropdownButton<String>(
        value: selectedVoiceId,
        dropdownColor: const Color(0xFF1A0B3A),
        underline: const SizedBox(),
        isExpanded: true,
        iconEnabledColor: Colors.white70,
        style: const TextStyle(color: Colors.white, fontSize: 14),
        items: voices
            .map((v) => DropdownMenuItem<String>(
                  value: v['id'].toString(),
                  child: Text(
                    '${v['is_default'] == true ? '🤖' : '🎙️'} ${v['name']}',
                    overflow: TextOverflow.ellipsis,
                  ),
                ))
            .toList(),
        onChanged: (value) async {
          if (value == null || value == selectedVoiceId) return;
          await stopTTS();
          setState(() => selectedVoiceId = value);
        },
      ),
    );
  }

  Widget _listenArea() {
    final reading = isPlayingTTS || ttsLoading;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              flex: 5,
              child: ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: reading ? const Color(0xFF5B21B6) : const Color(0xFF8B5CF6),
                  padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                onPressed: playTTS,
                icon: ttsLoading
                    ? const SizedBox(
                        width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : Icon(reading ? Icons.stop_circle : Icons.volume_up_rounded, color: Colors.white),
                label: Text(
                  ttsLoading
                      ? '목소리 준비 중… (장면 $ttsScene)'
                      : isPlayingTTS
                          ? '읽어주는 중 (장면 $ttsScene/${scenes.length})'
                          : '동화 듣기',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(flex: 4, child: _voicePicker()),
          ],
        ),
        if (voiceHint.isNotEmpty && voices.length <= 1)
          TextButton.icon(
            onPressed: _openVoicePage,
            icon: const Icon(Icons.mic_none, size: 18, color: Colors.purpleAccent),
            label: Text(voiceHint,
                style: const TextStyle(color: Colors.purpleAccent, fontSize: 13)),
          ),
      ],
    );
  }

  /// 생성 중: 글이 오기 시작했으면 쓰는 중인 장면 카드, 아니면 엔진별 로딩 문구(돌아가며)
  Widget _loadingCard() {
    if (_streamTarget.isNotEmpty) return _writingCard();
    final ending = identical(_loadingMessages, _endingLoadingMessages);
    final List<String> messages;
    if (_streamEngine == 'colab') {
      messages = ending ? _ourAiEndingMessages : _ourAiSceneMessages;
    } else if (_streamEngine.isNotEmpty) {
      messages = ending ? _gentleEndingMessages : _gentleSceneMessages;
    } else {
      messages = _loadingMessages;
    }
    return _loadingBox(messages[_loadingIndex % messages.length], sub: _streamStatus);
  }

  /// 우리 팀 AI가 쓰는 글이 한 글자씩 나타나는 카드
  Widget _writingCard() {
    final shown = _streamTarget.substring(0, _streamShown.clamp(0, _streamTarget.length));
    final typing = _streamShown < _streamTarget.length;
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF140028),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: const Color(0xFF8B5CF6), width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                decoration: BoxDecoration(
                  color: Colors.purple.withOpacity(0.22),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Text(
                  '✍️ 장면 ${scenes.length + 1} 쓰는 중',
                  style: const TextStyle(color: Colors.purpleAccent, fontSize: 13, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(width: 8),
              if (_engineLabels[_streamEngine] != null)
                Text(_engineLabels[_streamEngine]!,
                    style: const TextStyle(color: Colors.white38, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 14),
          Text.rich(
            TextSpan(children: [
              TextSpan(text: shown),
              if (typing) const TextSpan(text: ' ▍', style: TextStyle(color: Colors.purpleAccent)),
            ]),
            style: const TextStyle(color: Colors.white, fontSize: 18, height: 1.6),
          ),
          if (!typing) ...[
            const SizedBox(height: 16),
            Row(
              children: [
                const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.purpleAccent)),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    _streamStatus.isNotEmpty ? _streamStatus : '🌟 다음 이야기를 준비하고 있어요',
                    style: const TextStyle(color: Colors.white60, fontSize: 14),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _loadingBox(String message, {String sub = ''}) {
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
          if (sub.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(sub,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.4)),
          ],
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
              color: colors.first.withValues(alpha: _choiceBgAlpha),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: colors.first.withValues(alpha: _choiceBorderAlpha)),
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
                const SizedBox(width: 8),
                Icon(Icons.arrow_forward_ios_rounded, color: colors.first, size: 16),
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
              foregroundColor: _finishColor,
              backgroundColor: _finishColor.withValues(alpha: _choiceBgAlpha),
              side: BorderSide(color: _finishColor.withValues(alpha: _choiceBorderAlpha)),
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
        // 🔊 동화 듣기 + 목소리 고르기
        _listenArea(),
        const SizedBox(height: 12),
        // 🎬 동화 영상 (팀원 기능)
        if (assembledVideoUrl.isNotEmpty)
          SceneVideo(key: ValueKey(assembledVideoUrl), storyId: storyId, sceneNumber: 0, journey: true),
        if (_mediaVideo) ...[
          TextButton.icon(
            onPressed: _assemblingVideo ? null : _assembleJourneyVideo,
            icon: const Icon(Icons.movie_outlined),
            label: Text(_assemblingVideo ? '동화 영상 만드는 중' : '동화 영상 만들기'),
          ),
          const SizedBox(height: 12),
        ],
        // 🌐 커뮤니티 공유
        Row(
          children: [
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
        CharacterStrip(
          gender: characterGender,
          selectedKey: selectedCharacterKey,
          onGenderChanged: (gender) => setState(() {
            characterGender = gender;
            selectedCharacterKey = '${characterGender}_01';
          }),
          onSelected: (key) => setState(() => selectedCharacterKey = key),
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


/// 동화 본문 낱말 하나: 누르면 뜻풀이 팝업.
/// 마우스를 올리면(웹·PC) 밑줄이 진해지고 은은한 배경 + 손가락 커서. 터치 화면은 늘 연한 밑줄로 누를 수 있다는 걸 보여 줌
class _StoryWord extends StatefulWidget {
  final String word;
  final VoidCallback onTap;

  const _StoryWord({required this.word, required this.onTap});

  @override
  State<_StoryWord> createState() => _StoryWordState();
}

class _StoryWordState extends State<_StoryWord> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 120),
          padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
          decoration: BoxDecoration(
            color: _hover ? const Color(0x268B5CF6) : Colors.transparent,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            widget.word,
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              height: 1.5,
              decoration: TextDecoration.underline,
              decorationColor: _hover ? const Color(0xFFC4B5FD) : const Color(0x668B5CF6),
              decorationThickness: _hover ? 2.2 : 1.0,
            ),
          ),
        ),
      ),
    );
  }
}
