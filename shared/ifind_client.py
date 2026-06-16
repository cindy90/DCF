"""
shared/ifind_client.py
====================================================================
同花顺 iFinD QuantAPI 封装 —— 港股首发上市 / 行情 / 财务 / 宏观

底层（SDK 延迟导入 / 登录会话缓存 / .env 加载 / 返回→DataFrame 解析）已抽到
共享模块 `ifind_core`（与 market-dashboard/ifind.py 复用同一份，去重）；本文件
只保留高层查询 API 与港股便捷封装。

依赖
----
1. 官方 SDK `iFinDPy`（需登录 https://quantapi.10jqka.com.cn 下载安装）
2. 凭证写入项目根目录 `.env`：IFIND_USERNAME=... / IFIND_PASSWORD=...

使用
----
    from shared.ifind_client import (
        login, hk_ipo_calendar, hk_ipo_basics,
        hk_history_prices, hk_financials, edb_query,
    )
    df = hk_ipo_calendar('2024-01-01', '2026-05-07')

注意
----
所有 iFinD 指标 ID（`ths_xxx_xxx`）与数据池名称（`newshare` 等）请以 QuantAPI
「数据浏览器」为准；首次拉取建议先 print(df) 抽样校验字段名。
公共错误契约：登录/查询失败抛 RuntimeError（与历史一致）。
====================================================================
"""
from __future__ import annotations

import time
import logging
from pathlib import Path
from functools import wraps
from typing import Iterable

import pandas as pd

# 共享底层（与 market-dashboard/ifind.py 复用同一份 ifind_core）
from .ifind_core import (
    IFindNotConfigured,
    IFindError,
    is_configured,           # noqa: F401  便捷重导出
    load_env,
    ensure_login as _core_login,
    logout as _core_logout,
    to_df as _core_to_df,
)

logger = logging.getLogger(__name__)

# 加载项目根 .env（不覆盖已有环境变量）
load_env(str(Path(__file__).resolve().parent.parent / ".env"))


# --------------------------------------------------------------------
# 登录 / 登出（保持旧契约：失败抛 RuntimeError）
# --------------------------------------------------------------------
def login() -> None:
    """读取 .env 中 IFIND_USERNAME/PASSWORD 登录。重复调用安全。"""
    try:
        _core_login()
        logger.info("iFinD 登录成功")
    except IFindNotConfigured:
        raise RuntimeError("IFIND_USERNAME / IFIND_PASSWORD 未配置。请填入 .env")
    except IFindError as e:
        raise RuntimeError(str(e))


def logout() -> None:
    _core_logout()


def _ths():
    """返回已登录的 iFinDPy 模块；失败抛 RuntimeError（统一契约）。"""
    try:
        return _core_login()
    except IFindNotConfigured:
        raise RuntimeError("IFIND_USERNAME / IFIND_PASSWORD 未配置。请填入 .env")
    except IFindError as e:
        raise RuntimeError(str(e))


def _df(rsp) -> pd.DataFrame:
    """ifind_core.to_df 的薄封装：把 IFindError 翻译成 RuntimeError（保持旧契约）。"""
    try:
        return _core_to_df(rsp)
    except IFindError as e:
        raise RuntimeError(str(e))


def _retry(times: int = 3, sleep: float = 1.0):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            last: Exception | None = None
            for i in range(times):
                try:
                    return fn(*a, **kw)
                except Exception as e:
                    last = e
                    logger.warning("iFinD 调用失败 重试 %d/%d: %s", i + 1, times, e)
                    time.sleep(sleep * (i + 1))
            assert last is not None
            raise last
        return wrapper
    return deco


def _join_codes(codes) -> str:
    if isinstance(codes, str):
        return codes
    if isinstance(codes, (list, tuple, set)):
        return ",".join(str(c) for c in codes)
    raise TypeError(f"codes 必须是 str / 序列，得到 {type(codes).__name__}")


# ====================================================================
# A. 行情数据
# ====================================================================
@_retry()
def history_quotes(codes, indicators: str,
                   begin: str, end: str,
                   options: str = "") -> pd.DataFrame:
    """
    历史行情。
        codes      : 'XXXXX.HK' 或列表（如 ['00700.HK', '09988.HK']）
        indicators : 'open;high;low;close;volume;amount;turnoverRatio;changeRatio'
        begin/end  : 'YYYY-MM-DD'
        options    : iFinD 复权/币种串，例：
                     'Interval:D,CPS:00102,baseDate:1900-01-01,Currency:HKD' (前复权)
    """
    THS = _ths()
    rsp = THS.THS_HistoryQuotes(_join_codes(codes), indicators, options, begin, end)
    return _df(rsp)


