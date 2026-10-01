import 'dart:convert';
import 'dart:io';

import 'package:fairytale_hyeonlim_merged/services/api_service.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late HttpServer server;
  late List<Map<String, dynamic>> requests;

  setUp(() async {
    requests = [];
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    dotenv.testLoad(
      fileInput: 'AI_API_BASE_URL=http://127.0.0.1:${server.port}',
    );
    server.listen((request) async {
      requests.add(
        Map<String, dynamic>.from(
          jsonDecode(await utf8.decoder.bind(request).join()) as Map,
        ),
      );
      request.response.headers.contentType = ContentType.json;
      request.response.write(
        jsonEncode({
          'chapter': 2,
          'text': '별이는 친구와 함께 숲길을 살펴보았어요.',
          'choices': ['지도에서 길을 찾아본다', '친구에게 도움을 부탁한다', '주변의 발자국을 살펴본다'],
          'scene_contract': {'location': '숲길'},
        }),
      );
      await request.response.close();
    });
  });

  tearDown(() async {
    await server.close(force: true);
    dotenv.clean();
  });

  const character = {
    'character_key': 'male_01',
    'name': '별이',
    'description': '푸른 옷을 입은 작은 모험가',
  };
  const cast = [
    {'role': 'hero', 'name': '별이', 'character_key': 'male_01'},
  ];
  const overrides = {'hero': 'male_01'};

  test('start keeps the selected character and cast contract', () async {
    final result = await ApiService.startStory(
      genre: '판타지',
      age: '',
      prompt: '숲에서 친구를 찾는 모험',
      characterContext: character,
      storyCast: cast,
      characterOverrides: overrides,
    );

    expect(requests.single['character_context'], character);
    expect(requests.single['character_key'], 'male_01');
    expect(requests.single['story_cast'], cast);
    expect(requests.single['character_overrides'], overrides);
    expect(requests.single['prompt'], contains('[CHARACTER LOCK]'));
    expect(result['scene_contract'], {'location': '숲길'});
  });

  test(
    'compact continuation keeps identity and previous scene contract',
    () async {
      await ApiService.continueStory(
        storyId: 'story-1',
        storySoFar: '이전 동화 전체',
        choice: '친구에게 도움을 부탁한다',
        genre: '판타지',
        age: '',
        runtimeState: '  serialized-game-state  ',
        characterContext: character,
        storyCast: cast,
        characterOverrides: overrides,
        previousSceneContract: {'location': '마을', 'stage': 1},
      );

      expect(requests.single['runtime_state'], 'serialized-game-state');
      expect(requests.single.containsKey('story_so_far'), isFalse);
      expect(requests.single['choice'], '친구에게 도움을 부탁한다');
      expect(requests.single['character_context'], character);
      expect(requests.single['story_cast'], cast);
      expect(requests.single['character_overrides'], overrides);
      expect(requests.single['previous_scene_contract'], {
        'location': '마을',
        'stage': 1,
      });
      expect(
        requests.single['character_instruction'],
        contains('[CHARACTER LOCK]'),
      );
    },
  );

  test(
    'legacy continuation still sends full story without runtime state',
    () async {
      await ApiService.continueStory(
        storyId: 'story-1',
        storySoFar: '이전 동화 전체',
        choice: '지도에서 길을 찾아본다',
        genre: '판타지',
        age: '',
      );

      expect(requests.single['story_so_far'], '이전 동화 전체');
      expect(requests.single.containsKey('runtime_state'), isFalse);
    },
  );
}
