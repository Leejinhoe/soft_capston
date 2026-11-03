import unittest
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from models import UserSchema


class AuthTokenTests(unittest.TestCase):
    def setUp(self):
        self.user = {
            "_id": ObjectId(),
            "account_id": "test-user",
        }

    def test_issued_token_round_trips(self):
        token = main.issue_access_token(self.user)
        payload = main.verify_access_token(f"Bearer {token}")

        self.assertEqual(payload["uid"], str(self.user["_id"]))
        self.assertEqual(payload["account_id"], "test-user")

    def test_tampered_token_is_rejected(self):
        token = main.issue_access_token(self.user)
        encoded, signature = token.split(".", 1)
        tampered = f"{encoded[:-1]}A.{signature}"

        with self.assertRaises(ValueError):
            main.verify_access_token(f"Bearer {tampered}")

    def test_expired_token_is_rejected(self):
        with patch.object(main.time, "time", return_value=100):
            token = main.issue_access_token(self.user)
        with patch.object(
            main.time,
            "time",
            return_value=100 + main.AUTH_TOKEN_TTL_SECONDS + 1,
        ):
            with self.assertRaises(ValueError):
                main.verify_access_token(f"Bearer {token}")

    def test_missing_bearer_token_is_rejected(self):
        with self.assertRaises(ValueError):
            main.verify_access_token(None)

    def test_route_access_policy_protects_media_and_story_writes(self):
        self.assertEqual(
            main.route_access_policy('/api/media/jobs', 'POST'),
            'authenticated',
        )
        self.assertEqual(
            main.route_access_policy('/api/stories/create', 'POST'),
            'authenticated',
        )
        self.assertEqual(
            main.route_access_policy('/api/media/characters/male_01', 'PUT'),
            'admin',
        )
        self.assertEqual(
            main.route_access_policy('/api/community/reports', 'POST'),
            'authenticated',
        )

    def test_route_access_policy_protects_vocabulary_and_community_writes(self):
        protected_routes = [
            ('/api/auth/session', 'GET'),
            ('/api/vocabularies/add', 'POST'),
            ('/api/vocabularies/507f1f77bcf86cd799439011', 'DELETE'),
            ('/api/community/posts', 'POST'),
            ('/api/community/posts/507f1f77bcf86cd799439011/like', 'POST'),
            ('/api/community/posts/507f1f77bcf86cd799439011/comments', 'POST'),
            ('/api/community/posts/507f1f77bcf86cd799439011', 'DELETE'),
            (
                '/api/community/posts/507f1f77bcf86cd799439011/comments/'
                '507f1f77bcf86cd799439012',
                'DELETE',
            ),
        ]
        for path, method in protected_routes:
            with self.subTest(path=path, method=method):
                self.assertEqual(main.route_access_policy(path, method), 'authenticated')

        self.assertEqual(
            main.route_access_policy('/api/community/posts', 'GET'),
            'public',
        )

    def test_protected_writes_reject_requests_without_bearer_token(self):
        requests = [
            ('GET', '/api/auth/session'),
            ('POST', '/api/vocabularies/add'),
            ('DELETE', '/api/vocabularies/507f1f77bcf86cd799439011'),
            ('POST', '/api/community/posts'),
            ('POST', '/api/community/posts/507f1f77bcf86cd799439011/like'),
            (
                'POST',
                '/api/community/posts/507f1f77bcf86cd799439011/comments',
            ),
            ('DELETE', '/api/community/posts/507f1f77bcf86cd799439011'),
            (
                'DELETE',
                '/api/community/posts/507f1f77bcf86cd799439011/comments/'
                '507f1f77bcf86cd799439012',
            ),
        ]
        client = TestClient(main.app)
        for method, path in requests:
            with self.subTest(method=method, path=path):
                response = client.request(method, path, json={})
                self.assertEqual(response.status_code, 401)
        client.close()

    def test_route_access_policy_limits_user_data_to_owner(self):
        self.assertEqual(
            main.route_access_policy('/api/users/user-id/stories', 'GET'),
            'user_resource_owner',
        )
        self.assertEqual(
            main.route_access_policy('/api/users/by-account/account-id', 'GET'),
            'account_owner',
        )

    def test_registration_and_login_remain_public(self):
        self.assertEqual(
            main.route_access_policy('/api/users/register', 'POST'),
            'public',
        )
        self.assertEqual(
            main.route_access_policy('/api/users/login', 'POST'),
            'public',
        )

    def test_only_catalog_character_assets_are_shared(self):
        self.assertTrue(
            main.is_shared_character_asset(
                {
                    'asset_role': 'character_reference',
                    'character_key': 'male_01',
                }
            )
        )
        self.assertFalse(
            main.is_shared_character_asset(
                {
                    'asset_role': 'generated_scene',
                    'character_key': 'male_01',
                }
            )
        )


class RegistrationSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_reserved_admin_account_id_cannot_be_registered(self):
        with self.assertRaises(HTTPException) as raised:
            await main.register_user(
                UserSchema(
                    account_id=main.ADMIN_ACCOUNT_ID,
                    password="not-an-admin-password",
                    nickname="reserved-id-attempt",
                )
            )

        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
