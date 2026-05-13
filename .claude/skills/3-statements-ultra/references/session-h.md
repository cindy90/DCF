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
