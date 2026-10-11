"""汉王大健康血压云端 MCP。stdio 传输，日志只写 stderr。"""

import logging
import re
import sys
from typing import Annotated, Literal

from mcp.server import MCPServer
from pydantic import Field

from hanwang_bpm.session import Session

log = logging.getLogger("hanwang.bpm")
PHONE_PATTERN = re.compile(r"^1\d{10}$")

mcp = MCPServer(
    "hanwang-bpm",
    instructions=(
        "读取当前用户自己的汉王血压计云端数据。"
        "鉴权可以用 HANWANG_TOKEN，或 send_verify_code 后 login_with_code，或 login_with_password，或 set_token。"
        "先 list_devices 拿到 devSn，再 list_measurers 确认 devMeasurer（1 或 2），然后读取最近记录、历史、详情和趋势。"
        "请求不要添加 appKey、signature 或 Authorization 头。"
    ),
)

_session: Session | None = None


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def _check_phone(username: str) -> str:
    phone = username.strip()
    if not PHONE_PATTERN.match(phone):
        raise ValueError("请输入 11 位手机号")
    return phone


def _check_measurer(dev_measurer: str) -> str:
    if dev_measurer not in {"1", "2"}:
        raise ValueError('dev_measurer 只能是 "1" 或 "2"')
    return dev_measurer


@mcp.tool()
def send_verify_code(
    username: Annotated[str, Field(description="登录手机号，11 位")],
) -> dict:
    """向手机号发送汉王大健康登录验证码。这一步不需要 token。"""
    phone = _check_phone(username)
    log.info("Tool send_verify_code")
    return get_session().send_verify_code(phone)


@mcp.tool()
def login_with_code(
    username: Annotated[str, Field(description="登录手机号，11 位")],
    verify_code: Annotated[str, Field(description="短信验证码")],
) -> dict:
    """用短信验证码登录，返回 token 并保存到本机配置目录，供后续查询使用。"""
    phone = _check_phone(username)
    code = verify_code.strip()
    if not code:
        raise ValueError("验证码不能为空")
    log.info("Tool login_with_code")
    return get_session().login_with_code(phone, code)


@mcp.tool()
def login_with_password(
    username: Annotated[str, Field(description="登录手机号，11 位")],
    password: Annotated[str, Field(description="账号明文密码。发送前会在本地做 SM3 并转成大写，不会明文上传")],
) -> dict:
    """用密码登录。密码按客户端规则做 SM3 大写摘要后再提交，成功后保存 token。"""
    phone = _check_phone(username)
    if not password:
        raise ValueError("密码不能为空")
    log.info("Tool login_with_password")
    return get_session().login_with_password(phone, password)


@mcp.tool()
def set_token(
    token: Annotated[str, Field(description="已经拿到的登录 token。会写入本机配置并立即用于后续请求")],
) -> dict:
    """直接配置 token，不走登录接口。适合把已有 token 交给 MCP。"""
    log.info("Tool set_token")
    return get_session().set_token(token)


@mcp.tool()
def auth_status() -> dict:
    """查看当前是否已有 token。只返回来源、手机号和 token 末四位，不返回完整 token。"""
    log.info("Tool auth_status")
    return get_session().status()


@mcp.tool()
def current_user() -> dict:
    """读取当前登录用户资料。响应里的 token 会被去掉，只保留末四位。"""
    log.info("Tool current_user")
    return get_session().current_user()


@mcp.tool()
def logout() -> dict:
    """退出登录并删除本机保存的 token。若 MCP 环境变量仍配置了 HANWANG_TOKEN，下次启动还会用它。"""
    log.info("Tool logout")
    return get_session().logout()


@mcp.tool()
def list_devices() -> dict:
    """列出当前账号已绑定的血压计，包含 devSn、devName、devType 和 macAddr。"""
    log.info("Tool list_devices")
    return get_session().list_devices()


@mcp.tool()
def list_measurers(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
) -> dict:
    """列出该血压计的测量人。后续读数使用返回的 devMeasurer，取值为 1 或 2。"""
    if not dev_sn.strip():
        raise ValueError("dev_sn 不能为空")
    log.info("Tool list_measurers")
    return get_session().list_measurers(dev_sn.strip())


@mcp.tool()
def latest_readings(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
) -> dict:
    """读取每个测量人最近一条云端血压，包含收缩压 highVal、舒张压 lowVal、脉搏 heartRate、时间和分级 status。"""
    if not dev_sn.strip():
        raise ValueError("dev_sn 不能为空")
    log.info("Tool latest_readings")
    return get_session().latest_readings(dev_sn.strip())


