"""
shared/ifind_client.py
====================================================================
同花顺 iFinD QuantAPI 封装 —— 港股首发上市 / 行情 / 财务 / 宏观

依赖
----
1. 官方 SDK `iFinDPy`（需登录 https://quantapi.10jqka.com.cn 下载安装）
2. 凭证写入项目根目录 `.env`：
       IFIND_USERNAME=...
       IFIND_PASSWORD=...

使用
----
    from shared.ifind_client import (
        login, hk_ipo_calendar, hk_ipo_basics,
        hk_history_prices, hk_financials, edb_query,
    )

    df = hk_ipo_calendar('2024-01-01', '2026-05-07')

注意
----
所有 iFinD 指标 ID（`ths_xxx_xxx`）与数据池名称（`newshare` 等）
请以 QuantAPI 客户端的「数据浏览器」为准；本文件中的常量为常见用法，
首次拉取建议先 print(df) 抽样校验字段名。
====================================================================
"""
from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from functools import wraps
from typing import Iterable, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# 1. .env 加载（避免硬依赖 python-dotenv）
# --------------------------------------------------------------------
def _load_env(env_path: Path | None = None) -> None:
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_env()

# --------------------------------------------------------------------
# 2. SDK 导入（延迟报错，便于纯解析模式 import 本模块）
# --------------------------------------------------------------------
try:
    from iFinDPy import (
        THS_iFinDLogin, THS_iFinDLogout,
        THS_BasicData, THS_HistoryQuotes, THS_RealtimeQuotes,
        THS_DateSerial, THS_DataPool, THS_EDBQuery,
    )
    _SDK_OK = True
    _SDK_ERR: Exception | None = None
except Exception as e:  # ImportError 或 DLL 加载失败
    _SDK_OK = False
    _SDK_ERR = e

def _require_sdk() -> None:
    if not _SDK_OK:
        raise ImportError(
            "iFinDPy 未安装或加载失败。\n"
            "请到 QuantAPI 官网下载客户端: "
            "https://quantapi.10jqka.com.cn/gws/static/static/ds_web/quantapi-web/\n"
            f"原始错误: {_SDK_ERR}"
        )


# --------------------------------------------------------------------
# 3. 登录 / 登出 / 装饰器
# --------------------------------------------------------------------
_LOGGED_IN = False

def login() -> None:
    """读取 .env 中的 IFIND_USERNAME/PASSWORD 登录。重复调用安全。"""
    global _LOGGED_IN
    if _LOGGED_IN:
        return
    _require_sdk()
    user = os.environ.get("IFIND_USERNAME", "").strip()
    pwd = os.environ.get("IFIND_PASSWORD", "").strip()
    if not user or not pwd:
        raise RuntimeError(
            "IFIND_USERNAME / IFIND_PASSWORD 未配置。请填入 .env"
        )
    rc = THS_iFinDLogin(user, pwd)
    # 0 = 成功, -201 = 已登录（不同 SDK 版本码值略有差异，做宽松判定）
    if rc not in (0, -201):
        raise RuntimeError(f"iFinD 登录失败 rc={rc} user={user}")
    _LOGGED_IN = True
    logger.info("iFinD 登录成功 user=%s", user)


def logout() -> None:
    global _LOGGED_IN
    if _LOGGED_IN and _SDK_OK:
        THS_iFinDLogout()
        _LOGGED_IN = False


