import 'package:flutter/foundation.dart';
import 'story_model.dart';
import '../services/api_service.dart';

class AppState extends ChangeNotifier {
  // ─── 현재 진행 중인 이야기 ───
  StorySession? currentStory;
  bool isLoading = false;
  String? errorMessage;

  // ─── 완료된 이야기 목록 ───
  List<StorySession> completedStories = [];

  // ─── 심리 분석 결과 ───
  PsychResult? psychResult;
  bool isPsychLoading = false;

  void _setLoading(bool v) {
    isLoading = v;
    notifyListeners();
  }

  void clearError() {
    errorMessage = null;
    notifyListeners();
  }

  // ─── 새 동화 시작 ───
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

      currentStory = StorySession(
        storyId: data['story_id'] ?? 'story_0',
        genre: genre,
        age: age,
        initialPrompt: prompt,
        chapters: [StoryChapter(chapter: 1, text: data['story_text'] ?? '')],
        choices: List<String>.from(data['choices'] ?? []),
        vocab: vocab,
        allChoicesMade: [],
        currentChapter: 1,
      );
      notifyListeners();
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // ─── 선택 후 이어쓰기 ───
  Future<bool> continueStory(String choice) async {
    if (currentStory == null) return false;
    _setLoading(true);
    errorMessage = null;
    try {
      final data = await ApiService.continueStory(
        storyId: currentStory!.storyId,
        storySoFar: currentStory!.fullStoryText,
        choice: choice,
        genre: currentStory!.genre,
        age: currentStory!.age,
      );

      final newText = data['new_text'] ?? '';
      final newChapter = currentStory!.currentChapter + 1;

      final vocab = (data['vocab'] as List? ?? [])
          .map((e) => VocabWord.fromJson(e as Map<String, dynamic>))
          .toList();

      currentStory!.chapters.add(
        StoryChapter(chapter: newChapter, text: newText, choiceMade: choice),
      );
      currentStory!.choices = List<String>.from(data['choices'] ?? []);
      currentStory!.vocab = [...currentStory!.vocab, ...vocab];
      currentStory!.allChoicesMade = [...currentStory!.allChoicesMade, choice];
      currentStory!.currentChapter = newChapter;

      notifyListeners();
      return true;
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
      notifyListeners();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // ─── 심리 분석 ───
  Future<void> loadPsychAnalysis() async {
    if (currentStory == null) return;
    isPsychLoading = true;
    notifyListeners();
    try {
      final data = await ApiService.analyzePsychology(
        storyId: currentStory!.storyId,
        choicesMade: currentStory!.allChoicesMade,
      );
      psychResult = PsychResult.fromJson(data);
    } catch (e) {
      errorMessage = e.toString().replaceAll('Exception: ', '');
    } finally {
      isPsychLoading = false;
      notifyListeners();
    }
  }

  // ─── 이야기 완료 처리 ───
  void finishCurrentStory() {
    if (currentStory != null) {
      completedStories.insert(0, currentStory!);
    }
    currentStory = null;
    psychResult = null;
    notifyListeners();
  }

  void resetCurrentStory() {
    currentStory = null;
    psychResult = null;
    errorMessage = null;
    notifyListeners();
  }
}
