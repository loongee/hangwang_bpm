"""会话 token：环境变量优先作为初始值，登录和 set_token 会覆盖当前进程并写入本地文件。"""

import logging
import os
from typing import Any

from hanwang_bpm.client import DEFAULT_BASE_URL, HanwangClient, HanwangError
from hanwang_bpm.sm3 import sm3_password
from hanwang_bpm.store import clear_credentials, load_credentials, save_credentials

log = logging.getLogger("hanwang.bpm")

SEND_CODE_PATH = "/bpmeterapp/api/member/get/verify/code/new"
LOGIN_CODE_PATH = "/bpmeterapp/api/member/verify/code/new/login"
LOGIN_PASSWORD_PATH = "/bpmeterapp/api/member/account/pwd/login"
LOGOUT_PATH = "/bpmeterapp/api/member/logout"
USER_INFO_PATH = "/bpmeterapp/api/member/get/info"
DEVICE_LIST_PATH = "/bpmeterapp/api/device/bind/list"
MEASURER_LIST_PATH = "/bpmeterapp/api/measurer/list"
LATEST_PATH = "/bpmeterapp/api/v3/device/latest/data/list"
HISTORY_PATH = "/bpmeterapp/api/device/data/list"
DETAIL_PATH = "/bpmeterapp/api/device/detail/data"
TREND_PATH = "/bpmeterapp/api/device/trend/datas"
OVERVIEW_PATH = "/bpmeterapp/api/device/overview/data"
CALENDAR_PATH = "/bpmeterapp/api/device/calendar/data"
LEVEL_PATH = "/bpmeterapp/api/v3/device/time/level/data"
WEEK_OVERVIEW_PATH = "/bpmeterapp/api/report/get/week/overview"
MONTH_OVERVIEW_PATH = "/bpmeterapp/api/report/get/month/overview"
WEEK_DISTRIBUTION_PATH = "/bpmeterapp/api/v3/report/get/week/bp/data/distribute"
MONTH_DISTRIBUTION_PATH = "/bpmeterapp/api/v3/report/get/month/bp/data/distribute"

PASSWORD_APP_TYPE = "1101091290"


def token_tail(token: str | None) -> str | None:
    if not token:
        return None
    return token[-4:]


def public_profile(record: dict[str, Any] | None) -> dict[str, Any]:
    record = record or {}
    return {
        "username": record.get("username"),
        "userId": record.get("userId") or record.get("id"),
        "nickname": record.get("nickname"),
    }


