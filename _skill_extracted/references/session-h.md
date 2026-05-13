# SESSION H — Comps Tab (可比公司估值分析)

**Prerequisite:** `PHASE_DONE: SESSION_G` in `_State` tab.
**Output:** Adds `Comps` sheet to the existing Excel model.
**Estimated time:** 15–20 min.

---

## PRE-FLIGHT CHECKLIST

```
□ _State: PHASE_DONE = SESSION_G
□ DCF tab complete: EV Gordon / EV Exit / Net Debt / Equity values populated
□ KEY_CELLS_IS, KEY_CELLS_BS populated in _State
□ project_config.yaml exists in the project directory
□ _comps_data.json exists (tushare data pre-fetched)
□ "Comps" tab does NOT already exist
```

---

## ██ SHARED MODULE — MANDATORY IMPORT ██

**DO NOT define inline style/helper functions.** Import everything from `shared/`:

```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # DCF agent/

from shared import (
    fill, fnt, fnt_yahei, aln, bdr,
    C_BLK, C_COLHDR, C_CORE, C_REF, C_STAT, C_SUBJ, C_VAL, C_BRIDGE,
    C_GRAY, C_WHITE, C_NOTE,
    FMT_TEXT, FMT_N0, FMT_N1, FMT_N2, FMT_PCT,
    write_blk_hdr, write_col_hdrs, write_cell,
    nv, stat, exch, load_json, filter_positive,
    read_state, write_state_key, read_key_cells, get_key_row,
)
from shared.config_loader import load_project_config, ProjectConfig
```

**If a helper function does not exist in `shared/`, add it to the appropriate `shared/*.py` file** — never define it locally in the build script.

---

## Step 1 — Load Config and Data

```python
cfg = ProjectConfig.from_yaml('project_config.yaml')
MODEL_PATH = cfg.model_path
DATA_PATH  = cfg.comps_data_path

with open(DATA_PATH, encoding='utf-8') as f:
    records_all = json.load(f)

wb = load_workbook(MODEL_PATH)
```

All project-specific parameters (core_peers, excluded_tickers, PE filter ranges, anchor row numbers, etc.) come from `project_config.yaml` — **never hardcode company-specific values in the build script**.

---

## Step 2 — tushare Data Collection

### 2.1 Peer Selection Methodology

From `project_config.yaml`:
- `comps.industry_index` — SW2021 L3 index code
- `comps.core_peers` — manually selected core comparable tickers
- `comps.excluded_tickers` — tickers to exclude (ST, extreme outliers, etc.)

```python
import tushare as ts

pro = ts.pro_api(TUSHARE_TOKEN)

# 1. Latest trade date
cal = pro.trade_cal(exchange='SSE', is_open='1', ...)
latest_trade_date = cal.sort_values('cal_date', ascending=False).iloc[0]['cal_date']

# 2. Index members (SW2021 L3)
members = pro.index_member(index_code=cfg._data['comps']['industry_index'])
# ⚠️ Note: column name is 'con_code' not 'ts_code'

# 3. For each ticker: daily_basic + income + balancesheet + fina_indicator
# Sleep 0.18s between calls to avoid 429 rate limits
```

### 2.2 Data Schema (`_comps_data.json` per record)

```json
{
  "ts_code": "300065.SZ",
  "name": "海兰信",
  "industry": "船舶",
  "total_mv_yi": 159.89,
  "pe_ttm": 422.75,
  "pb": 9.09,
  "ps_ttm": 22.52,
  "revenue_yi": 3.84,
  "ni_yi": 0.08,
  "roe": 0.5,
  "gpm": 33.9,
  "total_assets_yi": 9.12,
  "equity_yi": 1.76,
  "data_date": "20260403",
  "fin_period": "20241231"
}
```

---

## Step 3 — Build Comps Sheet (5 Blocks)

### Block 1: 可比公司基本信息 + 统计行

- One row per peer (core peers highlighted, reference peers plain)
- 4 statistics rows: Median / Mean / 25th / 75th percentile
- Columns: 名称 / 类别(★核心/□参考) / 市值(亿) / PE TTM / PB / PS TTM / Revenue(亿) / NI(亿) / ROE / GPM / Exchange

### Block 2: 交易乘数汇总

