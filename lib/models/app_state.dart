import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';

import '../services/api_service.dart';
import '../services/db_service.dart';
import 'character_profile.dart';
import 'story_model.dart';

class AppState extends ChangeNotifier {
  static const List<List<String>> _temporaryChoicePools = [
    ['반짝이는 빛을 따라 깊은 숲으로 간다', '숲속 친구들에게 함께 가자고 말한다', '별조각을 손수건에 감싸 단서를 살핀다'],
    ['작은 문에 새겨진 문양을 읽어 본다', '요정에게 길을 물어본다', '용기를 내어 문을 열고 들어간다'],
    ['잃어버린 별씨앗을 모두와 나누어 심는다', '가장 어두운 길에 먼저 등불을 건다', '마음속 소원을 조용히 말해 본다'],
    ['바람의 종소리를 따라간다', '구름다리 위에서 주변을 관찰한다', '다친 별나비를 돌봐 준다'],
    ['비밀 지도를 펼쳐 다음 표식을 찾는다', '친구와 역할을 나누어 움직인다', '처음 본 그림자에게 인사를 건넨다'],
  ];

  StorySession? currentStory;
  bool isLoading = false;
  String? errorMessage;

  String? currentUserId;
  String? currentAccountId;
  String? currentNickname;
  String? currentProvider;
  String? currentEmail;
  String? currentPhone;
  String? currentAddress;

  List<StorySession> completedStories = [];
  List<VocabWord> savedVocabulary = [];
  bool isUserDataLoading = false;
  String? userDataErrorMessage;

  PsychResult? psychResult;
  bool isPsychLoading = false;
  String? psychAnalysisNotice;
  String? _psychResultStoryIdentity;
  final Map<StorySession, Future<void>> _storySyncQueue = {};
  List<VocabWord>? _allVocabularyCache;

  bool get hasSignedInUser =>
      (currentAccountId != null && currentAccountId!.isNotEmpty) ||
      (currentUserId != null && currentUserId!.isNotEmpty);

  StorySession? get activePsychStory {
    if (currentStory != null && currentStory!.chapters.isNotEmpty) {
      return currentStory;
    }
    if (completedStories.isNotEmpty) return completedStories.first;
    return null;
  }

  bool canAnalyzeStory(StorySession story) =>
      story.hasReachedEnding && !isLoading;

  PsychResult? psychResultFor(StorySession story) {
    if (_psychResultStoryIdentity != _storyIdentity(story)) return null;
    return psychResult;
  }

  String get currentDisplayName {
    final nickname = currentNickname?.trim();
    if (nickname != null && nickname.isNotEmpty) return nickname;
    final accountId = currentAccountId?.trim();
    if (accountId != null && accountId.isNotEmpty) {
      return accountId.split('@').first;
    }
    return '동화 탐험가';
  }

  List<VocabWord> get allVocabulary {
    final cached = _allVocabularyCache;
    if (cached != null) return cached;

    final combined = <VocabWord>[];
    final seen = <String>{};

    void collect(List<VocabWord> words) {
      for (final word in words) {
        final key = '${word.hard}|${word.easy}|${word.definition}';
        if (seen.add(key)) {
          combined.add(word);
        }
      }
    }

    if (currentStory != null) {
      collect(currentStory!.vocab);
    }
    for (final story in completedStories) {
      collect(story.vocab);
    }
    collect(savedVocabulary);
    _allVocabularyCache = combined;
    return combined;
  }

  void _invalidateVocabularyCache() => _allVocabularyCache = null;

  void setSignedInUser({
    String? userId,
    required String accountId,
    required String nickname,
    required String provider,
    String? email,
    String? phone,
    String? address,
  }) {
    currentUserId = userId;
    currentAccountId = accountId;
    currentNickname = nickname;
    currentProvider = provider;
    currentEmail = email;
    currentPhone = phone;
    currentAddress = address;
    _invalidateVocabularyCache();
    notifyListeners();
    unawaited(loadUserData());
  }

  void clearSignedInUser() {
    DbService.clearAccessToken();
    currentUserId = null;
    currentAccountId = null;
    currentNickname = null;
    currentProvider = null;
    currentEmail = null;
    currentPhone = null;
    currentAddress = null;
    currentStory = null;
    completedStories = [];
    savedVocabulary = [];
    _invalidateVocabularyCache();
    _clearPsychResult();
    userDataErrorMessage = null;
    notifyListeners();
  }

  void updateSignedInProfile({
    String? nickname,
    String? email,
    String? phone,
    String? address,
  }) {
    if (nickname != null) currentNickname = nickname;
    if (email != null) currentEmail = email;
    if (phone != null) currentPhone = phone;
    if (address != null) currentAddress = address;
    notifyListeners();
  }

  void _setLoading(bool v) {
    isLoading = v;
    notifyListeners();
  }

  void clearError() {
    errorMessage = null;
    userDataErrorMessage = null;
    notifyListeners();
  }

  Future<void> loadUserData() async {
    final userId = currentUserId;
    if (userId == null || userId.isEmpty) return;

    isUserDataLoading = true;
    userDataErrorMessage = null;
    notifyListeners();

    try {
      final userData = await Future.wait<Object>([
        DbService.fetchUserStories(userId),
        DbService.fetchUserVocabularies(userId),
      ]);
      final stories = userData[0] as List<StorySession>;
      final vocabularies = userData[1] as List<VocabWord>;
      if (currentUserId != userId) return;

      _replaceCompletedStoriesFromDb(stories);
      savedVocabulary = vocabularies;
      _invalidateVocabularyCache();
      if (currentStory == null && completedStories.isNotEmpty) {
        psychResult ??= _buildPsychResultFromStory(completedStories.first);
      }
    } catch (e) {
      userDataErrorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      if (currentUserId == userId) {
        isUserDataLoading = false;
        notifyListeners();
      }
    }
  }

