import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bson import ObjectId

import main
from media_queue import serialize_media_job_document


class CloudflareQueueRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_enabled_worker_claims_cloudflare_jobs(self):
        collection = SimpleNamespace(find_one_and_update=AsyncMock(return_value=None))
        with patch.object(main, 'media_jobs_collection', collection):
            with patch.object(main, 'cloudflare_character_enabled', return_value=True):
                await main.claim_pending_media_job()
                query = collection.find_one_and_update.await_args.args[0]
                self.assertIn('pending_cloudflare', query['status']['$in'])
            with patch.object(main, 'cloudflare_character_enabled', return_value=False):
                await main.claim_pending_media_job()
                query = collection.find_one_and_update.await_args.args[0]
                self.assertNotIn('pending_cloudflare', query['status']['$in'])

    async def test_stale_cloudflare_jobs_keep_reserved_status(self):
        collection = SimpleNamespace(update_many=AsyncMock(
            side_effect=[SimpleNamespace(modified_count=1), SimpleNamespace(modified_count=2)]))
        with patch.object(main, 'media_jobs_collection', collection):
            self.assertEqual(await main.reset_stale_running_media_jobs(), 3)
        first, second = collection.update_many.await_args_list
        self.assertEqual(first.args[1]['$set']['status'], 'pending_cloudflare')
        self.assertEqual(second.args[0]['required_image_provider']['$ne'], 'cloudflare_workers_ai')

    def test_reserved_status_is_presented_as_pending(self):
        result = serialize_media_job_document({'_id': ObjectId(), 'status': 'pending_cloudflare'})
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['image']['status'], 'pending')
