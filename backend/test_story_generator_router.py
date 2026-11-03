import unittest

from story_generator_router import (
    HERO_NAME_MAP,
    StoryCharacterChatRequest,
    StoryCharactersRequest,
    StoryContinueRequest,
    StoryPsychRequest,
    StoryStartRequest,
    handle_story_character_chat,
    handle_story_characters,
    handle_story_continue,
    handle_story_health,
    handle_story_psych,
    handle_story_start,
)
from scene_contract import normalize_scene_contract


class StoryContinuationTests(unittest.IsolatedAsyncioTestCase):
    async def test_story_start_uses_hero_role_key_and_official_character_names(self):
        result = await handle_story_start(StoryStartRequest(
            genre='판타지',
            age='초등_저학년',
            prompt='별빛 숲의 비밀',
            character_key='female_01',
        ))
        self.assertIn('hero', result['characters'])
        self.assertEqual(len(result['characters']), 1)
        self.assertIn('미나', result['characters']['hero'])
        self.assertIn('미나', result['story_text'])
        for item in result['vocab']:
            self.assertIn(item['hard'], result['story_text'])
            self.assertTrue(item['easy'])
            self.assertTrue(item['definition'])
            self.assertNotEqual(item['easy'], item['definition'])
        self.assertEqual(len(HERO_NAME_MAP), 16)
        self.assertEqual(HERO_NAME_MAP['female_03'], '미란')
        self.assertEqual(HERO_NAME_MAP['male_03'], '태산')
        self.assertEqual(HERO_NAME_MAP['female_08'], '솔')

    async def test_runtime_state_advances_until_ending(self):
        state = 'ch1_female_01_판타지'
        for expected in (2, 3, 4):
            result = await handle_story_continue(StoryContinueRequest(
                story_id='test', choice='길을 따라간다', character_key='female_01',
                runtime_state=state,
            ))
            self.assertEqual(result['chapter'], expected)
            self.assertEqual(result['completed'], expected == 4)
            self.assertTrue(normalize_scene_contract(result['scene_contract'])['valid'])
            for item in result['vocab']:
                self.assertIn(item['hard'], result['new_text'])
            state = result['runtime_state']

    async def test_older_ending_rest_is_accepted(self):
        normalized = normalize_scene_contract({'action': 'rest'})
        self.assertTrue(normalized['valid'])
        self.assertEqual(normalized['action'], 'idle')

    async def test_unknown_runtime_state_uses_legacy_story(self):
        result = await handle_story_continue(StoryContinueRequest(
            story_id='test', choice='기다린다', runtime_state='unknown-format',
            story_so_far=('가' * 31) + '\n\n' + ('나' * 31),
        ))
        self.assertEqual(result['chapter'], 3)

    async def test_quiet_choice_in_chapter_3_preserves_quiet_contract_for_image_reuse(self):
        ch2 = await handle_story_continue(StoryContinueRequest(
            story_id='test', choice='숲속 오솔길을 따라간다', character_key='female_01',
            runtime_state='ch1_female_01_판타지',
        ))
        ch3_quiet = await handle_story_continue(StoryContinueRequest(
            story_id='test', choice=ch2['choices'][0], character_key='female_01',
            runtime_state=ch2['runtime_state'],
        ))
        ch3_active = await handle_story_continue(StoryContinueRequest(
            story_id='test', choice=ch2['choices'][1], character_key='female_01',
            runtime_state=ch2['runtime_state'],
        ))
        c2 = ch2['scene_contract']
        c3_q = ch3_quiet['scene_contract']
        c3_a = ch3_active['scene_contract']
        self.assertEqual(c2['action'], 'idle')
        self.assertEqual(c3_q['action'], 'idle')
        self.assertEqual(c2['visual_anchor'], c3_q['visual_anchor'])
        self.assertEqual(c2['required_props'], c3_q['required_props'])
        self.assertEqual(c2['target'], c3_q['target'])
        self.assertEqual(c3_a['action'], 'journey')
        self.assertNotEqual(c2['visual_anchor'], c3_a['visual_anchor'])

    async def test_psych_characters_chat_and_health_endpoints(self):
        health = await handle_story_health()
        self.assertEqual(health['status'], 'ok')

        psych = await handle_story_psych(StoryPsychRequest(
            story_id='test',
            story_title='별빛 숲의 비밀',
            choices_made=[
                '주변을 둘러보며 숨겨진 위험이나 함정이 없는지 살핀다.',
                '바위에 새겨진 정령의 고대 문자를 제자리에서 천천히 해독해 본다.',
            ],
            completed=True,
        ))
        self.assertIn('탐험가', psych['type'])
        self.assertEqual(len(psych['choice_insights']), 2)
        self.assertGreaterEqual(len(psych['caregiver_prompts']), 2)

        chars = await handle_story_characters(StoryCharactersRequest(
            story_id='test',
            story_title='별빛 숲의 비밀',
            story_text='달빛이 창문을 두드리던 밤, 미나(은)는 보물 상자를 열었습니다.',
        ))
        self.assertGreaterEqual(len(chars['characters']), 2)
        self.assertEqual(chars['characters'][0]['name'], '미나')

        chat_reply = await handle_story_character_chat(StoryCharacterChatRequest(
            story_id='test',
            story_title='별빛 숲의 비밀',
            story_text='미나(은)는 별빛 정원에 도착했습니다.',
            user_name='초이',
            character={'name': '미나'},
            user_message='모험에서 가장 기억나는 순간은 뭐야?',
        ))
        self.assertIn('초이', chat_reply['reply'])
        self.assertEqual(len(chat_reply['suggested_replies']), 3)

        letter_reply = await handle_story_character_chat(StoryCharacterChatRequest(
            story_id='test',
            story_title='별빛 숲의 비밀',
            story_text='미나(은)는 별빛 정원에 도착했습니다.',
            user_name='초이',
            character={'name': '미나'},
            messages=[{'role': 'user', 'content': '편지: 미나야 함께 모험해서 정말 즐거웠어!'}],
            user_message='나는 너에게 이런 편지를 썼어. 따뜻하게 답장해 줘.\n미나야 함께 모험해서 정말 즐거웠어!',
        ))
        self.assertIn('미나 보냄', letter_reply['reply'])


if __name__ == '__main__':
    unittest.main()
