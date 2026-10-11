"""把登录得到的 token 写到用户配置目录，避免放进仓库。"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

CONFIG_ENV = "HANWANG_CONFIG_DIR"


def config_dir() -> Path:
    override = os.environ.get(CONFIG_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "hanwang-bpm"


def credentials_path() -> Path:
    return config_dir() / "credentials.json"


def load_credentials() -> dict:
    path = credentials_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_credentials(*, token: str, username: str | None = None, user_id: str | None = None, nickname: str | None = None) -> Path:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = load_credentials()
    payload = {
        "token": token,
        "username": username if username is not None else existing.get("username"),
        "userId": user_id if user_id is not None else existing.get("userId"),
        "nickname": nickname if nickname is not None else existing.get("nickname"),
        "savedAt": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def clear_credentials() -> None:
    path = credentials_path()
    if path.is_file():
        path.unlink()