@mcp.tool()
def list_readings(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
    dimension: Annotated[Literal["hour", "day", "week", "month"], Field(description="时间粒度")] = "day",
    measured_time: Annotated[str | None, Field(description="翻页锚点或日历时间。日/周为 yyyy-MM-dd，小时为 yyyy-MM-dd HH:mm:ss")] = None,
    page_size: Annotated[int, Field(description="每页条数，客户端固定 50")] = 50,
    data_flag: Annotated[Literal["1", "2", "3"], Field(description="2 首页第一页，1 按锚点继续翻页，3 日历选中")] = "2",
    level_status: Annotated[str | None, Field(description="按分级筛选。不筛选时留空")] = None,
) -> dict:
    """按测量人分页读取历史血压。结果按年月日分组，单条记录在 list 里。"""
    if not dev_sn.strip():
        raise ValueError("dev_sn 不能为空")
    if not 1 <= page_size <= 50:
        raise ValueError("page_size 必须在 1 到 50 之间")
    log.info("Tool list_readings dimension=%s data_flag=%s", dimension, data_flag)
    return get_session().list_readings(
        dev_sn.strip(),
        _check_measurer(dev_measurer),
        dimension,
        measured_time,
        page_size,
        data_flag,
        level_status,
    )


@mcp.tool()
def reading_detail(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    measured_time: Annotated[str, Field(description="测量时间，格式 yyyy-MM-dd HH:mm:ss")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
) -> dict:
    """读取单条血压详情。详情里的脉搏字段名是 hearRate。"""
    if not dev_sn.strip() or not measured_time.strip():
        raise ValueError("dev_sn 和 measured_time 不能为空")
    log.info("Tool reading_detail")
    return get_session().reading_detail(dev_sn.strip(), _check_measurer(dev_measurer), measured_time.strip())


@mcp.tool()
def reading_trend(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    begin_date: Annotated[str, Field(description="开始日期 yyyy-MM-dd")],
    end_date: Annotated[str, Field(description="结束日期 yyyy-MM-dd")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
    dimension: Annotated[Literal["hour", "day", "week", "month"], Field(description="趋势粒度")] = "day",
) -> dict:
    """读取一段时间的血压趋势点，包含收缩压、舒张压、脉搏和 trendDataList。"""
    if not dev_sn.strip() or not begin_date.strip() or not end_date.strip():
        raise ValueError("dev_sn、begin_date、end_date 不能为空")
    log.info("Tool reading_trend dimension=%s", dimension)
    return get_session().reading_trend(
        dev_sn.strip(),
        _check_measurer(dev_measurer),
        dimension,
        begin_date.strip(),
        end_date.strip(),
    )


@mcp.tool()
def reading_overview(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
    measured_time: Annotated[str | None, Field(description="统计锚定时间，可留空")] = None,
) -> dict:
    """读取血压概览：收缩压、舒张压、脉搏的平均、最高和最低值。"""
    if not dev_sn.strip():
        raise ValueError("dev_sn 不能为空")
    log.info("Tool reading_overview")
    return get_session().reading_overview(dev_sn.strip(), _check_measurer(dev_measurer), measured_time)


@mcp.tool()
def reading_calendar(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
) -> dict:
    """列出该测量人有血压记录的日期。"""
    if not dev_sn.strip():
        raise ValueError("dev_sn 不能为空")
    log.info("Tool reading_calendar")
    return get_session().reading_calendar(dev_sn.strip(), _check_measurer(dev_measurer))


@mcp.tool()
def level_distribution(
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    begin_date: Annotated[str, Field(description="开始日期 yyyy-MM-dd")],
    end_date: Annotated[str, Field(description="结束日期 yyyy-MM-dd")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
) -> dict:
    """读取一段时间内的血压分级分布，包含数量 amount 和占比 levelRate。"""
    if not dev_sn.strip() or not begin_date.strip() or not end_date.strip():
        raise ValueError("dev_sn、begin_date、end_date 不能为空")
    log.info("Tool level_distribution")
    return get_session().level_distribution(
        dev_sn.strip(),
        _check_measurer(dev_measurer),
        begin_date.strip(),
        end_date.strip(),
    )


@mcp.tool()
def period_report(
    period: Annotated[Literal["week", "month"], Field(description="周报 week 或月报 month")],
    begin_date: Annotated[str, Field(description="开始日期 yyyy-MM-dd")],
    end_date: Annotated[str, Field(description="结束日期 yyyy-MM-dd")],
    dev_sn: Annotated[str, Field(description="血压计序列号 devSn")],
    dev_measurer: Annotated[Literal["1", "2"], Field(description="测量人。1 为测量人一，2 为测量人二")] = "1",
    section: Annotated[Literal["overview", "distribution"], Field(description="overview 为文字综述，distribution 为分级分布")] = "overview",
) -> dict:
    """读取周报或月报。overview 返回三段综述和均值，distribution 返回分级占比。"""
    if not dev_sn.strip() or not begin_date.strip() or not end_date.strip():
        raise ValueError("dev_sn、begin_date、end_date 不能为空")
    log.info("Tool period_report period=%s section=%s", period, section)
    return get_session().period_report(
        period,
        section,
        dev_sn.strip(),
        _check_measurer(dev_measurer),
        begin_date.strip(),
        end_date.strip(),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    log.info("Hanwang BPM MCP server starting")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
