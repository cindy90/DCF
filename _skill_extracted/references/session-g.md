# Session G — Sensitivity & Scenario Tabs

**Prerequisite:** `PHASE_DONE: SESSION_F` in `_State` tab.
**Output files:** adds `Sensitivity` and `Scenario` sheets to the existing Excel model.
**Estimated time:** 15–20 min.

---

## PRE-FLIGHT CHECKLIST

```
□ _State: PHASE_DONE = SESSION_F (or SESSION_G if resuming)
□ DCF tab complete: blocks B1-B6 present, WACC in DCF!B21, UFCFs in DCF!B33:F33
□ KEY_CELLS_IS, KEY_CELLS_BS, KEY_CELLS_CF all populated in _State
□ ASM_MAP populated in _State (must include rows 5-9, 24-25, 27-32, 35-36, 40-41)
□ "Sensitivity" and "Scenario" tabs do NOT already exist (fresh build)
```

---

## Step 1 — Read Required References

From `_State`, extract and confirm:

| Key | Expected value |
|-----|----------------|
| `IS_COL_MAP` | E=FY26, F=FY27, G=FY28, H=FY29, I=FY30 |
| `KEY_CELLS_IS` | Revenue_row (should be 17), EBIT_row (49), NI_row (58) |
| `KEY_CELLS_CF` | CFO_row (17) |
| `DCF_UFCF_RANGE` | `DCF!B33:F33` — confirm 5 values present |
| `DCF_NET_DEBT` | `DCF!B70` — confirm non-empty |
| `DCF_TERMINAL_EBITDA` | `DCF!B48` — confirm non-empty |
| `DCF_WACC_CELL` | `DCF!B21` |
| `DCF_G_CELL` | `DCF!B41` |
| `DCF_EXIT_MULT_CELL` | `DCF!B47` |
| `DCF_EV_GORDON` | `DCF!B60` |
| `DCF_EV_EXIT` | `DCF!B65` |
| `DCF_EQUITY_GORDON` | `DCF!B72` |
| `DCF_EQUITY_EXIT` | `DCF!B73` |
| `DCF_EQUITY_AVG` | `DCF!B74` |
| `ASM_MAP.Rev YoY% FY2026E` | Row 5 |
| `ASM_MAP.GM% Blended (FY2026E)` | Row 24 |

---

## Step 2 — Build Sensitivity Tab

### 2.1 Tab creation

```python
# Insert after DCF, before Cross_Check
dcf_idx = wb.sheetnames.index('DCF')
wb.create_sheet("Sensitivity", dcf_idx + 1)
ws = wb["Sensitivity"]
ws.sheet_properties.tabColor = "7030A0"   # purple
ws.sheet_view.showGridLines = False
ws.freeze_panes = "B6"
```

### 2.2 WACC / g / multiple ranges

| Table | WACC rows | Col variable | Range |
|-------|-----------|--------------|-------|
| A — EV Gordon | 9–14% (6 rows) | g | 2.0%, 2.5%, 3.0%, 3.5%, 4.0% |
| B — EV Exit | 9–14% (6 rows) | EV/EBITDA | 7×, 8×, 9×, 10×, 11×, 12× |
| C — Equity Gordon | 9–14% (6 rows) | g | same as A |
| D — Equity Exit | 9–14% (6 rows) | EV/EBITDA | same as B |
| E — Tornado | N/A | Variable | WACC±1%, g±0.5%, Exit±1× |

Base case: WACC=11%, g=3%, EV/EBITDA=10×. Highlight green.

### 2.3 Cell formula patterns

**Gordon EV cell** (WACC=`w`, g=`g`):
```
=IF((w-g)>0,
    DCF!B33/(1+w)^1 + DCF!C33/(1+w)^2 + DCF!D33/(1+w)^3 +
    DCF!E33/(1+w)^4 + DCF!F33/(1+w)^5 +
    DCF!F33*(1+g)/(w-g)/(1+w)^5,
  "ERR")
```

**Exit EV cell** (WACC=`w`, EV/EBITDA=`m`):
```
= DCF!B33/(1+w)^1 + DCF!C33/(1+w)^2 + DCF!D33/(1+w)^3 +
  DCF!E33/(1+w)^4 + DCF!F33/(1+w)^5 +
  DCF!B48 * m / (1+w)^5
```

**Equity Value** = same as above but append `- DCF!B70`.

**Critical rule:** `w`, `g`, `m` are literal numbers in each cell formula (e.g. `0.11`, `0.03`, `10`). The formula is **fully self-contained per cell** — no references to a single WACC parameter cell. This ensures table remains valid even if DCF inputs change, and individual scenario cells can be compared independently.

### 2.4 Tornado table

```
Variable          | Bear (base−Δ)              | Base          | Bull (base+Δ)
WACC ± 1%         | gordon_ev(0.12, 0.03)      | =DCF!B60      | gordon_ev(0.10, 0.03)
g ± 0.5%          | gordon_ev(0.11, 0.025)     | =DCF!B60      | gordon_ev(0.11, 0.035)
EV/EBITDA ± 1×    | exit_ev(0.11, 9)           | =DCF!B65      | exit_ev(0.11, 11)
Revenue growth    | → see Scenario tab         | =DCF!B60      | → see Scenario tab
```

