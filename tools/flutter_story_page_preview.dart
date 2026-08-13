import 'package:fairytale_hyeonlim_merged/main.dart';
import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/story_page.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final story = StorySession(
    storyId: 'preview-story',
    genre: 'fantasy',
    age: '7',
    initialPrompt: '빛나는 성을 향한 모험',
    chapters: [
      StoryChapter(
        chapter: 1,
        text: '민호는 붉은 목도리를 고쳐 매고 빛나는 성을 향해 힘차게 달리기 시작했습니다.',
      ),
    ],
    choices: const [],
    choiceOptions: const [],
    vocab: const [],
    characters: const {'hero': "꼬마 용사 '민호'"},
    characterOverrides: const {'hero': 'male_01'},
    storyCast: const [
      StoryCastMember(
        role: 'hero',
        name: '민호',
        characterKey: 'male_01',
        profileName: '민호',
      ),
    ],
  );

  runApp(
    ChangeNotifierProvider(
      create: (_) => AppState(),
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: '동화 화면 미리보기',
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: AppColors.bg,
          colorScheme: const ColorScheme.dark(
            primary: AppColors.p500,
            secondary: AppColors.pink,
            surface: AppColors.card,
          ),
        ),
        home: StoryPage(preloadedStory: story),
      ),
    ),
  );
}
