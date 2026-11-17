import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/story_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('한 장면을 전체 영상처럼 만들지 않고 완성 후 합성을 안내한다', (tester) async {
    final story = StorySession(
      storyId: 'media-retry',
      dbStoryId: 'db-media-retry',
      genre: '모험',
      age: '',
      initialPrompt: '숲속 우체부',
      chapters: [
        StoryChapter(
          chapter: 1,
          text: '다온이가 숲길에서 편지를 찾았어요.',
          mediaStatus: 'failed',
          mediaError: '통합 서버에서 삽화를 만들지 못했습니다.',
        ),
      ],
      choices: const ['친구에게 편지를 전해요'],
      choiceOptions: const [],
      vocab: const [],
    );
    final state = AppState()..currentStory = story;

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: const MaterialApp(home: StoryPage()),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('전체 동화 영상'),
      300,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.textContaining('현재 1장면 · 삽화 0장'), findsOneWidget);
    expect(find.textContaining('모든 장면의 삽화를 순서대로 이어 붙여요.'), findsOneWidget);
    expect(find.text('삽화 영상 만들기'), findsNothing);
    expect(find.byTooltip('삽화 다시 생성'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  testWidgets('실제 영상 보기와 캐릭터 움직임 메뉴를 함께 보여준다', (tester) async {
    final story = StorySession(
      storyId: 'video-and-motion',
      genre: '모험',
      age: '',
      initialPrompt: '숲속 우체부',
      chapters: [
        StoryChapter(
          chapter: 1,
          text: '다온이가 숲속 친구를 도와줬어요. Daon walked along the forest path.',
          imageUrl: 'https://media.example/scene.png',
          videoUrl: 'https://media.example/scene.mp4',
        ),
      ],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
      characterOverrides: const {'hero': 'male_01'},
    );
    final state = AppState()..currentStory = story;

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: const MaterialApp(home: StoryPage()),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('이 장면만 보는 미리보기'),
      300,
      scrollable: find.byType(Scrollable).first,
    );

    expect(find.byTooltip('이 장면만 보기'), findsOneWidget);
    expect(find.text('캐릭터 움직임 보기'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  testWidgets('동화의 하단 메뉴가 선택한 주 메뉴로 돌아간다', (tester) async {
    final state = AppState()
      ..currentStory = StorySession(
        storyId: 'nav',
        genre: '모험',
        age: '',
        initialPrompt: '이야기',
        chapters: [StoryChapter(chapter: 1, text: '시작')],
        choices: const ['길을 떠난다'],
        choiceOptions: const [],
        vocab: const [],
      );
    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const StoryPage()),
                ),
                child: const Text('동화 열기'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('동화 열기'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('단어장'));
    await tester.pumpAndSettle();
    expect(state.selectedMainTab, 3);
    expect(find.text('동화 열기'), findsOneWidget);
    expect(state.currentStory, isNotNull);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });

  testWidgets('원본 화면처럼 장면 아래에 선택지를 표시하고 음성 기능을 유지한다', (tester) async {
    final story = StorySession(
      storyId: 'preview',
      genre: '모험',
      age: '초등_저학년',
      initialPrompt: '별빛 숲',
      chapters: [StoryChapter(chapter: 1, text: '토끼가 별을 찾았어요.')],
      choices: const ['토끼에게 말을 걸어요', '숲길을 따라가요', '주변을 살펴봐요'],
      choiceOptions: const [],
      vocab: const [],
    );
    final state = AppState()..currentStory = story;
    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: const MaterialApp(home: StoryPage()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('동화 낭독'), findsOneWidget);
    expect(find.text('내 목소리'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('어떻게 할까요?'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('어떻게 할까요?'), findsOneWidget);
    expect(find.text('토끼에게 말을 걸어요'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox.shrink());
    state.dispose();
  });
}