### 2.5 QC

- [ ] Table A base cell matches `DCF!B60` ±1 (rounding)
- [ ] Table B base cell matches `DCF!B65` ±1
- [ ] Table C base cell matches `DCF!B72` ±1
- [ ] Table D base cell matches `DCF!B73` ±1
- [ ] No cell in any table references another Sensitivity cell (all formulas start from `DCF!B33`)
- [ ] WACC=14%, g=4%: ERR guard fires correctly (g > WACC check NOT applicable here, but check g < WACC)
  - Actually 14% > 4% so no ERR. Check g=14.5% row if it existed; since we cap at 14%, verify no ERR in valid range.

---

## Step 3 — Build Scenario Tab

### 3.1 Tab creation

```python
sens_idx = wb.sheetnames.index('Sensitivity')
wb.create_sheet("Scenario", sens_idx + 1)
ws2 = wb["Scenario"]
ws2.sheet_properties.tabColor = "ED7D31"   # orange
ws2.sheet_view.showGridLines = False
ws2.freeze_panes = "C8"
```

### 3.2 Three blocks

#### Block 1: Assumption Inputs (rows ~7–25)

Column layout:
```
A: parameter name
B: ASM_MAP row# (display only)
C-G: Bear values (light-red fill, FY26E–FY30E)
H-L: Base values (light-green fill, FY26E–FY30E) ← MUST BE =Assumptions!B{row}
M-N: Bull Δ description / Bull value
```

**Base column rules (strictly enforced):**
```
Revenue YoY% FY26E  → =Assumptions!B5
Revenue YoY% FY27E  → =Assumptions!B6
Revenue YoY% FY28E  → =Assumptions!B7
Revenue YoY% FY29E  → =Assumptions!B8
Revenue YoY% FY30E  → =Assumptions!B9
GM% Blended FY26E   → =Assumptions!B24
GM% Blended FY30E   → =Assumptions!B25
Selling% FY26E      → =Assumptions!B27
Admin% FY26E        → =Assumptions!B29
R&D% FY26E          → =Assumptions!B31
```

**Bear formulas:** `=MAX(0, Assumptions!B{row} - {delta})`
**Bull formulas (stored as Δ description):** `=Assumptions!B{row} + {delta}`

Never type the actual Base numeric value (e.g. 83%) — always link to Assumptions.

#### Block 2: Financial Summary (rows ~28–38)

5 years × 3 scenarios:
```
Col C-G:  Bear = IS!/CF!/DCF! base cell × bear_scale (or ± ppt for margins)
Col H-L:  Base = direct IS!/CF!/DCF! links
Col M-N:  Bull = IS!/CF!/DCF! last year × bull_scale (summary reference)
```

Line items and their scale factors:

| Line | Base ref | Bear scale | Bull scale |
|------|----------|------------|------------|
| Revenue | `IS!{col}17` | ×0.80 | ×1.10 |
| Gross Profit | `IS!{col}27` | ×0.72 | ×1.14 |
| GM% | `IS!{col}27/IS!{col}17` | -3ppt | +3ppt |
| EBIT | `IS!{col}49` | ×0.60 | ×1.20 |
| Net Income | `IS!{col}58` | ×0.60 | ×1.20 |
| CFO | `CF!{col}17` | ×0.70 | ×1.20 |
| UFCF | `DCF!{dcf_col}33` | ×0.70 | ×1.20 |

IS columns: E=FY26E, F=FY27E, G=FY28E, H=FY29E, I=FY30E.
DCF UFCF columns: B=FY26E, C=FY27E, D=FY28E, E=FY29E, F=FY30E.

#### Block 3: Scenario Valuation (rows ~41–52)

| Row | Bear | Base | Bull |
|-----|------|------|------|
| EV Gordon | inline (UFCF×0.80 + TV×0.80) using `DCF!B21`, `DCF!B41` | `=DCF!B60` | inline (UFCF×1.10) |
| EV Exit | inline (UFCF×0.80 + EBITDA×0.80×Mult) using `DCF!B21`, `DCF!B47` | `=DCF!B65` | inline |
| Net Debt | `=DCF!B70` | `=DCF!B70` | `=DCF!B70` |
| Equity Gordon | EV_Gordon_Bear − DCF!B70 | `=DCF!B72` | EV_Gordon_Bull − DCF!B70 |
| Equity Exit | EV_Exit_Bear − DCF!B70 | `=DCF!B73` | EV_Exit_Bull − DCF!B70 |
| **Equity Avg** | **(G+E_Bear)/2** | **`=DCF!B74`** | **(G+E_Bull)/2** |

