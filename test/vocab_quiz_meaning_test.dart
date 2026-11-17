import 'package:fairytale_hyeonlim_merged/models/story_model.dart';
import 'package:fairytale_hyeonlim_merged/vocab_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('퀴즈는 뜻을 보여 주고 단어를 답으로 고른다', (tester) async {
    final words = [
      VocabWord(hard: '용기', easy: '두려워도 힘을 내는 마음', definition: '두려워도 힘을 내는 마음'),
      VocabWord(hard: '우정', easy: '친구 사이의 다정한 마음', definition: '친구 사이의 다정한 마음'),
    ];
    await tester.pumpWidget(MaterialApp(home: VocabQuizPage(vocabs: words)));
    expect(find.text('이 뜻에 맞는 단어는?'), findsOneWidget);
    expect(find.text('용기'), findsOneWidget);
    expect(find.text('우정'), findsOneWidget);
    expect(
      find.text('두려워도 힘을 내는 마음').evaluate().length +
          find.text('친구 사이의 다정한 마음').evaluate().length,
      1,
    );
  });
}
