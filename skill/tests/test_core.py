import json
import os
import tempfile
import unittest
from unittest.mock import patch

from hanwang_bpm.client import HanwangClient, HanwangError, annotate_status, build_request
from hanwang_bpm.session import Session
from hanwang_bpm.sm3 import sm3, sm3_password
from hanwang_bpm.store import clear_credentials, load_credentials, save_credentials


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Sm3Test(unittest.TestCase):
    def test_abc(self):
        digest = sm3(b"abc").hex()
        self.assertEqual(digest, "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0")

    def test_empty(self):
        digest = sm3(b"").hex()
        self.assertEqual(digest, "1ab21d8355cfa17f8e61194831e81a8f22bec8c728fefb747ed035eb5082aa2b")


class RequestTest(unittest.TestCase):
    def test_token_header_and_no_signature(self):
        request = build_request(
            "https://bpm.hanvon.com",
            "/bpmeterapp/api/device/bind/list",
            {"unused": None, "devSn": "SN1"},
            "secret-token",
        )
        self.assertEqual(request.get_header("Token"), "secret-token")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertIsNone(request.get_header("Appkey"))
        self.assertNotIn(b"unused", request.data or b"")
        self.assertEqual(json.loads(request.data), {"devSn": "SN1"})

    def test_login_request_has_no_token_header(self):
        request = build_request("https://bpm.hanvon.com", "/login", {"username": "13800138000"}, None)
        self.assertIsNone(request.get_header("Token"))


class StatusTest(unittest.TestCase):
    def test_annotate_nested_status(self):
        annotated = annotate_status({"list": [{"status": "10", "highVal": 110}]})
        self.assertEqual(annotated["list"][0]["statusLabel"], "正常")


class StoreTest(unittest.TestCase):
    def setUp(self):
        self._old_config = os.environ.get("HANWANG_CONFIG_DIR")
        self._old_token = os.environ.get("HANWANG_TOKEN")
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["HANWANG_CONFIG_DIR"] = self._tmp.name
        os.environ.pop("HANWANG_TOKEN", None)
        clear_credentials()

    def tearDown(self):
        clear_credentials()
        self._tmp.cleanup()
        if self._old_config is None:
            os.environ.pop("HANWANG_CONFIG_DIR", None)
        else:
            os.environ["HANWANG_CONFIG_DIR"] = self._old_config
        if self._old_token is None:
            os.environ.pop("HANWANG_TOKEN", None)
        else:
            os.environ["HANWANG_TOKEN"] = self._old_token

    def test_round_trip_masks_permissions(self):
        path = save_credentials(token="abc12345", username="13800138000", user_id="7", nickname="甲")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        saved = load_credentials()
        self.assertEqual(saved["token"], "abc12345")
        self.assertEqual(saved["userId"], "7")


class SessionTest(StoreTest):
    def test_env_token_wins_over_file(self):
        save_credentials(token="file-token")
        os.environ["HANWANG_TOKEN"] = "env-token"
        session = Session()
        self.assertEqual(session.token, "env-token")
        self.assertEqual(session.source, "env")

    def test_blank_env_falls_back_to_file(self):
        save_credentials(token="file-token", username="13800138000")
        os.environ["HANWANG_TOKEN"] = "  "
        session = Session()
        self.assertEqual(session.token, "file-token")
        self.assertEqual(session.source, "file")

    def test_password_login_sends_sm3_and_saves_token(self):
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["body"] = json.loads(request.data)
            captured["token"] = request.get_header("Token")
            return FakeResponse(
                {
                    "code": 10001,
                    "msg": "success",
                    "data": {"id": 9, "username": "13800138000", "token": "login-token", "nickname": "乙"},
                }
            )

        with patch("hanwang_bpm.client.urllib.request.urlopen", fake_urlopen):
            result = Session().login_with_password("13800138000", "plain-password")

        self.assertNotIn("plain-password", json.dumps(captured["body"]))
        self.assertEqual(captured["body"]["password"], sm3_password("plain-password"))
        self.assertTrue(captured["body"]["password"].isupper())
        self.assertEqual(len(captured["body"]["password"]), 64)
        self.assertEqual(captured["body"]["appType"], "1101091290")
        self.assertIsNone(captured["token"])
        self.assertEqual(result["data"]["token"], "login-token")
        self.assertEqual(load_credentials()["token"], "login-token")

    def test_measurer_list_uses_dev_sn_field(self):
        captured = {}

        def fake_urlopen(request, timeout=0):
            captured["path"] = request.full_url
            captured["body"] = json.loads(request.data)
            captured["token"] = request.get_header("Token")
            return FakeResponse({"code": 10001, "msg": "success", "data": []})

        session = Session()
        session.set_token("configured-token")
        with patch("hanwang_bpm.client.urllib.request.urlopen", fake_urlopen):
            session.list_measurers("SN001")
        self.assertTrue(captured["path"].endswith("/bpmeterapp/api/measurer/list"))
        self.assertEqual(captured["body"], {"devSN": "SN001"})
        self.assertEqual(captured["token"], "configured-token")

    def test_expired_token(self):
        def fake_urlopen(request, timeout=0):
            return FakeResponse({"code": 401, "msg": "expired", "data": None})

        session = Session()
        session.set_token("stale")
        with patch("hanwang_bpm.client.urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(HanwangError) as raised:
                session.list_devices()
        self.assertEqual(raised.exception.code, 401)

    def test_requires_login(self):
        with self.assertRaises(HanwangError):
            HanwangClient().post("/bpmeterapp/api/device/bind/list", {}, token=None)


class ToolSurfaceTest(unittest.TestCase):
    def test_registered_tools(self):
        from hanwang_bpm.server import mcp

        names = {tool.name for tool in mcp._tool_manager.list_tools()}
        self.assertTrue(
            {
                "send_verify_code",
                "login_with_code",
                "login_with_password",
                "set_token",
                "auth_status",
                "list_devices",
                "list_measurers",
                "latest_readings",
                "list_readings",
                "reading_detail",
                "reading_trend",
            }.issubset(names)
        )


if __name__ == "__main__":
    unittest.main()
