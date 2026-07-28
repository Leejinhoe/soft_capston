import unittest
from unittest.mock import patch

from bson import ObjectId

import main


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


if __name__ == "__main__":
    unittest.main()