@_retry()
def realtime_quotes(codes,
                    indicators: str = "latest;preClose;openPrice;highPrice;lowPrice;volume"
                    ) -> pd.DataFrame:
    THS = _ths()
    rsp = THS.THS_RealtimeQuotes(_join_codes(codes), indicators)
    return _df(rsp)


# ====================================================================
# B. 基础 / 财务（截面 + 时间序列）
# ====================================================================
@_retry()
def basic_data(codes, indicators: str, params: str = "") -> pd.DataFrame:
    """
    截面基础数据 —— 公司资料、估值快照、IPO 信息、单期财务等。
        params 例: '20251231,100,OC' （报告期/单位/合并口径，按指标含义）
    """
    THS = _ths()
    rsp = THS.THS_BasicData(_join_codes(codes), indicators, params)
    return _df(rsp)


@_retry()
def date_serial(codes, indicators: str,
                options: str = "",
                begin: str = "", end: str = "") -> pd.DataFrame:
    """日序列 —— PE/PB 历史、财务时间序列等。"""
    THS = _ths()
    rsp = THS.THS_DateSerial(_join_codes(codes), indicators, options, begin, end)
    return _df(rsp)


# ====================================================================
# C. 数据池（IPO 列表 / 板块成分 / 概念）
# ====================================================================
@_retry()
def data_pool(pool_name: str, params: str, indicators: str) -> pd.DataFrame:
    """
    数据池查询。常用 pool_name:
        'newshare' —— 新股 / IPO
        'block'    —— 板块成分
        'index'    —— 指数成分
    具体参数请查 QuantAPI 数据浏览器 → 数据池。
    """
    THS = _ths()
    rsp = THS.THS_DataPool(pool_name, params, indicators)
    return _df(rsp)


# ====================================================================
# D. 宏观 EDB
# ====================================================================
@_retry()
def edb_query(indicator_id: str, begin: str, end: str) -> pd.DataFrame:
    """
    宏观经济数据库 EDB 查询。
        indicator_id : EDB 编号（如 'M001620244'），多个用分号
        begin/end    : 'YYYY-MM-DD'
    """
    THS = _ths()
    rsp = THS.THS_EDBQuery(indicator_id, begin, end)
    return _df(rsp)


# ====================================================================
# 港股专用便捷封装
# ====================================================================
HK_SUFFIX = ".HK"


def hk_ipo_calendar(begin: str, end: str) -> pd.DataFrame:
    """
    港股首发上市日历 —— 拉指定区间内已上市新股清单及关键发行信息。

    返回字段（视 SDK 版本可能调整，建议首次 print 验证）:
        thscode | 简称 | 上市日期 | 发行价 | 发行 PE | 发行后总股本 | 募资额
    """
    indicators = ";".join([
        "thscode",
        "ths_stock_short_name_stock",
        "ths_ipo_date_stock",
        "ths_ipo_price_hks",
        "ths_ipo_pe_hks",
        "ths_total_share_after_ipo_hks",
        "ths_ipo_amt_hks",
    ])
    # 'AHK' = 全部港股新股；如需细分主板/创业板请查数据浏览器
    return data_pool("newshare", f"AHK;{begin};{end}", indicators)


def hk_ipo_basics(codes) -> pd.DataFrame:
    """单只 / 多只港股 IPO 关键信息快照（保荐人、承销商、认购倍数等）"""
    indicators = ";".join([
        "ths_stock_short_name_stock",
        "ths_ipo_date_stock",
        "ths_ipo_price_hks",
        "ths_ipo_pe_hks",
        "ths_subscript_times_hks",       # 公开发售认购倍数
        "ths_intl_subscript_times_hks",  # 国际配售认购倍数
        "ths_ipo_amt_hks",               # 募资总额
        "ths_listing_recommend_hks",     # 保荐人
        "ths_underwriter_hks",           # 承销商 / 账簿管理人
        "ths_first_day_close_chg_hks",   # 首日涨跌幅
    ])
    return basic_data(codes, indicators)


