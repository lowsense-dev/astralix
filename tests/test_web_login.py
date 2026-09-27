import base64
import json
import unittest

from astralix._web_login import WebLogin
from astralix.qr import QRCode


class FakeQrLogin:
    url = "tg://login?token=dGVzdA"

    async def wait(self, timeout):
        return True


class FakeClient:
    def __init__(self):
        self.qr = FakeQrLogin()

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def qr_login(self):
        return self.qr

    async def get_me(self):
        return object()


class WebLoginFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_credentials_are_saved_and_qr_login_completes(self):
        saved = []
        login = WebLogin(lambda *_: FakeClient(), save_credentials=saved.append)
        try:
            response = await login.submit({"api_id": "12345", "api_hash": "a" * 32})
            self.assertEqual(json.loads(response.body)["stage"], "phone")
            self.assertEqual(saved, [(12345, "a" * 32)])

            response = await login.submit({"qr": "start"})
            code = json.loads(response.body)["qr"]
            packed = base64.b64decode(code["data"])
            expected = QRCode()
            expected.add_data(FakeQrLogin.url)
            matrix = expected.get_matrix()
            self.assertEqual(code["size"], len(matrix))
            actual = [
                bool(packed[offset // 8] & (1 << (7 - offset % 8)))
                for offset in range(code["size"] ** 2)
            ]
            self.assertEqual(actual, [value for row in matrix for value in row])

            await login.submit({"qr": "poll"})
            self.assertEqual(login.stage, "done")
            self.assertTrue(login.done.is_set())
        finally:
            await login.close()


if __name__ == "__main__":
    unittest.main()
