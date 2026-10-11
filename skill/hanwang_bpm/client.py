"""汉王血压云端 HTTP 客户端。只发 JSON POST，鉴权头名为 token。"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("hanwang.bpm")

DEFAULT_BASE_URL = "https://bpm.hanvon.com"
SUCCESS_CODES = {0, 10001, 10002}
TOKEN_EXPIRED = 401
TIMEOUT_SECONDS = 60

STATUS_LABELS = {
    3: "三级",
    2: "二级",
    1: "一级",
    9: "偏低",
    11: "正常高值",
    10: "正常",
    -1: "正常",
}


class HanwangError(Exception):
    def __init__(self, message: str, *, code: int | None = None):
        super().__init__(message)
        self.code = code


def omit_nulls(payload: dict[str, Any] | None) -> dict[str, Any]:
    return {key: value for key, value in (payload or {}).items() if value is not None}


def build_request(base_url: str, path: str, payload: dict[str, Any] | None, token: str | None) -> urllib.request.Request:
    body = json.dumps(omit_nulls(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
    }
    if token:
        headers["token"] = token
    url = base_url.rstrip("/") + path
    return urllib.request.Request(url, data=body, headers=headers, method="POST")


def annotate_status(value: Any) -> Any:
    if isinstance(value, list):
        return [annotate_status(item) for item in value]
    if not isinstance(value, dict):
        return value
    annotated = {key: annotate_status(item) for key, item in value.items()}
    if "status" in annotated and "statusLabel" not in annotated:
        try:
            code = int(annotated["status"])
        except (TypeError, ValueError):
            code = None
        label = STATUS_LABELS.get(code) if code is not None else None
        if label:
            annotated["statusLabel"] = label
    return annotated


def _as_code(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


class HanwangClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/") or DEFAULT_BASE_URL

    def post(self, path: str, payload: dict[str, Any] | None = None, *, token: str | None = None, auth: bool = True) -> dict[str, Any]:
        if auth and not token:
            raise HanwangError("未登录。请先调用登录工具，或在 MCP 环境变量 HANWANG_TOKEN 中配置 token。", code=TOKEN_EXPIRED)
        request = build_request(self.base_url, path, payload, token if auth else None)
        log.info("POST %s", path)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            log.error("HTTP %s from %s", exc.code, path)
            raise HanwangError(f"HTTP {exc.code}: {raw[:300]}") from exc
        except urllib.error.URLError as exc:
            log.error("Request failed: %s", exc.reason)
            raise HanwangError(f"请求失败: {exc.reason}") from exc

        log.info("HTTP %s", status)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HanwangError("响应不是 JSON") from exc
        if not isinstance(parsed, dict):
            raise HanwangError("响应 JSON 不是对象")

        code = _as_code(parsed.get("code"))
        message = parsed.get("msg") or parsed.get("message") or ""
        log.info("Response code=%s msg=%s", code, message)
        if code == TOKEN_EXPIRED:
            raise HanwangError("token 已失效，请重新登录或更新 HANWANG_TOKEN。", code=TOKEN_EXPIRED)
        if code not in SUCCESS_CODES:
            raise HanwangError(f"{message or '请求失败'} (code={code})", code=code if isinstance(code, int) else None)
        parsed["code"] = code
        parsed["data"] = annotate_status(parsed.get("data"))
        return parsed
