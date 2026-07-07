import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';

import '../services/api_service.dart';
import '../services/db_service.dart';
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
    return combined;
  }

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
    notifyListeners();
    unawaited(loadUserData());
  }

  void clearSignedInUser() {
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
    psychResult = null;
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
      final stories = await DbService.fetchUserStories(userId);
      final vocabularies = await DbService.fetchUserVocabularies(userId);
      if (currentUserId != userId) return;

      _replaceCompletedStoriesFromDb(stories);
      savedVocabulary = vocabularies;
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
  }) async {
    _setLoading(true);
    errorMessage = null;
    try {
      final data = await ApiService.startStory(
        genre: genre,
        age: age,
        prompt: prompt,
      );

      final vocab = (data['vocab'] as List? ?? [])
          .map((e) => VocabWord.fromJson(e as Map<String, dynamic>))
          .toList();

      final firstChapter = StoryChapter(
        chapter: 1,
        text: data['story_text']?.toString() ?? '',
        imageB64: data['image_b64'] as String?,
        storyEmotion: _parseEmotionAnalysis(data['story_emotion']),
      );

      currentStory = StorySession(
        storyId: data['story_id']?.toString() ?? 'story_0',
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
        allChoicesMade: [],
        currentChapter: 1,
      );
      psychResult = _buildPsychResultFromStory(currentStory!);

      notifyListeners();
      unawaited(_syncStoryStart(currentStory!));
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
        imageB64: data['image_b64'] as String?,
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
      psychResult = _buildPsychResultFromStory(session);

      notifyListeners();
      unawaited(_syncChapter(session, chapter));
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
    if (_isTemporaryStory(story) || story.allChoicesMade.isEmpty) {
      psychResult = _buildPsychResultFromStory(story);
      notifyListeners();
      return;
    }
    isPsychLoading = true;
    notifyListeners();
    try {
      final data = await ApiService.analyzePsychology(
        storyId: story.storyId,
        choicesMade: story.allChoicesMade,
      );
      psychResult = PsychResult.fromJson(data);
    } catch (e) {
      psychResult = _buildPsychResultFromStory(story);
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
      psychResult = _buildPsychResultFromStory(story);
    }
    currentStory = null;
    notifyListeners();
  }

  void resetCurrentStory() {
    currentStory = null;
    psychResult = null;
    errorMessage = null;
    notifyListeners();
  }

  Future<bool> deleteCompletedStory(StorySession story) async {
    final previousStories = List<StorySession>.from(completedStories);
    completedStories.removeWhere(
      (item) => _storyIdentity(item) == _storyIdentity(story),
    );
    notifyListeners();

    try {
      final dbStoryId = story.dbStoryId;
      if (dbStoryId != null && dbStoryId.isNotEmpty) {
        await DbService.deleteStory(storyId: dbStoryId, userId: currentUserId);
        savedVocabulary.removeWhere((word) => word.originStoryId == dbStoryId);
      }
      notifyListeners();
      return true;
    } catch (e) {
      completedStories = previousStories;
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
  }) async {
    _setLoading(true);
    errorMessage = null;
    try {
      final normalizedPrompt = prompt.trim().isEmpty
          ? '반짝이는 숲속 모험'
          : prompt.trim();
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
        videoUrl: _temporaryVideoMarker(genre, 1),
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
        allChoicesMade: [],
        currentChapter: 1,
      );
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

  Future<void> _syncStoryStart(StorySession session) async {
    if (currentUserId == null || currentUserId!.isEmpty) return;
    if (session.dbStoryId == null) {
      final dbStoryId = await DbService.createStorySession(
        userId: currentUserId!,
        title: session.initialPrompt,
        genre: session.genre,
        age: session.age,
        prompt: session.initialPrompt,
      );

      if (dbStoryId == null) return;
      session.dbStoryId = dbStoryId;
    }

    var changed = false;
    for (final chapter in session.chapters) {
      final synced = await _syncSceneIfNeeded(session, chapter);
      changed = synced || changed;
      await _generateMediaForChapter(session, chapter);
    }

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
    await _generateMediaForChapter(session, chapter);
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
      imageUrl: chapter.imageUrl,
      videoUrl: chapter.videoUrl,
    );
    if (!pushed) return false;

    session.syncedChapterNumbers.add(chapter.chapter);
    return true;
  }

  Future<void> _generateMediaForChapter(
    StorySession session,
    StoryChapter chapter,
  ) async {
    if (_isTemporaryStory(session)) return;
    if (chapter.imageB64 != null || chapter.text.trim().isEmpty) return;
    if (!session.syncedChapterNumbers.contains(chapter.chapter)) return;

    final hasImageUrl = chapter.imageUrl?.trim().isNotEmpty ?? false;
    final hasVideoUrl = chapter.videoUrl?.trim().isNotEmpty ?? false;
    if (hasImageUrl || hasVideoUrl) {
      session.mediaGenerationChapterNumbers.add(chapter.chapter);
      return;
    }

    if (session.mediaGenerationChapterNumbers.contains(chapter.chapter)) {
      return;
    }

    final dbStoryId = session.dbStoryId;
    if (dbStoryId == null || dbStoryId.isEmpty) return;

    session.mediaGenerationChapterNumbers.add(chapter.chapter);
    final media = await DbService.generateSceneMedia(
      storyId: dbStoryId,
      stepNumber: chapter.chapter,
      storyText: chapter.text,
      genre: session.genre,
      age: session.age,
      includeVideo: false,
    );

    if (media == null || !media.hasMedia) {
      session.mediaGenerationChapterNumbers.remove(chapter.chapter);
      return;
    }

    if (media.imageUrl?.trim().isNotEmpty ?? false) {
      chapter.imageUrl = media.imageUrl;
    }
    if (media.videoUrl?.trim().isNotEmpty ?? false) {
      chapter.videoUrl = media.videoUrl;
    }
    notifyListeners();
  }

  bool _isTemporaryStory(StorySession session) {
    return session.storyId.startsWith('mock_');
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
        videoUrl: _temporaryVideoMarker(session.genre, newChapterNumber),
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
        unawaited(_syncChapter(session, chapter));
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
    final choices = session.allChoicesMade.join(' ');
    final text = '${session.fullStoryText} $choices';
    final cooperative = RegExp(r'함께|친구|도움|나누|손을|협동').hasMatch(text);
    final thoughtful = RegExp(r'생각|살펴|관찰|조심|단서|문양|비밀').hasMatch(text);
    final brave = RegExp(r'용기|따라가|나아|문을 열|모험|먼저|깊은').hasMatch(text);
    final creative = RegExp(r'마법|별|소원|상상|빛|지도|주문').hasMatch(text);

    final emotionScores = <String, double>{};
    void collectEmotion(EmotionAnalysis? emotion) {
      if (emotion == null) return;
      final items = emotion.topEmotions.isNotEmpty
          ? emotion.topEmotions
          : emotion.activeEmotions;
      for (final item in items.take(5)) {
        final label = item.labelDisplay.isNotEmpty
            ? item.labelDisplay
            : item.label;
        emotionScores[label] = (emotionScores[label] ?? 0) + item.score;
      }
    }

    for (final chapter in session.chapters) {
      collectEmotion(chapter.storyEmotion);
      collectEmotion(chapter.selectedChoiceEmotion);
    }
    for (final option in session.choiceOptions) {
      collectEmotion(option.emotion);
    }

    int score({
      required int base,
      required bool keyword,
      required List<String> emotionHints,
    }) {
      var value = base + (keyword ? 14 : 0);
      for (final hint in emotionHints) {
        value += ((emotionScores[hint] ?? 0) * 8).round();
      }
      return value.clamp(45, 96).toInt();
    }

    final traits = <String, int>{
      '모험적': score(
        base: 58 + session.chapters.length * 3,
        keyword: brave,
        emotionHints: const ['기대감', '즐거움/신남', '신기함/관심'],
      ),
      '친절함': score(
        base: 56,
        keyword: cooperative,
        emotionHints: const ['아껴주는', '고마움', '안심/신뢰'],
      ),
      '용감함': score(
        base: 55 + session.allChoicesMade.length * 4,
        keyword: brave,
        emotionHints: const ['기대감', '놀람', '뿌듯함'],
      ),
      '창의적': score(
        base: 60,
        keyword: creative || thoughtful,
        emotionHints: const ['신기함/관심', '감동/감탄', '깨달음'],
      ),
      '협동심': score(
        base: 52,
        keyword: cooperative,
        emotionHints: const ['아껴주는', '환영/호의', '행복'],
      ),
    };

    final sortedTraits = traits.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    final strongest = sortedTraits.first.key;

    final type = switch (strongest) {
      '협동심' => '다정한 팀 리더',
      '친절함' => '마음을 돌보는 친구',
      '창의적' => '상상력이 반짝이는 탐험가',
      '용감함' => '용기 있는 개척자',
      _ => '호기심 많은 모험가',
    };

    final description = switch (strongest) {
      '협동심' =>
        '혼자 앞서가기보다 친구들과 함께 길을 찾는 힘이 커요. 주변을 살피며 모두가 안전하게 나아가도록 돕는 타입이에요.',
      '친절함' => '이야기 속에서 따뜻한 선택과 배려의 단서가 많이 보였어요. 마음을 잘 읽고 누군가를 도우려는 장점이 돋보여요.',
      '창의적' => '낯선 장면을 상상으로 풀어내는 힘이 좋아요. 작은 단서에서도 새로운 가능성을 발견하는 타입이에요.',
      '용감함' => '두근거리는 순간에도 한 걸음 내딛는 에너지가 보여요. 어려운 길 앞에서 시도해보는 힘이 큰 장점이에요.',
      _ => '새로운 장면을 궁금해하고 탐색하는 마음이 잘 드러나요. 차근차근 이야기를 따라가며 스스로 길을 찾는 타입이에요.',
    };

    return PsychResult(type: type, description: description, traits: traits);
  }
}
