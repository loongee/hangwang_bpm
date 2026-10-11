#!/bin/sh
# 从登录 shell 的 PATH 里找到 uv，再启动 MCP。日志走服务器自己的 stderr。
set -eu
DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it from https://docs.astral.sh/uv/ then retry." >&2
  exit 1
fi
exec uv run --directory "$DIR" hanwang-bpm
