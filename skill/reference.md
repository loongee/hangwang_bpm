# 汉王血压接口备忘

Base URL：`https://bpm.hanvon.com`。超时按读 60 秒。响应形状：

```json
{ "code": 10001, "msg": "success", "data": {} }
```

| code | 含义 |
| --- | --- |
| `10001` `0` | 成功 |
| `10002` | 成功，无动态数据 |
| `401` | token 失效 |
| `10070` | 不弹出自动刷新提示，不当作读数成功 |

## 登录

| 工具 | 路径 | 要点 |
| --- | --- | --- |
| `send_verify_code` | `/bpmeterapp/api/member/get/verify/code/new` | `{ "username": "手机号" }`，无 token |
| `login_with_code` | `/bpmeterapp/api/member/verify/code/new/login` | `platform` 固定 `"2"`，`appType` 为 `""`，`isJoinRenmin` 为 `"0"` |
| `login_with_password` | `/bpmeterapp/api/member/account/pwd/login` | `password` 是 `SM3(明文).toUpperCase()`，`appType` 为 `"1101091290"` |

`data.token` 是后续凭证。旧验证码接口才把 token 直接放在 `data` 字符串里。

## 读数

| 工具 | 路径 | 关键字段 |
| --- | --- | --- |
| `list_devices` | `/bpmeterapp/api/device/bind/list` | `devSn` `devName` `devType` `macAddr` |
| `list_measurers` | `/bpmeterapp/api/measurer/list` | 请求字段是 `devSN`。返回 `devMeasurer` `nickname` |
| `latest_readings` | `/bpmeterapp/api/v3/device/latest/data/list` | 每个测量人一条 |
| `list_readings` | `/bpmeterapp/api/device/data/list` | 按 `year` `month` `day` 分组，记录在 `list` |
| `reading_detail` | `/bpmeterapp/api/device/detail/data` | 另有 `rangeDesc` `statusDesc`，脉搏是 `hearRate` |
| `reading_trend` | `/bpmeterapp/api/device/trend/datas` | `trendDataList` 是该点明细 |
| `reading_overview` | `/bpmeterapp/api/device/overview/data` | `highAvg/highMax/highMin` 及舒张压、脉搏对应字段 |
| `reading_calendar` | `/bpmeterapp/api/device/calendar/data` | `[{ "measuredTime": "" }]` |
| `level_distribution` | `/bpmeterapp/api/v3/device/time/level/data` | `amount` `levelRate` |
| `period_report` overview | `/bpmeterapp/api/report/get/{week\|month}/overview` | `firstOverview` 等三段综述 |
| `period_report` distribution | `/bpmeterapp/api/v3/report/get/{week\|month}/bp/data/distribute` | 与分级分布相同 |

`dataFlag`：`"2"` 第一页，`"1"` 按 `measuredTime` 继续翻页，`"3"` 日历选中。`dimension` 为 `hour` 且来自日历时，客户端改用 `"1"`。

列表单条里的 `id` 是记录 ID，`measuredId` 是设备侧序号。`isInvalid` 表示已标记无效。
