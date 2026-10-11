---
name: hanwang-bpm
description: >-
  通过汉王大健康云端读取用户自己的血压计和测量数据。支持短信验证码登录、密码登录、在 MCP 环境变量
  HANWANG_TOKEN 中配置 token，以及 set_token。用于查询已绑定血压计、测量人、最近读数、历史、详情、趋势、分级和周月报。
  当用户提到汉王、血压计、血压数据、bpm.hanvon.com、HANWANG_TOKEN，或要登录并查看自己的云端血压记录时使用。
---

# 汉王血压计云端

本目录就是完整技能，可以单独拷贝使用。MCP 服务名是 `hanwang-bpm`，传输用 stdio。它只访问 `https://bpm.hanvon.com/` 上当前账号自己的血压数据。所有业务请求都是 `POST`，JSON 里值为 null 的字段不发送。鉴权头名是小写 `token`，不要加 `Authorization`、`appKey`、`randNumber`、`timestamp` 或 `signature`。

在任意 MCP 客户端里把工作目录指到本目录后启动：

```text
uv run hanwang-bpm
```

也可以直接执行本目录的 `run.sh`。需要预置 token 时，给这个进程设置环境变量 `HANWANG_TOKEN`，不要把 token 写进技能目录。

协议细节见 [reference.md](reference.md)。

## 先确认鉴权

调用读数工具前先看 `auth_status`。

已有 token 时，任选一种方式，不要两种同时抢：

1. 启动 MCP 时设置环境变量 `HANWANG_TOKEN`。进程启动时它优先于本机已保存的 token。
2. 调用 `set_token`。token 写入 `~/.config/hanwang-bpm/credentials.json`（权限 600），并立刻用于当前进程。
3. 没有 token 时走登录：`send_verify_code`，向用户要短信验证码，再 `login_with_code`。用户给了密码就用 `login_with_password`。密码只在本地做 SM3 大写摘要后上传。登录成功后的 token 同样写入上面的配置文件。

`code` 为 `401` 时停止读数，告诉用户 token 失效，并重新登录或更新 `HANWANG_TOKEN`。

`logout` 会删掉配置文件里的 token。环境变量里的 `HANWANG_TOKEN` 还在时，下次启动仍会用它。

## 读数顺序

1. `list_devices`，从返回里取 `devSn`。多台设备时先问用户要看哪一台。
2. `list_measurers`，确认 `devMeasurer`。`"1"` 是测量人一，`"2"` 是测量人二。请求体字段名是 `devSN`，工具已经按这个名字发送。
3. `latest_readings` 看每人最近一条。
4. 需要历史时用 `list_readings`。第一页 `data_flag` 用 `"2"`；沿锚点继续翻页用 `"1"` 并传入上页的 `measuredTime`；日历选中用 `"3"`。`page_size` 用 50。
5. 单条用 `reading_detail`，曲线用 `reading_trend`，汇总用 `reading_overview`，有记录的日期用 `reading_calendar`。
6. 分级占比用 `level_distribution`。周报或月报用 `period_report`：`section=overview` 是文字综述，`section=distribution` 是分级分布。

时间格式：日和周用 `yyyy-MM-dd`，小时用 `yyyy-MM-dd HH:mm:ss`，月起始按界面拼成 `yyyy-MM/01`。趋势的日、周、月区间也用 `yyyy-MM-dd`。

## 怎么向用户说明结果

血压单位是 mmHg。`highVal` 是收缩压，`lowVal` 是舒张压，列表里的脉搏是 `heartRate`，详情里的脉搏字段是 `hearRate`。

工具会额外给出 `statusLabel`。分级按设备规则理解：`3` 三级，`2` 二级，`1` 一级，`11` 正常高值，`10` 正常，`9` 偏低，`-1` 按正常说明。

成功码是 `10001`、`0` 和 `10002`。`10002` 表示没有动态数据，把结果说成这段时间没有记录。

不要主动解绑设备、改测量人、标记无效或上传蓝牙包。这个 MCP 没有这些工具。
