import 'package:fairytale_hyeonlim_merged/character_chat_page.dart';
import 'package:fairytale_hyeonlim_merged/models/app_state.dart';
import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  test('등장인물 응답을 앱 모델로 변환한다', () {
    final character = StoryCharacter.fromJson({
      'name': '별이',
      'role': '이야기의 주인공',
      'personality': '호기심이 많고 친구를 소중히 여겨요.',
      'greeting': '안녕! 나는 별이야.',
      'avatar_emoji': '🐰',
    });

    expect(character.name, '별이');
    expect(character.avatarEmoji, '🐰');
    expect(character.toJson()['personality'], contains('호기심'));
  });

  test('캐릭터 답장과 추천 질문을 최대 세 개만 읽는다', () {
    final reply = CharacterChatReply.fromJson({
      'reply': '숲에서 친구와 함께 길을 찾던 순간이 가장 기억나!',
      'suggested_replies': ['왜 기억에 남아?', '무섭지는 않았어?', '', '친구는 누구야?'],
    });

    expect(reply.reply, contains('친구'));
    expect(reply.suggestedReplies, hasLength(3));
    expect(reply.suggestedReplies, isNot(contains('')));
  });

  test('대화 기록에는 서버 전송에 필요한 값만 직렬화한다', () {
    final message = CharacterChatMessage(
      role: 'user',
      content: '그때 어떤 기분이었어?',
      createdAt: DateTime(2026, 8, 12),
    );

    expect(message.isUser, isTrue);
    expect(message.toJson(), {
      'role': 'user',
      'content': '그때 어떤 기분이었어?',
    });
  });

  testWidgets('임시 동화에서는 서버 없이 캐릭터 대화를 시작한다', (tester) async {
    final story = StorySession(
      storyId: 'mock_character_chat',
      genre: '판타지',
      age: '초등 저학년',
      initialPrompt: '별이와 여우의 숲 모험',
      chapters: [
        StoryChapter(
          chapter: 1,
          text: '별이는 숲길에서 여우 친구를 만났어요. 별이가 여우에게 함께 가자고 말했어요.',
        ),
      ],
      choices: const [],
      choiceOptions: const [],
      vocab: const [],
    );

    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AppState(),
        child: MaterialApp(home: CharacterChatPage(story: story)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('이야기 속 친구와 대화'), findsOneWidget);
    expect(find.text('누구와 이야기할까요?'), findsOneWidget);
    expect(find.textContaining('임시 동화의 등장인물'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '그때 어떤 기분이었어?');
    await tester.tap(find.byTooltip('메시지 보내기'));
    await tester.pumpAndSettle();

    expect(find.text('그때 어떤 기분이었어?'), findsOneWidget);
    expect(find.textContaining('조금 떨렸지만'), findsOneWidget);
  });
}
