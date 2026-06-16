"""
ifind_core —— iFinD（同花顺 iFinDPy）共享底层
================================================

把 market-dashboard/ifind.py（dict 单值, get_stock_analysis 用）与
DCF agent/shared/ifind_client.py（pandas DataFrame, 建模用）两套客户端
**重复的底层样板**抽到这里：SDK 延迟导入 + 登录/会话缓存 + .env 加载 +
代码/市场归一化 + 单值解析(THS_BD) + DataFrame 解析。

各客户端只保留自己的高层 API 与返回类型，登录/导入/解析全部委托本模块。

凭据
----
IFIND_USERNAME / IFIND_PASSWORD（兼容旧名 IFIND_USER / IFIND_PASS）。

GBK 路径坑（重要）
------------------
iFinDPy 常装在含中文的路径下；进程**不能以 -X utf8 / 设 PYTHONUTF8 启动**，
否则 iFinDPy 导入时按 UTF-8 读 GBK 路径文件会 UnicodeDecodeError。
MCP server 以普通 `python server.py`（locale=GBK）启动，导入正常。
本模块对 iFinDPy 做**延迟导入**（放在 ensure_login 内 try/except），
导入失败不影响调用方模块的 import。

跨仓库分发
----------
本文件为权威源（market-dashboard/ifind_core.py）；DCF agent/shared/ifind_core.py
为 vendored 副本，二者须保持一致（改动后手动同步）。
"""

from __future__ import annotations

import os
from typing import Any, Optional


class IFindNotConfigured(Exception):
    """未配置 IFIND_USERNAME/IFIND_PASSWORD。"""


class IFindError(Exception):
    """登录或查询失败（含 SDK 导入失败）。"""


# --------------------------------------------------------------------------- #
# 凭据
# --------------------------------------------------------------------------- #
def user() -> str:
    return (os.environ.get("IFIND_USERNAME") or os.environ.get("IFIND_USER") or "").strip()


def pwd() -> str:
    return (os.environ.get("IFIND_PASSWORD") or os.environ.get("IFIND_PASS") or "").strip()


def is_configured() -> bool:
    return bool(user() and pwd())


def load_env(*paths: str) -> None:
    """把若干 .env 文件加载进 os.environ（不覆盖已存在的键）。
    market-dashboard 由 server 统一加载 env，可不调用本函数；
    ifind_client 可用它加载项目根 .env。"""
    for p in paths:
        if not p or not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8").read().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


# --------------------------------------------------------------------------- #
# 登录 / 会话（进程内缓存，延迟导入 SDK）
# --------------------------------------------------------------------------- #
_THS = None                      # iFinDPy 模块句柄
_logged_in = False
_login_err: Optional[str] = None


def ensure_login():
    """惰性登录，进程内缓存。成功返回 iFinDPy 模块；
    未配置抛 IFindNotConfigured；导入/登录失败抛 IFindError。

    登录成功码取并集 {0,'0',None,-201}：
      - 0/'0'/None：常规成功（ifind.py 口径）；
      - -201：部分 SDK 版本「已登录」返回码（ifind_client.py 口径）。
    """
    global _THS, _logged_in, _login_err
    if _logged_in:
        return _THS
    if not is_configured():
        raise IFindNotConfigured()
    if _login_err:                # 上次登录已失败，不反复重试
        raise IFindError(_login_err)
    try:
        import iFinDPy as THS     # noqa: N814  延迟导入
    except Exception as e:        # noqa: BLE001  导入/DLL 失败
        _login_err = f"iFinDPy 导入失败：{e}（确认未以 -X utf8 启动）"
        raise IFindError(_login_err)
    ret = THS.THS_iFinDLogin(user(), pwd())
    code = ret.get("errorcode") if isinstance(ret, dict) else ret
    if code not in (0, "0", None, -201):
        msg = ret.get("errmsg") if isinstance(ret, dict) else ret
        _login_err = f"THS_iFinDLogin 失败 code={code} msg={msg}"
        raise IFindError(_login_err)
    _THS = THS
    _logged_in = True
    return THS


def logout() -> None:
    global _logged_in
    if _logged_in and _THS is not None:
        try:
            _THS.THS_iFinDLogout()
        except Exception:  # noqa: BLE001
            pass
        _logged_in = False


# --------------------------------------------------------------------------- #
# 代码格式归一化：NVDA → [NVDA.O, NVDA.N]；0700.HK / 600519.SH 原样
# --------------------------------------------------------------------------- #
def candidates(symbol: str) -> list[str]:
    s = symbol.upper().strip()
    if any(s.endswith(suf) for suf in (".HK", ".SH", ".SZ", ".O", ".N", ".OQ")):
        return [s]
    if s.endswith(".US"):
        s = s[:-3]
    if "." in s:
        return [s]
    return [s + ".O", s + ".N"]  # 纯美股：先纳斯达克 .O 再纽交所 .N


def market_of(code: str) -> str:
    if code.endswith(".HK"):
        return "HK"
    if code.endswith((".SH", ".SZ")):
        return "A"
    return "US"  # .O/.N/.OQ


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
def num(x: Any) -> Optional[float]:
    try:
        if x in (None, "", "None"):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def bd_value(THS, code: str, indicator: str, params: str = "") -> Optional[Any]:
    """THS_BD 单值查询（防御式解析）。THS_BD 返回 THSData 对象：
    .errorcode==0，.data 为 pandas DataFrame（列含 thscode 与指标列）。
    取第一行的指标列值；取不到返回 None。"""
    try:
        r = THS.THS_BD(code, indicator, params)
    except Exception:  # noqa: BLE001
        return None
    ec = getattr(r, "errorcode", None)
    if ec is None and isinstance(r, dict):
        ec = r.get("errorcode")
    if ec not in (0, "0"):
        return None
    data = getattr(r, "data", None)
    if data is None and isinstance(r, dict):
        data = r.get("data")
    try:
        if hasattr(data, "columns") and len(data) > 0:
            cols = list(data.columns)
            if indicator in cols:
                return data[indicator].iloc[0]
            return data.iloc[0, -1]  # 末列通常是指标值（首列为 thscode）
    except Exception:  # noqa: BLE001
        pass
    return None


def to_df(rsp):
    """iFinD 接口返回 → pandas DataFrame（兼容 DataFrame / dict[tables|data|table]）。
    错误码非 0 抛 IFindError。pandas 延迟导入（dict 单值客户端不必装 pandas）。"""
    import pandas as pd  # 延迟导入
    if rsp is None:
        raise IFindError("iFinD 接口返回 None")
    if isinstance(rsp, pd.DataFrame):
        return rsp
    if isinstance(rsp, dict):
        err = rsp.get("errorcode", rsp.get("error_code", -1))
        if err not in (0, "0"):
            raise IFindError(
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
    raise IFindError(f"无法解析 iFinD 返回: {type(rsp).__name__}")


__all__ = [
    "IFindNotConfigured", "IFindError",
    "user", "pwd", "is_configured", "load_env",
    "ensure_login", "logout",
    "candidates", "market_of",
    "num", "bd_value", "to_df",
]