  Future<bool> startStory({
    required String genre,
    required String age,
    required String prompt,
    String? selectedHeroCharacterKey,
  }) async {
    _setLoading(true);
    errorMessage = null;
    try {
      final selectedCharacterKey = selectedHeroCharacterKey?.trim();
      final data = await ApiService.startStory(
        genre: genre,
        age: age,
        prompt: prompt,
        characterContext: _characterContext(selectedCharacterKey),
      );

      final vocab = (data['vocab'] as List? ?? [])
          .map((e) => VocabWord.fromJson(e as Map<String, dynamic>))
          .toList();

      final firstChapter = StoryChapter(
        chapter: 1,
        text: data['story_text']?.toString() ?? '',
        imageBytes: _decodeImage(data['image_b64']),
        sceneContract: data['scene_contract'] is Map
            ? Map<String, dynamic>.from(data['scene_contract'] as Map)
            : null,
        storyEmotion: _parseEmotionAnalysis(data['story_emotion']),
      );

      final storyCharacters = _parseStoryCharacters(data);
      final storyCast = _parseStoryCast(data);
      final characterOverrides = _parseCharacterOverrides(data);
      if (selectedCharacterKey != null && selectedCharacterKey.isNotEmpty) {
        characterOverrides['hero'] = selectedCharacterKey;
      }
      if (selectedCharacterKey != null &&
          selectedCharacterKey.isNotEmpty &&
          !storyCharacters.containsKey('hero')) {
        storyCharacters['hero'] = 'The selected story protagonist';
      }

      currentStory = StorySession(
        storyId: data['story_id']?.toString() ?? 'story_0',
        runtimeState: data['runtime_state']?.toString(),
        genre: genre,
        age: age,
        initialPrompt: prompt,
        chapters: [firstChapter],
        choices: List<String>.from(data['choices'] ?? []),
        choiceOptions: _buildChoiceOptions(
          data['choices'] as List?,
          data['choice_emotions'] as List?,
        ),
        candidateVocab: vocab,
        vocab: [],
        characters: storyCharacters,
        characterOverrides: characterOverrides,
        storyCast: storyCast,
        allChoicesMade: [],
        currentChapter: 1,
        readProgress: 1,
      );
      _invalidateVocabularyCache();
      psychResult = _buildPsychResultFromStory(currentStory!);

      notifyListeners();
      final storyToSync = currentStory!;
      _queueStorySync(storyToSync, () => _syncStoryStart(storyToSync));
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  Future<bool> continueStory(String choice) async {
    if (currentStory == null) return false;
    if (_isTemporaryStory(currentStory!)) {
      return _continueTemporaryStory(choice);
    }
    _setLoading(true);
    errorMessage = null;
    try {
      final session = currentStory!;
      final data = await ApiService.continueStory(
        storyId: session.storyId,
        storySoFar: session.fullStoryText,
        choice: choice,
        genre: session.genre,
        age: session.age,
        characterContext: _characterContext(session.selectedHeroCharacterKey),
        storyCast: _storyCastJson(session),
        characterOverrides: session.characterOverrides,
        previousSceneContract: session.chapters.isEmpty
            ? null
            : session.chapters.last.sceneContract,
        runtimeState: session.runtimeState,
      );

      final newText = data['new_text']?.toString() ?? '';
      final newChapter = session.currentChapter + 1;

      final vocab = (data['vocab'] as List? ?? [])
          .map((e) => VocabWord.fromJson(e as Map<String, dynamic>))
          .toList();

      final chapter = StoryChapter(
        chapter: newChapter,
        text: newText,
        choiceMade: choice,
        imageBytes: _decodeImage(data['image_b64']),
        sceneContract: data['scene_contract'] is Map
            ? Map<String, dynamic>.from(data['scene_contract'] as Map)
            : null,
        selectedChoiceEmotion: _parseEmotionAnalysis(
          data['selected_choice_emotion'],
        ),
        storyEmotion: _parseEmotionAnalysis(data['story_emotion']),
      );

      session.chapters.add(chapter);
      session.choices = List<String>.from(data['choices'] ?? []);
      session.choiceOptions = _buildChoiceOptions(
        data['choices'] as List?,
        data['choice_emotions'] as List?,
      );
      session.candidateVocab = _mergeTemporaryVocab(
        session.candidateVocab,
        vocab,
      );
      session.allChoicesMade = [...session.allChoicesMade, choice];
      session.currentChapter = newChapter;
      session.readProgress = newChapter;
      session.runtimeState =
          data['runtime_state']?.toString() ?? session.runtimeState;
      psychResult = _buildPsychResultFromStory(session);

      notifyListeners();
      _queueStorySync(session, () => _syncChapter(session, chapter));
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  Future<void> loadPsychAnalysis() async {
    final story = activePsychStory;
    if (story == null) return;
    if (!canAnalyzeStory(story)) {
      psychAnalysisNotice = '모든 선택을 마치고 엔딩을 본 뒤 분석할 수 있어요.';
      notifyListeners();
      return;
    }
    isPsychLoading = true;
    psychAnalysisNotice = null;
    psychResult = null;
    _psychResultStoryIdentity = null;
    notifyListeners();
    try {
      final data = await ApiService.analyzePsychology(
        storyId: story.storyId,
        storyTitle: story.initialPrompt,
        choicesMade: story.allChoicesMade,
        completed: true,
        runtimeState: story.runtimeState,
      );
      psychResult = PsychResult.fromJson(data);
      _psychResultStoryIdentity = _storyIdentity(story);
    } catch (e) {
      psychResult = _buildPsychResultFromStory(story);
      _psychResultStoryIdentity = _storyIdentity(story);
      final detail = e
          .toString()
          .replaceFirst('Exception: ', '')
          .replaceAll(RegExp(r'\s+'), ' ')
          .trim();
      final shortDetail = detail.length > 120
          ? '${detail.substring(0, 120)}...'
          : detail;
      psychAnalysisNotice =
          'AI 해설 응답을 받지 못해 고른 선택 기록만 보여드려요.\n원인: $shortDetail';
      errorMessage = null;
    } finally {
      isPsychLoading = false;
      notifyListeners();
    }
  }

  void finishCurrentStory() {
    if (currentStory != null) {
      final story = currentStory!;
      completedStories.removeWhere(
        (item) => _storyIdentity(item) == _storyIdentity(story),
      );
      completedStories.insert(0, story);
      _clearPsychResult();
    }
    currentStory = null;
    _invalidateVocabularyCache();
    notifyListeners();
  }

  void resetCurrentStory() {
    currentStory = null;
    _invalidateVocabularyCache();
    _clearPsychResult();
    errorMessage = null;
    notifyListeners();
  }

  Future<bool> deleteCompletedStory(StorySession story) async {
    final previousStories = List<StorySession>.from(completedStories);
    completedStories.removeWhere(
      (item) => _storyIdentity(item) == _storyIdentity(story),
    );
    _invalidateVocabularyCache();
    notifyListeners();

    try {
      final dbStoryId = story.dbStoryId;
      if (dbStoryId != null && dbStoryId.isNotEmpty) {
        await DbService.deleteStory(storyId: dbStoryId, userId: currentUserId);
        savedVocabulary.removeWhere((word) => word.originStoryId == dbStoryId);
        _invalidateVocabularyCache();
      }
      notifyListeners();
      return true;
    } catch (e) {
      completedStories = previousStories;
      _invalidateVocabularyCache();
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> renameCompletedStory(StorySession story, String title) async {
    final trimmedTitle = title.trim();
    if (trimmedTitle.isEmpty) {
      errorMessage = '제목은 비워둘 수 없어요.';
      notifyListeners();
      return false;
    }

    try {
      final dbStoryId = story.dbStoryId;
      if (dbStoryId != null && dbStoryId.isNotEmpty) {
        final updated = await DbService.updateStoryTitle(
          storyId: dbStoryId,
          title: trimmedTitle,
          userId: currentUserId,
        );
        _applyStoryMetadata(story, updated);
      } else {
        story.initialPrompt = trimmedTitle;
      }
      _invalidateVocabularyCache();
      notifyListeners();
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> deleteVocabulary(VocabWord vocab) async {
    bool matches(VocabWord item) =>
        _vocabIdentity(item) == _vocabIdentity(vocab);

    try {
      final vocabId = vocab.id;
      if (vocabId != null && vocabId.isNotEmpty) {
        await DbService.deleteVocabulary(
          vocabId: vocabId,
          userId: currentUserId,
        );
      }
      savedVocabulary.removeWhere(matches);
      currentStory?.vocab.removeWhere(matches);
      for (final story in completedStories) {
        story.vocab.removeWhere(matches);
      }
      _invalidateVocabularyCache();
      notifyListeners();
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> saveVocabularyFromStory(
    StorySession session,
    VocabWord vocab,
  ) async {
    bool matches(VocabWord item) => _sameVocabContent(item, vocab);

    if (session.vocab.any(matches)) return true;

    final localWord = vocab.copyWith(
      originStoryId: session.dbStoryId,
      sourceStoryTitle: session.initialPrompt,
    );
    session.vocab.add(localWord);
    if (!savedVocabulary.any(matches)) {
      savedVocabulary.insert(0, localWord);
    }
    _invalidateVocabularyCache();
    notifyListeners();

    final userId = currentUserId;
    if (userId == null || userId.isEmpty) return true;

    try {
      if (session.dbStoryId == null) {
        await _syncStoryStart(session);
      }
      final dbStoryId = session.dbStoryId;
      if (dbStoryId == null || dbStoryId.isEmpty) return true;

      final savedId = await DbService.addVocabulary(
        userId: userId,
        storyId: dbStoryId,
        word: localWord,
        sourceStoryTitle: session.initialPrompt,
      );
      if (savedId != null && savedId.isNotEmpty) {
        _attachVocabId(session, localWord, savedId);
        _attachSavedVocabularyId(localWord, savedId, dbStoryId);
        _invalidateVocabularyCache();
        session.syncedVocabKeys.add(
          '${localWord.hard}|${localWord.easy}|${localWord.definition}',
        );
        notifyListeners();
      }
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    }
  }

  Future<bool> startTemporaryStory({
    required String genre,
    required String age,
    required String prompt,
    String? selectedHeroCharacterKey,
  }) async {
    _setLoading(true);
    errorMessage = null;
    try {
      final normalizedPrompt = prompt.trim().isEmpty
          ? '반짝이는 숲속 모험'
          : prompt.trim();
      final selectedCharacterKey = selectedHeroCharacterKey?.trim() ?? '';
      final chapterVocab = _temporaryVocabForChapter(
        genre: genre,
        prompt: normalizedPrompt,
        chapter: 1,
      );
      final firstChapter = StoryChapter(
        chapter: 1,
        text: _buildTemporaryOpening(
          genre: genre,
          age: age,
          prompt: normalizedPrompt,
        ),
        imageUrl: _temporaryImageMarker(genre, 1),
        storyEmotion: _temporaryStoryEmotion(genre: genre, chapter: 1),
      );
      final firstChoices = _temporaryChoicesForChapter(
        1,
        genre: genre,
        prompt: normalizedPrompt,
      );

      currentStory = StorySession(
        storyId: 'mock_${DateTime.now().millisecondsSinceEpoch}',
        genre: genre,
        age: age,
        initialPrompt: normalizedPrompt,
        chapters: [firstChapter],
        choices: firstChoices,
        choiceOptions: firstChoices
            .map(
              (choice) => ChoiceOption(
                text: choice,
                emotion: _temporaryChoiceEmotion(choice, 1),
              ),
            )
            .toList(),
        candidateVocab: chapterVocab,
        vocab: [],
        characters: selectedCharacterKey.isEmpty
            ? const {}
            : const {'hero': 'The selected story protagonist'},
        characterOverrides: selectedCharacterKey.isEmpty
            ? const {}
            : {'hero': selectedCharacterKey},
        allChoicesMade: [],
        currentChapter: 1,
      );
      _invalidateVocabularyCache();
      psychResult = _buildPsychResultFromStory(currentStory!);
      notifyListeners();
      return true;
    } catch (e) {
      errorMessage = '임시 동화를 만들지 못했어요: $e';
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  EmotionAnalysis? _parseEmotionAnalysis(dynamic raw) {
    if (raw is Map<String, dynamic>) {
      return EmotionAnalysis.fromJson(raw);
    }
    return null;
  }

  Uint8List? _decodeImage(dynamic raw) {
    final encoded = raw?.toString().trim();
    if (encoded == null || encoded.isEmpty) return null;
    try {
      return base64Decode(encoded);
    } catch (_) {
      return null;
    }
  }

  void _clearPsychResult() {
    psychResult = null;
    psychAnalysisNotice = null;
    _psychResultStoryIdentity = null;
  }

  Map<String, String> _parseStoryCharacters(Map<String, dynamic> data) {
    dynamic raw = data['characters'] ?? data['story_characters'];
    final storyPlan = data['story_plan'];
    if (raw == null && storyPlan is Map) {
      raw = storyPlan['characters'];
    }
    if (raw is Map) {
      return raw.map(
        (key, value) => MapEntry(key.toString(), value.toString()),
      );
    }

    for (final value in data.values.whereType<String>()) {
      final match = RegExp(
        r'\[(?:등장인물|CHARACTERS)\]\s*(\{.*?\})',
        dotAll: true,
      ).firstMatch(value);
      if (match == null) continue;
      try {
        final decoded = jsonDecode(match.group(1)!);
        if (decoded is Map) {
          return decoded.map(
            (key, value) => MapEntry(key.toString(), value.toString()),
          );
        }
      } catch (_) {}
    }
    return const {};
  }

  Map<String, String> _parseCharacterOverrides(Map<String, dynamic> data) {
    final raw = data['character_overrides'];
    if (raw is! Map) return <String, String>{};
    return raw.map(
      (key, value) => MapEntry(key.toString(), value.toString()),
    );
  }

  List<StoryCastMember> _parseStoryCast(Map<String, dynamic> data) {
    final raw = data['story_cast'] ?? data['storyCast'];
    if (raw is! List) return <StoryCastMember>[];
    return raw
        .whereType<Map>()
        .map(
          (item) => StoryCastMember.fromJson(
            item.map((key, value) => MapEntry(key.toString(), value)),
          ),
        )
        .where((member) => member.role.isNotEmpty)
        .toList();
  }

  List<Map<String, dynamic>> _storyCastJson(StorySession session) {
    return session.effectiveStoryCast
        .map(
          (member) => <String, dynamic>{
            'role': member.role,
            'name': member.name,
            if (member.characterKey.trim().isNotEmpty)
              'character_key': member.characterKey,
            if (member.profileName != null) 'profile_name': member.profileName,
            if (member.sourceDescription != null)
              'source_description': member.sourceDescription,
          },
        )
        .toList(growable: false);
  }

  List<ChoiceOption> _buildChoiceOptions(List? rawChoices, List? rawEmotions) {
    final choices = List<String>.from(rawChoices ?? []);
    final emotions = rawEmotions ?? const [];
    return List.generate(choices.length, (index) {
      final emotion = index < emotions.length
          ? _parseEmotionAnalysis(emotions[index])
          : null;
      return ChoiceOption(text: choices[index], emotion: emotion);
    });
  }

  void _queueStorySync(StorySession session, Future<void> Function() task) {
    final previous = _storySyncQueue[session] ?? Future<void>.value();
    final queued = previous.then<void>((_) async {
      try {
        await task();
      } catch (_) {
        // Local story progress remains available when a background DB sync fails.
      }
    });
    _storySyncQueue[session] = queued;
    unawaited(
      queued.whenComplete(() {
        if (identical(_storySyncQueue[session], queued)) {
          _storySyncQueue.remove(session);
        }
      }),
    );
  }

  Future<void> _syncStoryStart(StorySession session) async {
    if (currentUserId == null || currentUserId!.isEmpty) return;
    if (session.dbStoryId == null) {
      final dbStoryId = await DbService.createStorySession(
        userId: currentUserId!,
        title: session.initialPrompt,
        genre: session.genre,
        age: session.age,
        prompt: session.initialPrompt,
        characters: session.characters,
        characterOverrides: session.characterOverrides,
        aiStoryId: session.storyId,
        runtimeState: session.runtimeState,
        pendingChoices: session.choices,
        pendingChoiceEmotions: session.choiceOptions
            .map(
              (option) => option.emotion?.toJson() ?? const <String, dynamic>{},
            )
            .toList(),
        readProgress: session.readProgress,
      );

      if (dbStoryId == null) return;
      session.dbStoryId = dbStoryId;
    }

    var changed = false;
    for (final chapter in session.chapters) {
      final synced = await _syncSceneIfNeeded(session, chapter);
      changed = synced || changed;
      unawaited(_generateMediaForChapter(session, chapter));
    }
    await _syncReadingState(session);

    if (changed) {
      notifyListeners();
    }
  }

  Future<void> _syncChapter(StorySession session, StoryChapter chapter) async {
    if (_isTemporaryStory(session) && session.dbStoryId == null) return;
    if (currentUserId == null || currentUserId!.isEmpty) return;

    if (session.dbStoryId == null) {
      await _syncStoryStart(session);
      return;
    }
    if (session.dbStoryId == null) return;

    final changed = await _syncSceneIfNeeded(session, chapter);
    if (changed) {
      notifyListeners();
    }
    await _syncReadingState(session);
    unawaited(_generateMediaForChapter(session, chapter));
  }

  Future<void> _syncReadingState(StorySession session) async {
    final dbStoryId = session.dbStoryId;
    if (dbStoryId == null || dbStoryId.isEmpty) return;
    await DbService.saveStoryReadingState(
      storyId: dbStoryId,
      aiStoryId: session.storyId,
      runtimeState: session.runtimeState,
      pendingChoices: session.choices,
      pendingChoiceEmotions: session.choiceOptions
          .map(
            (option) => option.emotion?.toJson() ?? const <String, dynamic>{},
          )
          .toList(),
      readProgress: session.readProgress,
      completed: session.hasReachedEnding,
    );
  }

  void resumeStory(StorySession story) {
    currentStory = story;
    story.readProgress = story.currentChapter;
    completedStories = completedStories
        .where((item) => _storyIdentity(item) != _storyIdentity(story))
        .toList();
    _invalidateVocabularyCache();
    psychResult = _buildPsychResultFromStory(story);
    notifyListeners();
    _queueStorySync(story, () => _syncReadingState(story));
  }

  Future<bool> _syncSceneIfNeeded(
    StorySession session,
    StoryChapter chapter,
  ) async {
    final dbStoryId = session.dbStoryId;
    if (dbStoryId == null || dbStoryId.isEmpty) return false;
    if (session.syncedChapterNumbers.contains(chapter.chapter)) return false;

    final pushed = await DbService.pushScene(
      storyId: dbStoryId,
      stepNumber: chapter.chapter,
      storyText: chapter.text,
      choiceMade: chapter.choiceMade,
      sceneContract: chapter.sceneContract,
      selectedChoiceEmotion: chapter.selectedChoiceEmotion?.toJson(),
      storyEmotion: chapter.storyEmotion?.toJson(),
      imageUrl: chapter.imageUrl,
      videoUrl: chapter.videoUrl,
    );
    if (!pushed) return false;

    session.syncedChapterNumbers.add(chapter.chapter);
    return true;
  }

  Future<void> _generateMediaForChapter(
    StorySession session,
    StoryChapter chapter, {
    bool includeVideo = false,
  }) async {
    if (_isTemporaryStory(session)) return;
    if (chapter.text.trim().isEmpty) return;
    if (!includeVideo && chapter.imageBytes != null) return;
    if (!session.syncedChapterNumbers.contains(chapter.chapter)) return;

    final hasImageUrl = chapter.imageUrl?.trim().isNotEmpty ?? false;
    final hasVideoUrl = chapter.videoUrl?.trim().isNotEmpty ?? false;
    if ((!includeVideo && hasImageUrl) || (includeVideo && hasVideoUrl)) return;

    if (session.mediaGenerationChapterNumbers.contains(chapter.chapter)) {
      return;
    }

    final dbStoryId = session.dbStoryId;
    if (dbStoryId == null || dbStoryId.isEmpty) return;

    session.mediaGenerationChapterNumbers.add(chapter.chapter);
    chapter.mediaStatus = 'running';
    chapter.mediaError = null;
    notifyListeners();
    try {
      final media = await DbService.generateSceneMedia(
        storyId: dbStoryId,
        stepNumber: chapter.chapter,
        storyText: chapter.text,
        genre: session.genre,
        age: session.age,
        characterKey: session.selectedHeroCharacterKey,
        sceneContract: chapter.sceneContract,
        includeVideo: includeVideo,
      );

      if (media == null) {
        chapter.mediaStatus = 'failed';
        chapter.mediaError = includeVideo
            ? '영상 생성 결과를 가져오지 못했습니다.'
            : '삽화 생성 결과를 가져오지 못했습니다.';
        return;
      }

      chapter.mediaJobId = media.jobId;
      chapter.mediaStatus = media.status;
      chapter.mediaError = media.error;

      if (media.imageUrl?.trim().isNotEmpty ?? false) {
        chapter.imageUrl = media.imageUrl;
      }
      if (media.videoUrl?.trim().isNotEmpty ?? false) {
        chapter.videoUrl = media.videoUrl;
      }

      final requestedVideoMissing =
          includeVideo && !(media.videoUrl?.trim().isNotEmpty ?? false);
      if (media.isPartial ||
          media.status == 'failed' ||
          requestedVideoMissing) {
        chapter.mediaStatus = media.isPartial || requestedVideoMissing
            ? 'partial'
            : 'failed';
        chapter.mediaError ??= requestedVideoMissing
            ? '삽화는 준비됐지만 영상 생성에 실패했습니다.'
            : includeVideo
            ? '영상 생성에 실패했습니다.'
            : '삽화 생성에 실패했습니다.';
      } else if (!media.hasMedia) {
        chapter.mediaStatus = 'failed';
        chapter.mediaError ??= includeVideo ? '생성된 영상이 없습니다.' : '생성된 삽화가 없습니다.';
      }
    } catch (error) {
      chapter.mediaStatus = 'failed';
      chapter.mediaError = includeVideo
          ? '영상 생성 중 오류가 발생했습니다: $error'
          : '삽화 생성 중 오류가 발생했습니다: $error';
    } finally {
      session.mediaGenerationChapterNumbers.remove(chapter.chapter);
      notifyListeners();
    }
  }

  Future<void> retryMediaForChapter(
    StorySession session,
    StoryChapter chapter,
  ) async {
    session.mediaGenerationChapterNumbers.remove(chapter.chapter);
    chapter.mediaStatus = null;
    chapter.mediaError = null;
    notifyListeners();
    await _generateMediaForChapter(session, chapter);
  }

  /// Videos are optional: illustrations are generated with each chapter, while
  /// this explicit action starts the slower and more expensive video render.
  Future<void> generateVideoForChapter(
    StorySession session,
    StoryChapter chapter,
  ) async {
    if (session.mediaGenerationChapterNumbers.contains(chapter.chapter) ||
        (chapter.videoUrl?.trim().isNotEmpty ?? false)) {
      return;
    }

    if (_isTemporaryStory(session)) {
      chapter.videoUrl = _temporaryVideoMarker(session.genre, chapter.chapter);
      chapter.mediaStatus = 'completed';
      chapter.mediaError = null;
      notifyListeners();
      return;
    }

    await _generateMediaForChapter(session, chapter, includeVideo: true);
  }

  bool _isTemporaryStory(StorySession session) {
    return session.storyId.startsWith('mock_');
  }

  Map<String, dynamic>? _characterContext(String? characterKey) {
    final normalizedKey = characterKey?.trim() ?? '';
    if (normalizedKey.isEmpty) return null;
    final profile = CharacterProfileCatalog.findByKey(normalizedKey);
    return {
      'character_key': normalizedKey,
      if (profile != null) 'name': profile.displayName,
      if (profile != null) 'description': profile.description,
      if (profile != null) 'gender': profile.gender,
      if (profile != null) 'age_group': profile.ageGroup,
      'identity_locked': true,
    };
  }

  String _storyIdentity(StorySession session) {
    final dbId = session.dbStoryId;
    if (dbId != null && dbId.isNotEmpty) return 'db:$dbId';
    return 'local:${session.storyId}';
  }

  String _vocabIdentity(VocabWord vocab) {
    final id = vocab.id;
    if (id != null && id.isNotEmpty) return 'db:$id';
    return 'local:${vocab.hard}|${vocab.easy}|${vocab.definition}';
  }

  bool _sameVocabContent(VocabWord a, VocabWord b) {
    return a.hard == b.hard && a.easy == b.easy && a.definition == b.definition;
  }

  void _attachVocabId(StorySession session, VocabWord target, String id) {
    final index = session.vocab.indexWhere(
      (word) => _sameVocabContent(word, target),
    );
    if (index < 0) return;
    session.vocab[index] = session.vocab[index].copyWith(
      id: id,
      originStoryId: session.dbStoryId,
      sourceStoryTitle: session.initialPrompt,
    );
  }

  void _attachSavedVocabularyId(
    VocabWord target,
    String id,
    String originStoryId,
  ) {
    final index = savedVocabulary.indexWhere(
      (word) => _sameVocabContent(word, target),
    );
    if (index < 0) return;
    savedVocabulary[index] = savedVocabulary[index].copyWith(
      id: id,
      originStoryId: originStoryId,
    );
  }

  void _applyStoryMetadata(StorySession target, StorySession source) {
    target.storyId = source.storyId;
    target.dbStoryId = source.dbStoryId;
    target.initialPrompt = source.initialPrompt;
    target.genre = source.genre;
    target.age = source.age;
  }

  void _replaceCompletedStoriesFromDb(List<StorySession> dbStories) {
    final currentDbStoryId = currentStory?.dbStoryId;
    final remoteStories = dbStories
        .where((story) => story.dbStoryId != currentDbStoryId)
        .toList();
    final localOnlyStories = completedStories
        .where((story) => story.dbStoryId == null || _isTemporaryStory(story))
        .toList();

    final merged = <StorySession>[];
    final seen = <String>{};
    for (final story in [...remoteStories, ...localOnlyStories]) {
      if (seen.add(_storyIdentity(story))) {
        merged.add(story);
      }
    }
    completedStories = merged;
    _invalidateVocabularyCache();
  }

  List<String> _temporaryChoicesForChapter(
    int chapter, {
    required String genre,
    required String prompt,
  }) {
    if (chapter >= 4) return const [];
    final seed = _temporarySeed('$genre|$prompt|$chapter');
    final pool = [
      ..._temporaryChoicePools[(chapter - 1) % _temporaryChoicePools.length],
      ..._genreChoices(genre),
      ..._promptChoices(prompt),
    ];
    final start = seed % pool.length;
    final choices = <String>[];
    for (
      var offset = 0;
      choices.length < 3 && offset < pool.length * 2;
      offset++
    ) {
      final choice = pool[(start + offset) % pool.length];
      if (!choices.contains(choice)) choices.add(choice);
    }
    return choices;
  }

  List<String> _genreChoices(String genre) {
    switch (genre) {
      case '판타지':
        return const ['달빛 마법 주문을 작게 외워 본다', '별가루가 흘러가는 방향을 따라간다'];
      case '모험':
        return const ['낡은 나침반이 가리키는 길로 간다', '폭포 뒤 숨은 통로를 찾아본다'];
      case '우정':
        return const ['친구의 손을 꼭 잡고 함께 결정한다', '서로의 생각을 한 가지씩 말해 본다'];
      case '자연':
        return const ['나뭇잎의 흔들림을 관찰한다', '시냇물 소리가 커지는 곳으로 간다'];
      case '동물':
        return const ['작은 발자국을 조심히 따라간다', '동물 친구에게 먹이를 나누어 준다'];
      case '미스터리':
        return const ['수상한 발자국의 간격을 재 본다', '고성 벽에 숨은 글자를 비춰 본다'];
      default:
        return const ['가장 반짝이는 길을 골라 본다', '마음이 따뜻해지는 방향으로 간다'];
    }
  }

  List<String> _promptChoices(String prompt) {
    final keyword = prompt.length > 10 ? prompt.substring(0, 10) : prompt;
    return ['"$keyword"에 숨은 뜻을 떠올려 본다', '"$keyword"을 친구에게 보여 준다'];
  }

  String _genreSetting(String genre) {
    switch (genre) {
      case '판타지':
        return '달빛이 부서지는 마법 숲';
      case '모험':
        return '지도에도 없는 비밀 오솔길';
      case '우정':
        return '웃음소리가 가득한 작은 마을';
      case '자연':
        return '바람과 새들이 속삭이는 초록 숲';
      case '동물':
        return '동물 친구들이 사는 해님 언덕';
      case '미스터리':
        return '별빛이 흐르는 조용한 고성';
      default:
        return '반짝이는 이야기 숲';
    }
  }

  int _temporarySeed(String value) {
    var hash = 0;
    for (final codeUnit in value.codeUnits) {
      hash = (hash * 31 + codeUnit) & 0x7fffffff;
    }
    return hash;
  }

  String _temporaryImageMarker(String genre, int chapter) {
    final theme = switch (genre) {
      '판타지' => 'moon-forest',
      '모험' => 'secret-map',
      '우정' => 'warm-village',
      '자연' => 'green-river',
      '동물' => 'animal-hill',
      '미스터리' => 'star-castle',
      _ => 'storybook',
    };
    return 'mock://image/$theme/$chapter';
  }

  String _temporaryVideoMarker(String genre, int chapter) {
    final theme = switch (genre) {
      '판타지' => 'glowing-spell',
      '모험' => 'running-map',
      '우정' => 'friends-together',
      '자연' => 'wind-and-leaves',
      '동물' => 'animal-parade',
      '미스터리' => 'hidden-door',
      _ => 'storybook-motion',
    };
    return 'mock://video/$theme/$chapter';
  }

  EmotionScoreItem _emotionItem(int index, String label, double score) {
    return EmotionScoreItem(
      labelIndex: index,
      label: label,
      labelDisplay: label,
      score: (score.clamp(0.0, 1.0) as num).toDouble(),
    );
  }

  EmotionAnalysis _emotionAnalysis(List<EmotionScoreItem> items) {
    final sorted = List<EmotionScoreItem>.from(items)
      ..sort((a, b) => b.score.compareTo(a.score));
    final primary = sorted.first;
    return EmotionAnalysis(
      emotionLabelSource: 'temporary_kote',
      emotionLabelsAreGeneric: false,
      primaryEmotionIndex: primary.labelIndex,
      primaryEmotion: primary.label,
      primaryEmotionDisplay: primary.labelDisplay,
      primaryScore: primary.score,
      topEmotions: sorted,
      activeEmotions: sorted.where((item) => item.score >= 0.35).toList(),
      scores: {
        for (final item in sorted)
          item.label: double.parse(item.score.toStringAsFixed(3)),
      },
      scoresByIndex: {
        for (final item in sorted)
          item.labelIndex: double.parse(item.score.toStringAsFixed(3)),
      },
    );
  }

  EmotionAnalysis _temporaryStoryEmotion({
    required String genre,
    required int chapter,
  }) {
    final base = switch (genre) {
      '미스터리' => [
        _emotionItem(15, '신기함/관심', 0.95),
        _emotionItem(39, '놀람', 0.82),
        _emotionItem(8, '기대감', 0.78),
        _emotionItem(41, '불안/걱정', 0.42),
        _emotionItem(2, '감동/감탄', 0.38),
      ],
      '우정' => [
        _emotionItem(16, '아껴주는', 0.94),
        _emotionItem(4, '고마움', 0.88),
        _emotionItem(40, '행복', 0.82),
        _emotionItem(43, '안심/신뢰', 0.68),
        _emotionItem(42, '기쁨', 0.63),
      ],
      '모험' => [
        _emotionItem(8, '기대감', 0.96),
        _emotionItem(28, '즐거움/신남', 0.86),
        _emotionItem(15, '신기함/관심', 0.74),
        _emotionItem(2, '감동/감탄', 0.55),
        _emotionItem(39, '놀람', 0.42),
      ],
      _ => [
        _emotionItem(2, '감동/감탄', 0.94),
        _emotionItem(42, '기쁨', 0.88),
        _emotionItem(40, '행복', 0.84),
        _emotionItem(8, '기대감', 0.78),
        _emotionItem(15, '신기함/관심', 0.62),
      ],
    };

    final adjusted = base
        .map(
          (item) => _emotionItem(
            item.labelIndex,
            item.label,
            min(1.0, item.score + chapter * 0.015),
          ),
        )
        .toList();
    return _emotionAnalysis(adjusted);
  }

  EmotionAnalysis _temporaryChoiceEmotion(String choice, int chapter) {
    if (RegExp('친구|함께|도움|나누어|돌봐').hasMatch(choice)) {
      return _emotionAnalysis([
        _emotionItem(16, '아껴주는', 0.92),
        _emotionItem(4, '고마움', 0.84),
        _emotionItem(43, '안심/신뢰', 0.76),
        _emotionItem(40, '행복', 0.66 + chapter * 0.03),
        _emotionItem(2, '감동/감탄', 0.58),
      ]);
    }
    if (RegExp('용기|먼저|열고|깊은|폭포').hasMatch(choice)) {
      return _emotionAnalysis([
        _emotionItem(8, '기대감', 0.94),
        _emotionItem(28, '즐거움/신남', 0.82),
        _emotionItem(39, '놀람', 0.62),
        _emotionItem(42, '기쁨', 0.57 + chapter * 0.04),
        _emotionItem(13, '뿌듯함', 0.48),
      ]);
    }
    if (RegExp('살핀|읽어|관찰|단서|표식|글자').hasMatch(choice)) {
      return _emotionAnalysis([
        _emotionItem(15, '신기함/관심', 0.95),
        _emotionItem(29, '깨달음', 0.74),
        _emotionItem(8, '기대감', 0.69),
        _emotionItem(39, '놀람', 0.56),
        _emotionItem(43, '안심/신뢰', 0.39),
      ]);
    }
    return _emotionAnalysis([
      _emotionItem(8, '기대감', 0.86),
      _emotionItem(2, '감동/감탄', 0.75),
      _emotionItem(42, '기쁨', 0.64),
      _emotionItem(15, '신기함/관심', 0.54),
      _emotionItem(40, '행복', 0.48),
    ]);
  }

  List<VocabWord> _temporaryVocabForChapter({
    required String genre,
    required String prompt,
    required int chapter,
    String? choice,
  }) {
    final common = <VocabWord>[
      VocabWord(
        hard: '호기심',
        easy: '궁금한 마음',
        definition: '새로운 것을 알고 싶어 하는 마음이에요.',
        sourceStoryTitle: prompt,
      ),
      VocabWord(
        hard: '소원',
        easy: '바라는 일',
        definition: '마음속으로 꼭 이루어지면 좋겠다고 바라는 일이에요.',
        sourceStoryTitle: prompt,
      ),
      VocabWord(
        hard: '단서',
        easy: '힌트',
        definition: '문제를 풀거나 비밀을 알아내는 데 도움이 되는 작은 실마리예요.',
        sourceStoryTitle: prompt,
      ),
    ];

    final byGenre = switch (genre) {
      '판타지' => [
        VocabWord(
          hard: '주문',
          easy: '마법 말',
          definition: '마법을 부릴 때 외우는 특별한 말이에요.',
          sourceStoryTitle: prompt,
        ),
        VocabWord(
          hard: '별가루',
          easy: '반짝 가루',
          definition: '별빛처럼 반짝이는 상상 속의 가루예요.',
          sourceStoryTitle: prompt,
        ),
      ],
      '미스터리' => [
        VocabWord(
          hard: '수상한',
          easy: '이상한',
          definition: '평소와 달라서 궁금하거나 의심이 드는 모습이에요.',
          sourceStoryTitle: prompt,
        ),
        VocabWord(
          hard: '비밀',
          easy: '숨긴 이야기',
          definition: '아직 다른 사람에게 알려지지 않은 일이에요.',
          sourceStoryTitle: prompt,
        ),
      ],
      '자연' => [
        VocabWord(
          hard: '시냇물',
          easy: '작은 물길',
          definition: '졸졸 흐르는 작은 물줄기를 말해요.',
          sourceStoryTitle: prompt,
        ),
        VocabWord(
          hard: '관찰하다',
          easy: '자세히 보다',
          definition: '무엇이 어떻게 움직이는지 찬찬히 살펴보는 거예요.',
          sourceStoryTitle: prompt,
        ),
      ],
      _ => [
        VocabWord(
          hard: '용기',
          easy: '씩씩한 마음',
          definition: '무섭거나 어려워도 해 보려는 마음이에요.',
          sourceStoryTitle: prompt,
        ),
        VocabWord(
          hard: '다정한',
          easy: '친절한',
          definition: '상대방을 따뜻하게 대해 주는 모습이에요.',
          sourceStoryTitle: prompt,
        ),
      ],
    };

    final byChapter = [
      VocabWord(
        hard: chapter == 1
            ? '모험'
            : chapter == 2
            ? '문양'
            : '약속',
        easy: chapter == 1
            ? '새로운 일을 겪는 것'
            : chapter == 2
            ? '그림 무늬'
            : '꼭 하기로 한 말',
        definition: chapter == 1
            ? '낯선 곳에서 새롭고 신나는 일을 겪는 거예요.'
            : chapter == 2
            ? '물건이나 문에 새겨진 특별한 모양이에요.'
            : '서로 믿고 꼭 지키기로 한 말이에요.',
        sourceStoryTitle: prompt,
      ),
    ];

    final result = [...common, ...byGenre, ...byChapter];
    if (choice != null && RegExp('친구|함께|도움').hasMatch(choice)) {
      result.add(
        VocabWord(
          hard: '협동',
          easy: '함께하기',
          definition: '여럿이 힘을 합쳐 같은 목표를 이루는 거예요.',
          sourceStoryTitle: prompt,
        ),
      );
    }
    return result;
  }

  List<VocabWord> _mergeTemporaryVocab(
    List<VocabWord> current,
    List<VocabWord> incoming,
  ) {
    final seen = current
        .map((word) => '${word.hard}|${word.easy}|${word.definition}')
        .toSet();
    return [
      ...current,
      ...incoming.where(
        (word) => seen.add('${word.hard}|${word.easy}|${word.definition}'),
      ),
    ];
  }

  String _buildTemporaryOpening({
    required String genre,
    required String age,
    required String prompt,
  }) {
    final setting = _genreSetting(genre);
    final seed = _temporarySeed('$genre|$age|$prompt');
    final companion = [
      '작은 별나비',
      '노란 목도리를 한 여우',
      '말하는 조약돌',
      '구름 모자를 쓴 요정',
    ][seed % 4];
    final mystery = [
      '은빛 열쇠',
      '접히지 않는 지도',
      '노래하는 씨앗',
      '무지개빛 발자국',
    ][(seed ~/ 3) % 4];
    return '$setting에서 작은 모험이 시작되었어요. 오늘의 주인공은 "$prompt"라는 꿈을 품고 조심조심 길을 나섰답니다.\n\n'
        '그때 $companion가 나타나 "$mystery를 찾으면 마음속 소원이 한 뼘 자랄 거야" 하고 속삭였어요. 길가에는 반짝이는 돌멩이와 흔들리는 그림자가 있었고, 멀리서는 누군가 도움을 기다리는 듯한 따뜻한 빛이 깜빡였지요.\n\n'
        '주인공은 심장이 두근거렸지만, 오늘만큼은 겁보다 호기심이 조금 더 컸답니다.';
  }

  String _buildTemporaryContinuation(
    StorySession session,
    String choice,
    int chapter,
  ) {
    if (chapter >= 4) {
      final endingGift = switch (session.genre) {
        '미스터리' => '고성의 낡은 종이 맑게 울리며 숨겨진 방을 열어 주었어요',
        '우정' => '친구들의 손에서 따뜻한 빛이 피어나 모두의 마음을 이어 주었어요',
        '자연' => '숲의 바람이 씨앗을 감싸 초록빛 길을 만들어 주었어요',
        _ => '숲속에 퍼져 있던 작은 빛들이 하나둘 모여 커다란 별길을 만들었어요',
      };
      return '주인공은 "$choice" 하기로 마음먹었어요. 그 순간 $endingGift.\n\n'
          '별길 끝에서 만난 친구들은 주인공이 지금까지 보여 준 용기와 다정함 덕분에 모두 환하게 웃었어요. 주인공은 어려운 단서도 차근차근 살피면 길이 된다는 걸 알게 되었답니다.\n\n'
          '그렇게 오늘의 모험은 포근한 추억이 되었고, 다음 모험도 분명 멋질 거라는 약속을 남긴 채 이야기는 아름답게 마무리되었답니다.';
    }

    final nextHint = switch (chapter) {
      2 => '빛을 따라가자 작은 문 하나가 나타났어요. 문에는 달, 나뭇잎, 작은 발자국 문양이 차례로 새겨져 있었답니다.',
      3 => '문 안쪽에서는 바람이 반짝이는 종을 살짝 흔들고 있었어요. 종소리는 누군가의 웃음처럼 맑고 다정했지요.',
      _ => '작은 발걸음이 새로운 장면을 열어 주었어요.',
    };

    return '주인공은 "$choice" 하기로 했어요. $nextHint 모두가 숨을 죽인 사이, 바닥에 있던 별가루가 둥실 떠오르며 길을 밝혀 주었답니다.\n\n'
        '그 빛은 겁을 내기보다 천천히 살펴보면 더 멀리 갈 수 있다고 알려 주는 것 같았어요. 주인공은 새로 배운 단어처럼 낯선 장면을 마음속에 또렷이 새기며 다음 장면으로 한 걸음 더 다가갔지요.';
  }

  Future<bool> _continueTemporaryStory(String choice) async {
    _setLoading(true);
    errorMessage = null;
    try {
      final session = currentStory!;
      final newChapterNumber = session.currentChapter + 1;
      final chapterVocab = _temporaryVocabForChapter(
        genre: session.genre,
        prompt: session.initialPrompt,
        chapter: newChapterNumber,
        choice: choice,
      );
      final chapter = StoryChapter(
        chapter: newChapterNumber,
        text: _buildTemporaryContinuation(session, choice, newChapterNumber),
        choiceMade: choice,
        imageUrl: _temporaryImageMarker(session.genre, newChapterNumber),
        selectedChoiceEmotion: _temporaryChoiceEmotion(
          choice,
          newChapterNumber,
        ),
        storyEmotion: _temporaryStoryEmotion(
          genre: session.genre,
          chapter: newChapterNumber,
        ),
      );

      final nextChoices = _temporaryChoicesForChapter(
        newChapterNumber,
        genre: session.genre,
        prompt: session.initialPrompt,
      );
      session.chapters.add(chapter);
      session.currentChapter = newChapterNumber;
      session.allChoicesMade = [...session.allChoicesMade, choice];
      session.choices = nextChoices;
      session.choiceOptions = nextChoices
          .map(
            (item) => ChoiceOption(
              text: item,
              emotion: _temporaryChoiceEmotion(item, newChapterNumber),
            ),
          )
          .toList();
      session.candidateVocab = _mergeTemporaryVocab(
        session.candidateVocab,
        chapterVocab,
      );
      psychResult = _buildPsychResultFromStory(session);
      notifyListeners();
      if (session.dbStoryId != null) {
        _queueStorySync(session, () => _syncChapter(session, chapter));
      }
      return true;
    } catch (e) {
      errorMessage = '임시 이야기를 이어쓰지 못했어요: $e';
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  PsychResult _buildPsychResultFromStory(StorySession session) {
    final records = session.choiceEmotionHistory;
    return PsychResult(
      type: '고른 선택 기록',
      description: records.isEmpty
          ? '아직 고른 선택이 없어요. 엔딩까지 읽은 뒤 선택 기록을 살펴볼 수 있어요.'
          : '이번 동화에서 고른 선택을 순서대로 기록했어요. '
                '이 기록만으로 감정이나 성격을 점수로 판단하지 않아요. '
                'AI 해설을 요청하면 당시 장면과 다른 선택지를 함께 살펴볼 수 있어요.',
      traits: const {},
      choiceInsights: records
          .map((record) => '관찰: ${record.step}번째에 “${record.choice}”를 골랐어요.')
          .toList(),
    );
  }
}
