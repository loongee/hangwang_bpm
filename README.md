# 汉王血压计云端 MCP

通过 [汉王大健康](https://bpm.hanvon.com/) 读取当前账号自己的血压计和测量数据。服务名是 `hanwang-bpm`，传输方式是 stdio。

它只做读取：列出已绑定设备、测量人、最近读数、历史、详情、趋势、分级和周月报。不提供解绑设备、修改测量人、标记无效或上传蓝牙包。

## 目录

| 路径 | 内容 |
| --- | --- |
| `skill/` | MCP 服务和技能说明，可以单独拷贝使用 |
| `scripts/login.py` | 命令行短信验证码登录，成功后打印 token |
| `docs/汉王大健康_通信协议.md` | 由客户端还原的通信协议 |
| `analysis/` | 协议对照用的反编译摘录 |

`skill/SKILL.md` 是给智能体用的操作说明，接口字段见 `skill/reference.md`。

## 环境

- Python 3.10 及以上
- [uv](https://docs.astral.sh/uv/)

## 启动

在 `skill/` 目录启动服务：

```sh
uv run hanwang-bpm
```

也可以直接执行 `skill/run.sh`。日志写到 stderr。

在 MCP 客户端里把命令指到这个目录，例如：

```json
{
  "mcpServers": {
    "hanwang-bpm": {
      "command": "uv",
      "args": ["run", "--directory", "/绝对路径/hanwang_mcp/skill", "hanwang-bpm"]
    }
  }
}
```

需要预置 token 时，给进程设置环境变量 `HANWANG_TOKEN`。不要把 token 写进仓库。

## 鉴权

读数前先看 `auth_status`。token 按下面顺序取得，已有 token 时不要同时抢两种方式：

1. 环境变量 `HANWANG_TOKEN`。进程启动时它优先于本机已保存的 token。
2. 调用 `set_token`，或用 `login_with_code` / `login_with_password` 登录。登录成功后 token 写入 `~/.config/hanwang-bpm/credentials.json`（权限 600）。可用 `HANWANG_CONFIG_DIR` 改这个目录。
3. 没有 token 时：`send_verify_code` 发短信，再用 `login_with_code`。用户给了密码就用 `login_with_password`。密码只在本地做 SM3 大写摘要后上传。

`code` 为 `401` 时停止读数，重新登录或更新 `HANWANG_TOKEN`。`logout` 会删掉配置文件里的 token；环境变量里的 `HANWANG_TOKEN` 还在时，下次启动仍会用它。

也可以不启动 MCP，直接用脚本登录：

```sh
python3 scripts/login.py
```

## 工具

| 用途 | 工具 |
| --- | --- |
| 登录状态 | `auth_status`、`current_user`、`logout` |
| 登录 | `send_verify_code`、`login_with_code`、`login_with_password`、`set_token` |
| 设备和测量人 | `list_devices`、`list_measurers` |
| 读数 | `latest_readings`、`list_readings`、`reading_detail`、`reading_trend`、`reading_overview`、`reading_calendar` |
| 汇总 | `level_distribution`、`period_report` |

建议顺序：`list_devices` 取 `devSn`，`list_measurers` 确认 `devMeasurer`（`"1"` 或 `"2"`），再读最近一条或历史。请求头只用小写 `token`，不要加 `Authorization`、`appKey` 或 `signature`。

血压单位是 mmHg。`highVal` 是收缩压，`lowVal` 是舒张压。成功码是 `10001`、`0` 和 `10002`；`10002` 表示这段时间没有记录。

默认服务地址是 `https://bpm.hanvon.com`，可用 `HANWANG_BASE_URL` 覆盖。

## 测试

```sh
cd skill
uv run python -m unittest discover -s tests
```
