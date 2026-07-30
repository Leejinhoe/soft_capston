import asyncio
import unittest

import main


class RootResponseTests(unittest.TestCase):
    def test_root_returns_a_readable_korean_status_message(self):
        response = asyncio.run(main.root())

        self.assertEqual(
            response,
            {"message": "동화 생성 API 서버가 정상적으로 실행 중입니다."},
        )


if __name__ == "__main__":
    unittest.main()
