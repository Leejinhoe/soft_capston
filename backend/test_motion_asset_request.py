import unittest

from motion_asset_request import missing_motion_asset_request


class MotionAssetRequestTests(unittest.TestCase):
    def test_telescope_is_not_misclassified_as_idle(self):
        request = missing_motion_asset_request(
            character_key='male_01', identity={}, motion_plan={'action': 'idle'},
            parameters={'motion_asset_tier': 'generic_motion_sheet'},
            story_text='민호가 망원경을 눈에 대고 성을 살펴본다.',
        )
        self.assertEqual(request['action'], 'look_through_telescope')
        self.assertEqual(request['required_props'], ['handheld telescope'])

    def test_reference_transform_records_locked_character_and_semantics(self):
        request = missing_motion_asset_request(
            character_key='female_04',
            identity={'asset_fingerprint': 'ref-123', 'asset_version': 'v2'},
            motion_plan={'action': 'handoff', 'requires_partner': True,
                         'requires_object': True, 'required_props': ['book']},
            parameters={'motion_asset_tier': 'reference_transform'},
        )
        self.assertEqual(request['character_key'], 'female_04')
        self.assertEqual(request['action'], 'handoff')
        self.assertTrue(request['requires_partner'])
        self.assertEqual(request['required_props'], ['book'])
        self.assertEqual(request['reference_asset_fingerprint'], 'ref-123')

    def test_existing_real_motion_and_idle_do_not_create_request(self):
        for action, tier in [('journey', 'identity_run_cycle'),
                             ('idle', 'reference_transform')]:
            self.assertIsNone(missing_motion_asset_request(
                character_key='male_01', identity={}, motion_plan={'action': action},
                parameters={'motion_asset_tier': tier},
            ))

    def test_missing_character_is_not_assigned_a_different_identity(self):
        self.assertIsNone(missing_motion_asset_request(
            character_key=None, identity={}, motion_plan={'action': 'jump'},
            parameters={'motion_asset_tier': 'camera_only'},
        ))


if __name__ == '__main__':
    unittest.main()