def hk_history_prices(codes, begin: str, end: str,
                      adjust: str = "F",
                      currency: str = "HKD") -> pd.DataFrame:
    """
    港股历史行情。
        adjust   : 'N' 不复权 / 'F' 前复权 / 'B' 后复权
        currency : 'HKD' / 'CNY' / 'USD'
    """
    cps = {"N": "00100", "F": "00102", "B": "00103"}[adjust]
    options = (f"Interval:D,CPS:{cps},baseDate:1900-01-01,"
               f"Currency:{currency}")
    indicators = "open;high;low;close;volume;amount;turnoverRatio;changeRatio"
    return history_quotes(codes, indicators, begin, end, options)


def hk_financials(codes, report_date: str,
                  consolidate: str = "OC") -> pd.DataFrame:
    """
    港股财务三表关键科目（单期截面）。
        report_date : 'YYYYMMDD'
        consolidate : 'OC' 合并 / 'PC' 母公司
    多期请改用 date_serial / 循环调用。
    """
    indicators = ";".join([
        "ths_oper_total_rev",          # 营业总收入
        "ths_oper_rev",                # 营业收入
        "ths_oper_cost",
        "ths_gross_profit_ttm",
        "ths_op_profit",
        "ths_total_profit",
        "ths_net_profit",
        "ths_np_atoopc",               # 归母净利
        "ths_total_assets",
        "ths_total_liab",
        "ths_total_se",                # 股东权益合计
        "ths_se_atoopc",
        "ths_cash_eqv_end_period",
        "ths_oper_cash_flow",          # 经营活动现金流量净额
        "ths_invest_cash_flow",
        "ths_finan_cash_flow",
        "ths_capex",
    ])
    return basic_data(codes, indicators, f"{report_date},100,{consolidate}")


def hk_valuation_snapshot(codes, date: str = "") -> pd.DataFrame:
    """估值快照（市值、PE、PB、EV/EBITDA、股息率）"""
    indicators = ";".join([
        "ths_market_value",
        "ths_pe_ttm",
        "ths_pb_lf",
        "ths_ps_ttm",
        "ths_ev_ebitda",
        "ths_dividend_yield",
    ])
    return basic_data(codes, indicators, date)


# ====================================================================
# 宏观便捷封装：返回常用 EDB ID 字典
# ====================================================================
# ⚠️ EDB ID 因数据库更新会变动，请以 QuantAPI「EDB 浏览器」实际为准。
HK_MACRO_EDB = {
    # 香港本地 / 内地（占位；运行前请自行核对，错误 ID 会返回空表）
}

# 走 history_quotes 的宏观/外汇代码
HK_MACRO_QUOTE = {
    "HSI":     "HSI.HI",       # 恒生指数
    "HSCEI":   "HSCEI.HI",     # 国企指数
    "HSTECH":  "HSTECH.HI",    # 恒生科技
    "USDHKD":  "USDHKD.FX",
    "USDCNH":  "USDCNH.FX",
}


def hk_macro_quote_history(begin: str, end: str,
                           tickers: Iterable[str] | None = None) -> pd.DataFrame:
    """拉常用恒指家族 + 美元港币 / 美元离岸人民币历史。"""
    if tickers is None:
        tickers = list(HK_MACRO_QUOTE.values())
    return history_quotes(list(tickers), "close;volume;changeRatio",
                          begin, end, "Interval:D,Currency:original")


# ====================================================================
__all__ = [
    "login", "logout",
    # 通用
    "history_quotes", "realtime_quotes", "basic_data", "date_serial",
    "data_pool", "edb_query",
    # 港股便捷
    "hk_ipo_calendar", "hk_ipo_basics", "hk_history_prices",
    "hk_financials", "hk_valuation_snapshot",
    # 宏观
    "hk_macro_quote_history", "HK_MACRO_EDB", "HK_MACRO_QUOTE",
    "HK_SUFFIX",
    # 自 ifind_core 重导出
    "is_configured", "IFindNotConfigured", "IFindError",
]


# ====================================================================
# 烟雾测试: python -m shared.ifind_client
# ====================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    login()
    print("=== 港股 IPO 日历 (近 30 天样例) ===")
    from datetime import date, timedelta
    today = date.today()
    df = hk_ipo_calendar((today - timedelta(days=30)).isoformat(),
                         today.isoformat())
    print(df.head(10))
    logout()