- PE / PB / PS per company with validity flags ("有效" / "N/A-亏损" / "N/A-极值")
- Filter rules from `project_config.yaml`: `comps.pe_filter.max`, `comps.peg_filter.max`
- Statistics: Median / Mean (after filtering)

### Block 3: 对标锚点 (Subject Company Anchors)

**NO HARDCODES** — all values are cross-sheet formula references:

| Metric | Formula Pattern |
|--------|----------------|
| Revenue FY_LAST (亿) | `=IS!{hist_col}{revenue_row}/10000` |
| Gross Profit (亿) | `=IS!{hist_col}{gp_row}/10000` |
| EBIT (亿) | `=IS!{hist_col}{ebit_row}/10000` |
| Net Income (亿) | `=IS!{hist_col}{ni_row}/10000` |
| Total Equity (亿) | `=BS!{hist_col}{equity_row}/10000` |
| Total Assets (亿) | `=BS!{hist_col}{ta_row}/10000` |
| EV Gordon (万) | `=DCF!{dcf_cells.ev_gordon}` |
| EV Exit (万) | `=DCF!{dcf_cells.ev_exit}` |
| Net Debt (万) | `=DCF!{dcf_cells.net_debt}` |
| Equity Value avg (万) | `=DCF!{dcf_cells.eq_avg}` |

Row numbers and column letters come from `anchor_refs` in `project_config.yaml` + `dcf_cells`.

### Block 4: 估值推算 (Implied Valuation)

For each method (P/E TTM, P/E Forward, P/S, P/B):
- Low = 25th percentile multiple × anchor
- Mid = Median multiple × anchor
- High = 75th percentile multiple × anchor
- P/S and P/E → implied equity = anchor × multiple (for P/S: minus Net Debt)
- P/B → implied equity = Book Equity × PB multiple

### Block 5: 估值汇总桥接

DCF vs Comps side-by-side comparison:

| Method | Low | Mid | High | Source |
|--------|-----|-----|------|--------|
| DCF (Gordon) | `=DCF!{eq_gordon}` | `=DCF!{eq_avg}` | `=DCF!{eq_exit}` | DCF tab |
| P/E 可比 | Block4 ref | Block4 ref | Block4 ref | Comps Block 4 |
| P/S 可比 | Block4 ref | Block4 ref | Block4 ref | Comps Block 4 |
| P/B 可比 | Block4 ref | Block4 ref | Block4 ref | Comps Block 4 |

Analyst commentary: from `project_config.yaml` → `analyst_notes.comps_bridge`.

---

## Step 4 — _State Update

| Key | Value |
|-----|-------|
| COMPS_TAB | Comps |
| COMPS_TAB_COLOR | `{cfg.comps.tab_color}` |
| COMPS_DATA_DATE | `{latest_trade_date}` |
| COMPS_FIN_PERIOD | `{fin_period}` |
| COMPS_SOURCE | tushare daily_basic + income + balancesheet + fina_indicator |
| COMPS_SW_INDEX | `{cfg.comps.industry_index} {cfg.comps.industry_name}` |
| COMPS_N_PEERS | `{n}` |
| COMPS_PE_MED | `{pe_median}` |
| COMPS_PB_MED | `{pb_median}` |
| COMPS_PS_MED | `{ps_median}` |
| PHASE_DONE | SESSION_H |

---

## Step 5 — Save and Verify

```python
wb.save(MODEL_PATH)
print(f"✅ Comps tab complete — {n_peers} peers, PE_med={pe_med}, PB_med={pb_med}, PS_med={ps_med}")
```

Append checkpoint to `_model_log.md`.

---

## Appendix — iFinD 已验证指标目录 (跨项目复用)

完整 CSV: `shared/ifind_indicator_catalog.csv`

### 估值类 (universal — A股/港股/美股皆可)
| indicator_id | params | 单位 | 说明 |
|---|---|---|---|
| `pe_ttm`        | `YYYY-MM-DD,100` | ratio   | 市盈率 TTM |
| `ps_ttm`        | `YYYY-MM-DD,100` | ratio   | 市销率 TTM |
| `pb_latest`     | `YYYY-MM-DD,100` | ratio   | 市净率 (最新, 替代 pb_mrq) |
| `roe_ttm`       | `YYYY-MM-DD,100` | percent | ROE TTM (返回百分数) |
| `total_shares`  | `YYYY-MM-DD,100` | 股       | 总股本 |
| `ev1_to_ebitda` | `YYYY-MM-DD`     | ratio   | EV/EBITDA (无 unit 后缀; 部分港股 None) |

