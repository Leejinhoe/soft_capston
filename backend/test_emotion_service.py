import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fairytale_emotion_service import router, runtime, KoteRuntime, unavailable


class EmotionApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_targets_are_separate_and_ordered(self):
        with patch.object(runtime, 'analyze', side_effect=lambda text: {'text': text, 'emotion_scoring_enabled': True}):
            data = self.client.post('/api/emotions/analyze', json={
                'story_text': 'story', 'choices': ['first', 'second'], 'selected_choice': 'selected'}).json()
        self.assertEqual([x['text'] for x in data['choice_emotions']], ['first', 'second'])
        self.assertEqual(data['selected_choice_emotion']['text'], 'selected')
        self.assertEqual(data['story_emotion']['text'], 'story')

    def test_missing_model_does_not_fail_request(self):
        with patch.object(runtime, 'analyze', return_value=unavailable()):
            response = self.client.post('/api/emotions/analyze', json={'choices': ['choice']})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['emotion_scoring_enabled'])

    def test_repeated_targets_are_analyzed_once_per_request(self):
        def analyze(text):
            return {'text': text, 'emotion_scoring_enabled': True,
                    'requires_review': text == 'same'}

        with patch.object(runtime, 'analyze', side_effect=analyze) as mocked:
            data = self.client.post('/api/emotions/analyze', json={
                'story_text': 'story', 'choices': ['same', 'other', 'same'],
                'selected_choice': 'same'}).json()
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual([item['text'] for item in data['choice_emotions']],
                         ['same', 'other', 'same'])
        self.assertTrue(data['selected_choice_emotion']['requires_review'])

    def test_failed_target_is_retried_within_request(self):
        def analyze(text):
            if text == 'story':
                return unavailable()
            analyze.calls += 1
            return unavailable() if analyze.calls == 1 else {'emotion_scoring_enabled': True}
        analyze.calls = 0
        with patch.object(runtime, 'analyze', side_effect=analyze):
            data = self.client.post('/api/emotions/analyze', json={
                'story_text': 'story', 'choices': ['same'], 'selected_choice': 'same'}).json()
        self.assertFalse(data['choice_emotions'][0]['emotion_scoring_enabled'])
        self.assertTrue(data['selected_choice_emotion']['emotion_scoring_enabled'])

    def test_limits(self):
        for payload in ({'choices': ['a'] * 4}, {'choices': ['a' * 1001]}, {'choices': [' ']}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/emotions/analyze', json=payload).status_code, 422)

    def test_loader_failure_is_private_and_safe(self):
        service = KoteRuntime()
        with patch.object(service, 'load', side_effect=RuntimeError('secret private path')):
            result = service.analyze('sentence')
        self.assertNotIn('secret', str(result))
        self.assertFalse(result['emotion_scoring_enabled'])

    def test_empty_input_does_not_load_model(self):
        service = KoteRuntime()
        with patch.object(service, 'load') as load:
            self.assertEqual(service.analyze(' ')['analysis_status'], 'empty_input')
            load.assert_not_called()

    def test_scene_schema_preserves_emotion_fields(self):
        from models import SceneSchema
        payload = {'emotion_label_source': 'kote_checkpoint_v1', 'primary_emotion': '기쁨'}
        scene = SceneSchema(step_number=1, story_text='story', story_emotion=payload,
                            selected_choice_emotion=payload)
        self.assertEqual(scene.model_dump()['story_emotion'], payload)
        self.assertEqual(scene.model_dump()['selected_choice_emotion'], payload)

    def test_reading_state_schema_preserves_choices_and_runtime(self):
        from models import StoryReadingStateSchema
        state = StoryReadingStateSchema(ai_story_id='ai-1', runtime_state='state-2',
            pending_choices=['first'], pending_choice_emotions=[{}], read_progress=2)
        self.assertEqual(state.model_dump()['pending_choices'], ['first'])
        self.assertEqual(state.model_dump()['runtime_state'], 'state-2')

    def test_api_serializers_preserve_emotions(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'serialize_scene')
        namespace = {'serialize_datetime': lambda value: value, 'serialize_object_id': lambda value: value}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<serializer>', 'exec'), namespace)
        emotion = {'primary_emotion': '공포/무서움'}
        result = namespace['serialize_scene']({'content': 'text', 'user_choice': 'choice',
            'story_emotion': emotion, 'selected_choice_emotion': emotion})
        self.assertEqual(result['story_emotion'], emotion)
        self.assertEqual(result['selected_choice_emotion'], emotion)


if __name__ == '__main__':
    unittest.main()