class Session:
    def __init__(self) -> None:
        self.base_url = os.environ.get("HANWANG_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
        self.client = HanwangClient(self.base_url)
        self.ignore_env = False
        self.token: str | None = None
        self.source = "none"
        self.profile: dict[str, Any] = {}
        self._load_initial_token()

    def _load_initial_token(self) -> None:
        env_token = "" if self.ignore_env else os.environ.get("HANWANG_TOKEN", "").strip()
        saved = load_credentials()
        if env_token:
            self.token = env_token
            self.source = "env"
            if saved.get("token") == env_token:
                self.profile = saved
            log.info("Using token from HANWANG_TOKEN")
            return
        saved_token = str(saved.get("token") or "").strip()
        if saved_token:
            self.token = saved_token
            self.source = "file"
            self.profile = saved
            log.info("Using token from %s", "credentials file")
            return
        self.token = None
        self.source = "none"
        self.profile = {}
        log.info("No token configured")

    def _remember(self, token: str, data: dict[str, Any] | None, source: str) -> None:
        data = data or {}
        username = data.get("username")
        user_id = data.get("id")
        nickname = data.get("nickname")
        save_credentials(
            token=token,
            username=str(username) if username is not None else None,
            user_id=str(user_id) if user_id is not None else None,
            nickname=str(nickname) if nickname is not None else None,
        )
        self.token = token
        self.source = source
        self.ignore_env = True
        self.profile = load_credentials()
        log.info("Token saved source=%s user=%s", source, username)

    def status(self) -> dict[str, Any]:
        return {
            "authenticated": bool(self.token),
            "source": self.source if self.token else "none",
            "tokenTail": token_tail(self.token),
            "baseUrl": self.base_url,
            **public_profile(self.profile),
        }

    def send_verify_code(self, username: str) -> dict[str, Any]:
        log.info("Sending verification code")
        return self.client.post(SEND_CODE_PATH, {"username": username}, auth=False)

    def login_with_code(self, username: str, verify_code: str) -> dict[str, Any]:
        envelope = self.client.post(
            LOGIN_CODE_PATH,
            {
                "username": username,
                "verifyCode": verify_code,
                "platform": "2",
                "appType": "",
                "isJoinRenmin": "0",
            },
            auth=False,
        )
        return self._finish_login(envelope, username)

    def login_with_password(self, username: str, password: str) -> dict[str, Any]:
        envelope = self.client.post(
            LOGIN_PASSWORD_PATH,
            {
                "username": username,
                "password": sm3_password(password),
                "platform": "2",
                "appType": PASSWORD_APP_TYPE,
                "isJoinRenmin": "0",
            },
            auth=False,
        )
        return self._finish_login(envelope, username)

    def _finish_login(self, envelope: dict[str, Any], username: str) -> dict[str, Any]:
        data = envelope.get("data")
        token = data.get("token") if isinstance(data, dict) else None
        if isinstance(data, str) and data:
            token = data
            data = {"username": username}
        if not token:
            raise HanwangError("登录响应里没有 token")
        if isinstance(data, dict) and not data.get("username"):
            data = {**data, "username": username}
        self._remember(str(token), data if isinstance(data, dict) else {"username": username}, "login")
        profile = public_profile(data if isinstance(data, dict) else {"username": username})
        profile["isHasDev"] = data.get("isHasDev") if isinstance(data, dict) else None
        profile["devType"] = data.get("devType") if isinstance(data, dict) else None
        return {
            "code": envelope.get("code"),
            "msg": envelope.get("msg"),
            "data": {
                "token": token,
                "saved": True,
                "source": "login",
                **profile,
            },
        }

    def set_token(self, token: str) -> dict[str, Any]:
        cleaned = token.strip()
        if not cleaned:
            raise HanwangError("token 不能为空")
        self._remember(cleaned, self.profile, "config")
        log.info("Token replaced from set_token")
        return {
            "saved": True,
            "source": "config",
            "tokenTail": token_tail(cleaned),
            "envStillSet": bool(os.environ.get("HANWANG_TOKEN", "").strip()),
        }

    def logout(self) -> dict[str, Any]:
        remote_error = None
        if self.token:
            try:
                self.client.post(LOGOUT_PATH, {}, token=self.token)
            except HanwangError as exc:
                remote_error = str(exc)
                log.warning("Remote logout failed: %s", exc)
        clear_credentials()
        env_still_set = bool(os.environ.get("HANWANG_TOKEN", "").strip())
        self.token = None
        self.source = "none"
        self.profile = {}
        self.ignore_env = True
        log.info("Local token cleared")
        return {
            "cleared": True,
            "remoteError": remote_error,
            "envStillSet": env_still_set,
        }

    def current_user(self) -> dict[str, Any]:
        envelope = self.client.post(USER_INFO_PATH, {}, token=self.token)
        data = envelope.get("data")
        if isinstance(data, dict):
            data = dict(data)
            raw_token = data.pop("token", None)
            if raw_token:
                data["tokenTail"] = token_tail(str(raw_token))
            envelope["data"] = data
            self.profile = {
                **self.profile,
                "username": data.get("username") or self.profile.get("username"),
                "userId": data.get("id") or self.profile.get("userId"),
                "nickname": data.get("nickname") or self.profile.get("nickname"),
            }
        return envelope

    def list_devices(self) -> dict[str, Any]:
        return self.client.post(DEVICE_LIST_PATH, {}, token=self.token)

    def list_measurers(self, dev_sn: str) -> dict[str, Any]:
        # 客户端测量人列表使用字段名 devSN。
        return self.client.post(MEASURER_LIST_PATH, {"devSN": dev_sn}, token=self.token)

    def latest_readings(self, dev_sn: str) -> dict[str, Any]:
        return self.client.post(LATEST_PATH, {"devSn": dev_sn}, token=self.token)

    def list_readings(
        self,
        dev_sn: str,
        dev_measurer: str,
        dimension: str,
        measured_time: str | None,
        page_size: int,
        data_flag: str,
        level_status: str | None,
    ) -> dict[str, Any]:
        return self.client.post(
            HISTORY_PATH,
            {
                "devSn": dev_sn,
                "devMeasurer": dev_measurer,
                "dimension": dimension,
                "measuredTime": measured_time,
                "pageSize": page_size,
                "dataFlag": data_flag,
                "levelStatus": level_status,
            },
            token=self.token,
        )

    def reading_detail(self, dev_sn: str, dev_measurer: str, measured_time: str) -> dict[str, Any]:
        return self.client.post(
            DETAIL_PATH,
            {"devSn": dev_sn, "devMeasurer": dev_measurer, "measuredTime": measured_time},
            token=self.token,
        )

    def reading_trend(
        self,
        dev_sn: str,
        dev_measurer: str,
        dimension: str,
        begin_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        return self.client.post(
            TREND_PATH,
            {
                "devSn": dev_sn,
                "devMeasurer": dev_measurer,
                "dimension": dimension,
                "beginDate": begin_date,
                "endDate": end_date,
            },
            token=self.token,
        )

    def reading_overview(self, dev_sn: str, dev_measurer: str, measured_time: str | None) -> dict[str, Any]:
        return self.client.post(
            OVERVIEW_PATH,
            {"devSn": dev_sn, "devMeasurer": dev_measurer, "measuredTime": measured_time},
            token=self.token,
        )

    def reading_calendar(self, dev_sn: str, dev_measurer: str) -> dict[str, Any]:
        return self.client.post(
            CALENDAR_PATH,
            {"devSn": dev_sn, "devMeasurer": dev_measurer},
            token=self.token,
        )

    def level_distribution(self, dev_sn: str, dev_measurer: str, begin_date: str, end_date: str) -> dict[str, Any]:
        return self.client.post(
            LEVEL_PATH,
            {
                "devSn": dev_sn,
                "devMeasurer": dev_measurer,
                "beginDate": begin_date,
                "endDate": end_date,
            },
            token=self.token,
        )

    def period_report(
        self,
        period: str,
        section: str,
        dev_sn: str,
        dev_measurer: str,
        begin_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        paths = {
            ("week", "overview"): WEEK_OVERVIEW_PATH,
            ("month", "overview"): MONTH_OVERVIEW_PATH,
            ("week", "distribution"): WEEK_DISTRIBUTION_PATH,
            ("month", "distribution"): MONTH_DISTRIBUTION_PATH,
        }
        path = paths.get((period, section))
        if path is None:
            raise HanwangError("period 只能是 week 或 month，section 只能是 overview 或 distribution")
        return self.client.post(
            path,
            {
                "devSn": dev_sn,
                "devMeasurer": dev_measurer,
                "beginDate": begin_date,
                "endDate": end_date,
            },
            token=self.token,
        )
