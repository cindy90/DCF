# SESSION J — Valuation Summary Tab (综合估值分析)

**Prerequisite:** `PHASE_DONE: SESSION_H` in `_State` tab.
**Output:** Adds `Valuation_Summary` sheet to the existing Excel model.
**Estimated time:** 10–15 min.

---

## PRE-FLIGHT CHECKLIST

```
□ _State: PHASE_DONE = SESSION_H
□ Comps tab complete: Block 4 estimation rows populated
□ DCF tab complete: EV Gordon / EV Exit / Net Debt / Equity values
□ project_config.yaml exists with valuation section filled
□ "Valuation_Summary" tab does NOT already exist
```

---

## ██ SHARED MODULE — MANDATORY IMPORT ██

**DO NOT define inline style/helper functions.** Import everything from `shared/`:

```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import (
    fill, fnt, aln, bdr,
    C_BLK, C_COLHDR, C_DCF, C_PE, C_PS, C_PB, C_WGT, C_CUR,
    C_GRAY, C_WHITE, C_NOTE,
    FMT_TEXT, FMT_N1, FMT_N2, FMT_PCT,
    write_blk_hdr, write_col_hdrs, write_cell,
    read_state, write_state_key,
)
from shared.config_loader import ProjectConfig
```

---

## Step 1 — Load Config and Locate Comps Rows

```python
cfg = ProjectConfig.from_yaml('project_config.yaml')
wb = load_workbook(cfg.model_path)

# Dynamically locate Comps Block 4 rows by scanning row labels
ws_comps = wb['Comps']
for row in ws_comps.iter_rows(min_row=1, max_row=ws_comps.max_row, min_col=2, max_col=2):
    val = str(row[0].value or '')
    if 'P/E TTM' in val: R_PE_ROW = row[0].row
    elif 'P/2' in val:   R_PE25E_ROW = row[0].row
    elif 'P/S' in val:   R_PS_ROW = row[0].row
    elif 'P/B' in val:   R_PB_ROW = row[0].row
```

**Never hardcode Comps row numbers** — always scan by label. Row layout may differ between projects.

---

## Step 2 — Build Valuation Summary (5 Blocks)

### Block 1: 综合估值汇总表

Each valuation method → Pessimistic / Neutral / Optimistic equity value (亿元):

| Method | Low (亿) | Mid (亿) | High (亿) | Weight | Source |
|--------|---------|---------|----------|--------|--------|
| DCF Gordon | `=DCF!{eq_gordon}/10000` | — | — | from config | DCF tab |
| DCF Exit | `=DCF!{eq_exit}/10000` | — | — | from config | DCF tab |
| P/E TTM | `=Comps!I{pe_row}` | `=Comps!H{pe_row}` | `=Comps!J{pe_row}` | from config | Comps Block 4 |
| P/E Forward | `=Comps!I{pe25e_row}` | `=Comps!H{pe25e_row}` | `=Comps!J{pe25e_row}` | from config | Comps Block 4 |
| P/S | `=Comps!I{ps_row}` | `=Comps!H{ps_row}` | `=Comps!J{ps_row}` | from config | Comps Block 4 |
| P/B | `=Comps!I{pb_row}` | `=Comps!H{pb_row}` | `=Comps!J{pb_row}` | from config | Comps Block 4 |

Method weights come from `project_config.yaml` → `valuation.method_weights`.

### Block 2: 估值区间瀑布图数据

Data rows for driving a horizontal bar chart (BarChart with error bars):
- Each method: base = low, bar length = mid − low, whisker = high
- Enables visual comparison of valuation ranges

### Block 3: 权重加权估值 & 当前融资对比

- Weighted average across all methods using `method_weights`
- Current round comparison: `valuation.current_round_value` and `valuation.current_round_label`
- Premium/discount calculation vs weighted mid

### Block 4: 关键假设摘要

Summary of key DCF assumptions (all formula references, no hardcodes):
- WACC → `=DCF!{dcf_cells.wacc}`
- Terminal growth → `=DCF!{dcf_cells.perpetuity_g}`
- Exit multiple → `=DCF!{dcf_cells.exit_multiple}`
- EV/Equity bridge → formula references

### Block 5: 分析师结论

Analyst commentary from `project_config.yaml` → `analyst_notes.conclusion`.
Written as a merged text block below the data.

---

## Step 3 — _State Update

| Key | Value |
|-----|-------|
| VALSUMMARY_TAB | Valuation_Summary |
| VALSUMMARY_TAB_COLOR | `{cfg.valuation.tab_color}` |
| PHASE_DONE | SESSION_J |

---

## Step 4 — Final Sheet Ordering

Reorder all sheets to match `desired_sheet_order` from `project_config.yaml`:

```python
desired = cfg._data.get('desired_sheet_order', [])
for i, name in enumerate(desired):
    if name in wb.sheetnames:
        wb.move_sheet(name, offset=i - wb.sheetnames.index(name))
```

---

## Step 5 — Save and Verify

```python
wb.save(cfg.model_path)
print("✅ Valuation_Summary complete — all blocks written, sheet order set")
```

Append checkpoint to `_model_log.md`.