def _ensure_login(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not _LOGGED_IN:
            login()
        return fn(*a, **kw)
    return wrapper


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
                    logger.warning("iFinD 调用失败 重试 %d/%d: %s",
                                   i + 1, times, e)
                    time.sleep(sleep * (i + 1))
            assert last is not None
            raise last
        return wrapper
    return deco


# --------------------------------------------------------------------
# 4. 响应统一转 DataFrame
# --------------------------------------------------------------------
def _to_df(rsp) -> pd.DataFrame:
    if rsp is None:
        raise RuntimeError("iFinD 接口返回 None")
    if isinstance(rsp, pd.DataFrame):
        return rsp
    if isinstance(rsp, dict):
        err = rsp.get("errorcode", rsp.get("error_code", -1))
        if err not in (0, "0"):
            raise RuntimeError(
                f"iFinD 错误码 {err}: {rsp.get('errmsg') or rsp.get('error_msg')}"
            )
        for key in ("data", "tables", "table"):
            data = rsp.get(key)
            if isinstance(data, pd.DataFrame):
                return data
            if isinstance(data, dict):
                return pd.DataFrame(data)
            if isinstance(data, list) and data:
                return pd.DataFrame(data)
        return pd.DataFrame()  # 空结果
    raise RuntimeError(f"无法解析 iFinD 返回: {type(rsp).__name__}")


def _join_codes(codes) -> str:
    if isinstance(codes, str):
        return codes
    if isinstance(codes, (list, tuple, set)):
        return ",".join(str(c) for c in codes)
    raise TypeError(f"codes 必须是 str / 序列，得到 {type(codes).__name__}")


# ====================================================================
# A. 行情数据
# ====================================================================
@_ensure_login
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
    rsp = THS_HistoryQuotes(_join_codes(codes), indicators, options, begin, end)
    return _to_df(rsp)


@_ensure_login
@_retry()
def realtime_quotes(codes,
                    indicators: str = "latest;preClose;openPrice;highPrice;lowPrice;volume"
                    ) -> pd.DataFrame:
    rsp = THS_RealtimeQuotes(_join_codes(codes), indicators)
    return _to_df(rsp)


# ====================================================================
# B. 基础 / 财务（截面 + 时间序列）
# ====================================================================
@_ensure_login
@_retry()
def basic_data(codes, indicators: str, params: str = "") -> pd.DataFrame:
    """
    截面基础数据 —— 公司资料、估值快照、IPO 信息、单期财务等。
        params 例: '20251231,100,OC' （报告期/单位/合并口径，按指标含义）
    """
    rsp = THS_BasicData(_join_codes(codes), indicators, params)
    return _to_df(rsp)


@_ensure_login
@_retry()
def date_serial(codes, indicators: str,
                options: str = "",
                begin: str = "", end: str = "") -> pd.DataFrame:
    """日序列 —— PE/PB 历史、财务时间序列等。"""
    rsp = THS_DateSerial(_join_codes(codes), indicators, options, begin, end)
    return _to_df(rsp)


# ====================================================================
# C. 数据池（IPO 列表 / 板块成分 / 概念）
# ====================================================================
@_ensure_login
@_retry()
def data_pool(pool_name: str, params: str, indicators: str) -> pd.DataFrame:
    """
    数据池查询。常用 pool_name:
        'newshare' —— 新股 / IPO
        'block'    —— 板块成分
        'index'    —— 指数成分
    具体参数请查 QuantAPI 数据浏览器 → 数据池。
    """
    rsp = THS_DataPool(pool_name, params, indicators)
    return _to_df(rsp)


# ====================================================================
# D. 宏观 EDB
# ====================================================================
@_ensure_login
@_retry()
def edb_query(indicator_id: str, begin: str, end: str) -> pd.DataFrame:
    """
    宏观经济数据库 EDB 查询。
        indicator_id : EDB 编号（如 'M001620244'），多个用分号
        begin/end    : 'YYYY-MM-DD'
    """
    rsp = THS_EDBQuery(indicator_id, begin, end)
    return _to_df(rsp)


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
# 下面为常见示例占位；运行前请自行核对，错误 ID 会返回空表。
HK_MACRO_EDB = {
    # 香港本地
    # "HK_GDP_YOY":     "M00xxxxxx",
    # "HK_CPI_YOY":     "M00xxxxxx",
    # "HK_UNEMP_RATE":  "M00xxxxxx",
    # "HIBOR_3M":       "M00xxxxxx",
    # 内地（与港股投资逻辑相关）
    # "CN_GDP_YOY":     "M00xxxxxx",
    # "CN_CPI_YOY":     "M00xxxxxx",
    # "CN_M2_YOY":      "M00xxxxxx",
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
