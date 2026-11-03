import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class TestDeployGateTests(unittest.TestCase):
    def test_optional_key_blocks_otherwise_public_routes(self):
        with patch.dict(os.environ, {'TEST_DEPLOY_ACCESS_KEY': 'test-only-secret'}):
            client = TestClient(main.app)
            self.assertEqual(client.get('/api/emotions/health').status_code, 403)
            self.assertEqual(client.get('/api/emotions/health', headers={'X-Test-Key': 'wrong'}).status_code, 403)
            self.assertEqual(client.get('/api/emotions/health', headers={'X-Test-Key': 'test-only-secret'}).status_code, 200)
            self.assertEqual(client.get('/').status_code, 200)

    def test_no_key_preserves_existing_policy(self):
        with patch.dict(os.environ, {'TEST_DEPLOY_ACCESS_KEY': ''}):
            self.assertEqual(TestClient(main.app).get('/api/emotions/health').status_code, 200)