### 市值/净利 (按市场分流)
| 字段 | A股 indicator | 港股 indicator | params |
|---|---|---|---|
| 总市值 | `ths_market_value_stock` | `market_value` (推荐) / `ths_market_value_hks` | `YYYY-MM-DD,100` |
| 归母净利 TTM | `ths_np_ttm_stock` | `ths_np_ttm_hks` | 空 |
| 归母净利 (单期) | `ths_np_atoopc_stock` | `ths_np_atoopc_hks` | `YYYYMMDD,OC` |

### 价格 / 实时行情
- `realtime_quotes(ticker, 'latest')` → `OrderedDict({'latest': [价格]})` (原币)
- `history_quotes(codes, 'close', begin, end, 'Interval:D,Currency:original')` → 历史日线
- 港股复权:`'Interval:D,CPS:00102,baseDate:1900-01-01,Currency:HKD'`

### 外汇 — HKD↔CNY 推导
```python
df = history_quotes(['USDCNH.FX','USDHKD.FX'], 'close',
                    begin, end, 'Interval:D,Currency:original')
hkd_cny = USDCNH / USDHKD   # ≈ 0.87
```

### Ticker 格式注意
- 港股: 4 位补零 — `1316.HK`, `0699.HK`, `1057.HK`
- A股: 标准 6 位 — `603596.SH`, `002284.SZ`, `601689.SH`
- 港股指数: **`HSI.HK`** (注意是 `.HK` 不是 `.HI` — 后者多 ticker 同传时返回 None)
- A股指数: `000300.SH` 沪深300, `000905.SH` 中证500, `000016.SH` 上证50

---

## SESSION K (扩展) — DCF 二级市场数据刷新

DCF tab Block 1 中以下输入可由 iFinD 自动刷新:

### Rf 无风险利率
```python
df = basic_data('250015.IB', 'ths_ytm_bond', '2026-05-08')
# 250015.IB = 25国债15 (2025年发行的最新 10Y 国债)
# 返回百分数: 1.29 → /100 写入小数 0.0129
```
Fallback bond tickers (旧 10Y 国债, 剩余期限近 10Y 优先):
`230018.IB → 220015.IB → 190015.IB`

### Unlevered Beta βU (Hamada 去杠杆)
```python
# 1. 拉每只同业 + 基准 2 年日收盘
df = history_quotes(f'{stock},{bench}', 'close', begin, end,
                    'Interval:D,Currency:original')
# 2. 5 日采样 → weekly log 收益
# 3. OLS β = cov(s, i) / var(i)
# 4. D/E: 试 ths_total_liab / ths_total_se;
#    失败回退到目标 D/V (如 20% → D/E=0.25)
# 5. 去杠杆: βU = βL / (1 + (1-tax) × D/E)
# 6. 多同业取中位数
# 基准: A股用 000300.SH, 港股用 HSI.HK
# 税率: A股 0.25, 港股 0.165
```

### 保持静态 (分析师判断输入)
- B6  ERP%   — Damodaran / IB 内部口径, 无 iFinD 直连
- B12 Kd%   — 企业债 YTM iFinD 当前账户无权限
- B13 Tax   — 长期法定税率 (CN 25% / HK 16.5% blended)
- B31 g     — 长期名义 GDP 增长
- B37 Exit  — 行业 EV/EBITDA 中枢

### _State 追加键
| Key | Value |
|-----|-------|
| DCF_DATA_SOURCE | iFinD QuantAPI |
| DCF_REFRESH_DATE | YYYY-MM-DD |
| DCF_RF_VALUE | 0.0129 |
| DCF_RF_SOURCE | ths_ytm_bond(250015.IB) |
| DCF_BETA_U_VALUE | 1.034 |
| DCF_BETA_SOURCE | weekly OLS regression (2Y) over N peers, Hamada unlever, median |
| PHASE_DONE | …;SESSION_K_DCF_MARKET_REFRESH |

### 参考脚本
- `<company>/build_dcf_market_refresh.py` — 完整实现 (Rf + βU 回归 + 去杠杆)
- `<company>/build_h_comps_ifind_refresh.py` — Comps 同业刷新