**Bear/Bull scenario EV formula** (scale = 0.80 or 1.10):
```
Gordon: =IF((DCF!B21-DCF!B41)>0,
             DCF!B33*s/(1+DCF!B21)^1 + DCF!C33*s/(1+DCF!B21)^2 + ... +
             DCF!F33*s*(1+DCF!B41)/(DCF!B21-DCF!B41)/(1+DCF!B21)^5,
           "ERR")

Exit:   = DCF!B33*s/(1+DCF!B21)^1 + ... + DCF!B48*s*DCF!B47/(1+DCF!B21)^5
```
Where `s` = scale literal (0.80 or 1.10). `DCF!B21`, `DCF!B41`, `DCF!B47` are cell references, not numbers.

### 3.3 QC

- [ ] Every Base cell in Block 1 starts with `=Assumptions!B` (grep check)
- [ ] No Base block cell contains a hardcoded numeric literal for a parameter
- [ ] Block 2 Base column cells link to IS!/CF!/DCF! (not re-computed inline)
- [ ] Block 3 Base column matches DCF!B72/B73/B74 exactly
- [ ] WACC cell in Bear/Bull formulas = `DCF!B21` reference (not 0.11 hardcoded)

---

## Step 4 — Update _State

```python
updates = {
    "PHASE_DONE": "SESSION_G",
    "SESSION_G_DATE": "<today>",
    "SENSITIVITY_TAB": "Sensitivity",
    "SENSITIVITY_KEY_CELLS": "EV_Gordon_base=DCF!B60; EV_Exit_base=DCF!B65; NetDebt=DCF!B70",
    "SCENARIO_TAB": "Scenario",
    "SCENARIO_BEAR_SCALE": "0.80",
    "SCENARIO_BULL_SCALE": "1.10",
    "SCENARIO_BASE_LINKS": "All Base params = Assumptions!B{row} via ASM_MAP",
    "SCENARIO_KEY_REFS": "WACC=DCF!B21; g=DCF!B41; ExitMult=DCF!B47; NetDebt=DCF!B70",
}
```

---

## Step 5 — Final QC Checklist

```
□ QC-S1: Sensitivity sheet exists with 5 tables (A-E)
□ QC-S2: Sensitivity table A base cell = DCF!B60 ±1
□ QC-S3: Sensitivity table B base cell = DCF!B65 ±1
□ QC-S4: Sensitivity table C base cell = DCF!B72 ±1
□ QC-S5: Sensitivity table D base cell = DCF!B73 ±1
□ QC-SC1: Scenario sheet exists with 3 blocks
□ QC-SC2: No hardcoded Base values in Block 1 (all link to Assumptions!B)
□ QC-SC3: Block 3 Base Equity Avg = DCF!B74 reference
□ QC-SC4: Bear/Bull WACC = DCF!B21 reference (not 0.11)
□ QC-SC5: Net Debt in Block 3 = DCF!B70 for all 3 scenarios
□ Tab order: ..., DCF, Sensitivity, Scenario, Cross_Check, ...
□ _State PHASE_DONE = SESSION_G
```

---

## Error Handling

| Error | Fix |
|-------|-----|
| Sensitivity base ≠ DCF!B60 | Recalculate; check if DCF uses different UFCF row |
| Scenario Base cell has literal number | Find ASM_MAP row and replace with `=Assumptions!B{row}` |
| Bear/Bull EV formula has 0.11 hardcoded | Replace with `DCF!B21` reference |
| Tab already exists | Delete and rebuild; or verify existing matches this spec |
| `g ≥ WACC` ERR in sensitivity | Expected for edge cells (g=4%, WACC=3.5% etc.) — correct behavior |

---

## Appendix — Default Scenario Parameters (example)

These are the Assumptions values used to derive Bear/Bull deltas.
If company changes, re-read ASM_MAP from _State and adjust accordingly.

| Parameter | Asm Row | Base Value | Bear Δ | Bull Δ |
|-----------|---------|------------|--------|--------|
| Rev YoY% FY26E | 5 | 83% | −20ppt | +10ppt |
| Rev YoY% FY27E | 6 | 50% | −20ppt | +10ppt |
| Rev YoY% FY28E | 7 | 33% | −20ppt | +10ppt |
| Rev YoY% FY29E | 8 | 50% | −20ppt | +10ppt |
| Rev YoY% FY30E | 9 | 39% | −20ppt | +10ppt |
| GM% FY26E | 24 | 23.5% | −3ppt | +3ppt |
| GM% FY30E | 25 | 30.0% | −3ppt | +3ppt |
| Selling% FY26E | 27 | 5.0% | +1ppt | −1ppt |
| Admin% FY26E | 29 | 6.7% | +1ppt | −1ppt |
| R&D% FY26E | 31 | 4.5% | +1ppt | −1ppt |

Financial summary scaling:

| P&L line | Bear scale | Bull scale |
|----------|------------|------------|
| Revenue | ×0.80 | ×1.10 |
| Gross Profit | ×0.72 | ×1.14 |
| EBIT | ×0.60 | ×1.20 |
| Net Income | ×0.60 | ×1.20 |
| CFO | ×0.70 | ×1.20 |
| UFCF | ×0.70 | ×1.20 |

DCF scenario scaling (applied to all UFCF values and Terminal Value):
- Bear: all cash flows × 0.80
- Bull: all cash flows × 1.10
- WACC / g / Exit multiple: unchanged (held at DCF base)
