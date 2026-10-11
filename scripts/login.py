#!/usr/bin/env python3
"""汉王大健康验证码登录。

流程：输入手机号 -> 发送验证码 -> 输入验证码 -> 登录并输出 token。
"""

import json
import logging
import re
import sys
import urllib.error
import urllib.request

BASE_URL = "https://bpm.hanvon.com"
SEND_CODE_PATH = "/bpmeterapp/api/member/get/verify/code/new"
LOGIN_PATH = "/bpmeterapp/api/member/verify/code/new/login"
# 客户端把这几个 code 都当成成功
SUCCESS_CODES = {0, 10001, 10002}
TIMEOUT_SECONDS = 60
PHONE_PATTERN = re.compile(r"^1\d{10}$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hanwang.login")


def prompt(label: str) -> str:
    try:
        return input(label).strip()
    except EOFError:
        log.error("Input closed before a value was entered")
        sys.exit(1)


def post_json(path: str, payload: dict) -> dict:
    url = BASE_URL + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    log.info("POST %s", url)
    log.info("Request body: %s", json.dumps(payload, ensure_ascii=False))
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        log.error("HTTP %s from %s", exc.code, url)
        log.error("Response body: %s", raw)
        raise SystemExit(1) from exc
    except urllib.error.URLError as exc:
        log.error("Request failed: %s", exc.reason)
        raise SystemExit(1) from exc

    log.info("HTTP %s", status)
    log.info("Response body: %s", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("Response is not JSON")
        raise SystemExit(1) from exc
    if not isinstance(parsed, dict):
        log.error("Response JSON is not an object")
        raise SystemExit(1)
    return parsed


def ensure_success(payload: dict, action: str) -> dict:
    code = payload.get("code")
    message = payload.get("msg") or payload.get("message") or "unknown error"
    if code not in SUCCESS_CODES:
        log.error("%s failed, code=%s, msg=%s", action, code, message)
        print(f"错误: {message} (code={code})")
        raise SystemExit(1)
    log.info("%s succeeded, code=%s, msg=%s", action, code, message)
    return payload


def send_code(phone: str) -> None:
    payload = ensure_success(post_json(SEND_CODE_PATH, {"username": phone}), "Send verification code")
    data = payload.get("data")
    if data:
        log.info("Send-code data: %s", data)


def login(phone: str, verify_code: str) -> str:
    payload = ensure_success(
        post_json(
            LOGIN_PATH,
            {
                "username": phone,
                "verifyCode": verify_code,
                "platform": "2",
                "appType": "",
                "isJoinRenmin": "0",
            },
        ),
        "Login",
    )
    data = payload.get("data")
    token = data.get("token") if isinstance(data, dict) else None
    if isinstance(data, str) and data:
        # 旧接口把 token 直接放在 data 字符串里
        token = data
    if not token:
        log.error("Login response has no token, data=%s", data)
        print("错误: 登录响应里没有 token")
        raise SystemExit(1)
    user_id = data.get("id") if isinstance(data, dict) else None
    nickname = data.get("nickname") if isinstance(data, dict) else None
    log.info("Login user id=%s nickname=%s", user_id, nickname)
    return token


def main() -> None:
    phone = prompt("请输入手机号: ")
    if not PHONE_PATTERN.match(phone):
        log.error("Invalid phone number: %s", phone)
        print("错误: 请输入 11 位手机号")
        raise SystemExit(1)

    log.info("Sending verification code to %s", phone)
    send_code(phone)
    print("验证码已发送，请查看短信。")

    verify_code = prompt("请输入验证码: ")
    if not verify_code:
        log.error("Verification code is empty")
        print("错误: 验证码不能为空")
        raise SystemExit(1)

    log.info("Logging in with phone %s", phone)
    token = login(phone, verify_code)
    print(f"token: {token}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.error("Interrupted by user")
        raise SystemExit(130)
