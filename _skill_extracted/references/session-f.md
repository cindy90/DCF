# SESSION F — DCF Valuation Tab

## Overview

SESSION F adds the **DCF** tab to an existing completed 3-statement model (after SESSION E).
Prerequisite: SESSION E PHASE_DONE must be present in _State. All IS/BS/CF tabs must be complete with KEY_CELLS written to _State.

**Tab created:** `DCF` (green tab color #70AD47, inserted after Returns, before Cross_Check)

**Sheet count after SESSION F:** 9 data tabs + _Registry + _State = 11 total

---

## SESSION F Steps

```
Step 1:  Re-read SKILL.md (Rule Zero, R12)
Step 2:  Open Excel → read _State tab
Step 3:  Verify PHASE_DONE includes "SESSION_E" (or equivalent)
Step 4:  Read KEY_CELLS_IS, KEY_CELLS_BS, KEY_CELLS_CF from _State
Step 5:  Read references/session-f.md (this file)
Step 6:  Build DCF tab (see PHASE F below)
Step 7:  Write checkpoint to _model_log.md
Step 8:  Update _State: add PHASE_DONE: SESSION_F, DCF_KEY_CELLS: {...}
```

---

## PHASE F — DCF Tab Architecture

The DCF tab has **6 blocks** in a single column layout (col A = labels, col B = values / formulas):

```
BLOCK 1  (R4–R21):   WACC 加权平均资本成本
BLOCK 2  (R23–R37):  FCF 自由现金流预测 (FY_FCST cols B–F = 5 forecast years)
BLOCK 3  (R39–R54):  Terminal Value (3A Gordon + 3B Exit Multiple + 3C TV%)
BLOCK 4  (R56–R74):  EV → Equity Bridge (两法 + Net Debt)
BLOCK 5  (R76–R93):  敏感性分析 (Table1: WACC×g, Table2: WACC×EV/EBITDA)
BLOCK 6  (R95–R107): 估值汇总表 (Summary + Notes)
```

**Column mapping for BLOCK 2:**
- Col B = FY_{FCST+1}E (links to IS/CF forecast col E = openpyxl col 5)
- Col C = FY_{FCST+2}E (IS/CF col F)
- Col D = FY_{FCST+3}E (IS/CF col G)
- Col E = FY_{FCST+4}E (IS/CF col H)
- Col F = FY_{FCST+5}E (IS/CF col I)

Read `first_fcst_col` from KEY_CELLS_IS to determine the correct IS/CF column letters.

---

## BLOCK 1 — WACC Calculation

### 1.1 Cost of Equity (CAPM)

| Row | Label                              | Formula / Input    |
|-----|------------------------------------|--------------------|
| R6  | 无风险利率 Rf                       | 0.025 (hard input) |
| R7  | 股权风险溢价 ERP                    | 0.070 (hard input) |
| R8  | Unlevered Beta βU                  | 1.20 (hard input)  |
| R9  | D/E (FY_LAST_HIST)                 | `=(BS!{hist_col}STBorrow + BS!{hist_col}LeaseLT + BS!{hist_col}LTPay) / MAX(BS!{hist_col}TotalEq, 1)` |
| R10 | Tax rate (for relevering)          | 0.15 (hard input)  |
| R11 | Relevered Beta βL                  | `=B8*(1+(1-B10)*B9)` |
| R12 | Ke = Rf + βL×ERP                   | `=B6+B11*B7`        |

### 1.2 Cost of Debt & Capital Structure

| Row | Label                              | Formula / Input    |
|-----|------------------------------------|--------------------|
| R15 | Kd pre-tax                         | 0.050 (hard input) |
| R16 | Kd after-tax = Kd×(1-t)           | `=B15*(1-B10)`     |
| R17 | Total Capital (IBD + Equity)       | `=BS!{hist_col}STBorrow + BS!{hist_col}LeaseLT + BS!{hist_col}LTPay + BS!{hist_col}TotalEq` |
| R18 | We = Equity / Total Capital        | `=IF(B17=0,0.7, BS!{hist_col}TotalEq/B17)` |
| R19 | Wd = IBD / Total Capital           | `=IF(B17=0,0.3, (BS!{hist_col}STBorrow+BS!{hist_col}LeaseLT+BS!{hist_col}LTPay)/B17)` |
| R21 | **WACC = We×Ke + Wd×Kd×(1-t)**    | `=B18*B12+B19*B16` |

**NOTE:** `{hist_col}` = the last historical column letter (e.g., `D` if FY2025 is col D). Read from KEY_CELLS_BS `first_fcst_col - 1`.

---

## BLOCK 2 — FCF Projection (UFCF method)

UFCF = NOPAT + D&A + Capex(as signed from CF) − ΔNWC

| Row | Label                | Formula (example for col B = year1)                        |
|-----|----------------------|------------------------------------------------------------|
| R25 | EBIT                 | `=IS!{fcst1}EBIT_row`                                      |
| R26 | 减: Tax (EBIT×t)     | `=-IS!{fcst1}EBIT_row * Assumptions!{tax_cell}`            |
| R27 | NOPAT                | `=B25+B26`                                                 |
| R29 | + D&A                | `=IS!{fcst1}DA_Total_row`                                  |
| R30 | + Capex (CF sign)    | `=CF!{fcst1}CAPEX_row`  (already negative in CF — adds)    |
| R31 | − ΔNWC               | `=-(NWC_curr - NWC_prior)`  where NWC = AR+Inv+Prepay+OtherRecv−AP−ContractLiab |
| R33 | **UFCF**             | `=B27+B29+B30+B31`                                         |
| R34 | Discount period t    | Hardcode: 1, 2, 3, 4, 5                                    |
| R35 | Discount factor      | `=1/(1+$B$21)^t`                                           |
| R36 | PV of FCF            | `=B33*B35`                                                 |
| R37 | Σ PV of FCFs         | `=SUM(B36:F36)`                                            |

**ΔNWC sign convention:** ΔNWC is the cash OUTFLOW from working capital increase. Use `=-(NWC_curr − NWC_prior)` so that if NWC grows (cash consumed), this is negative → reduces UFCF. If NWC shrinks (cash released), positive → adds to UFCF.

**Capex:** CF CAPEX row is already negative in the CF statement (cash outflow = negative number). Adding it directly to UFCF is correct: `+ CF!{col}CAPEX_row`. Do NOT double-negate.

---

## BLOCK 3 — Terminal Value

### 3A: Gordon Growth Model
```
TV_Gordon  = UFCF_{T+1} / (WACC − g)
           = F33*(1+B41) / (B21−B41)        [where F33=last UFCF, B41=g, B21=WACC]
Guard:     =IF((B21-B41)>0, ..., "ERR: g≥WACC")

PV_TV_Gordon = TV_Gordon / (1+WACC)^5
```

### 3B: EV/EBITDA Exit Multiple
```
Terminal EBITDA = IS!{fcst5}EBIT_row + IS!{fcst5}DA_Total_row
TV_Exit        = Terminal EBITDA × exit_multiple
PV_TV_Exit     = TV_Exit / (1+WACC)^5
```

### 3C: TV% of EV
```
TV%_Gordon  = PV_TV_Gordon / (Σ PV_FCFs + PV_TV_Gordon)
TV%_Exit    = PV_TV_Exit   / (Σ PV_FCFs + PV_TV_Exit)
```
Typical range for high-growth companies: TV% = 60–80%. If >90%, the terminal assumptions dominate — flag for review.

---

## BLOCK 4 — Enterprise Value → Equity Bridge

```
EV (Gordon)  = Σ PV_FCFs + PV_TV_Gordon
EV (Exit)    = Σ PV_FCFs + PV_TV_Exit

IBD          = BS!{hist_col}STBorrow + BS!{hist_col}LeaseLT + BS!{hist_col}LTPay
Cash         = CF!{hist_col}EndCash_row    ← use CF TotalCash (=CF!col37 per KEY_CELLS_CF)
Net Debt     = IBD − Cash

Equity Value (Gordon) = EV (Gordon) − Net Debt
Equity Value (Exit)   = EV (Exit) − Net Debt
Average Equity Value  = (Gordon + Exit) / 2
```

**Use FY_LAST_HIST for Net Debt**, not a forecast year. If Cash > IBD → Net Cash (negative Net Debt → adds to equity value).

---

## BLOCK 5 — Sensitivity Tables

Two 6×5 or 6×6 grids. Each cell contains an **independent inline formula** (no Excel DATA TABLE — openpyxl cannot write DATA TABLE arrays):

### Table 1: WACC (rows) × g (cols) → EV Gordon
```python
# Each cell (wi, gi) where w = WACC value, g = terminal growth value:
pv_fcfs = '+'.join([f'{col}33/(1+{w})^{t}' for t, col in enumerate(fcst_cols, 1)])
tv_gor  = f'{last_fcst_col}33*(1+{g})/({w}-{g})/(1+{w})^5'
formula = f'={pv_fcfs}+{tv_gor}'
# Guard: skip cell if abs(w-g) < 0.001
```

### Table 2: WACC (rows) × EV/EBITDA multiple (cols) → EV Exit
```python
# Each cell (wi, mi) where w = WACC value, m = exit multiple:
pv_fcfs  = '+'.join([f'{col}33/(1+{w})^{t}' for t, col in enumerate(fcst_cols, 1)])
tv_exit  = f'B48*{m}/(1+{w})^5'   # B48 = terminal EBITDA cell in Block 3B
formula  = f'={pv_fcfs}+{tv_exit}'
```

Highlight base-case cell (WACC=11%, g=3% or m=10x) in green.

---

## BLOCK 6 — Valuation Summary Table

3-row table: Gordon / Exit / Average
Columns: 方法 | EV(万元) | 净有息负债(万元) | 权益价值(万元) | 权益价值(亿元)

---

## Key Formula Rules (R12 enforcement)

1. **No hardcoded WACC in formulas.** Rf, ERP, Beta, Kd are allowed as input cells (light-blue fill). WACC itself must be computed `=We×Ke + Wd×Kd×(1-t)`.
2. **All FCF components link to IS/BS/CF rows** using KEY_CELLS from _State.
3. **Sensitivity grid cells are self-contained** — they do not reference the WACC/g input cells in Block 1 (to avoid circular Data Table issues and to ensure each scenario is truly independent).
4. **Net Debt uses last historical column** — not current-year forecast.
5. **g < WACC guard** — `IF((WACC−g)>0, formula, "ERR: g≥WACC")` on all Gordon TV cells.

---

## _State Update (end of SESSION F)

Write to _State tab:
```
PHASE_DONE: SESSION_F
DCF_KEY_CELLS: {"WACC_cell": "DCF!B21", "Ke_cell": "DCF!B12", "EV_Gordon_cell": "DCF!B60",
                "EV_Exit_cell": "DCF!B65", "Equity_Gordon_cell": "DCF!B72",
                "Equity_Exit_cell": "DCF!B73", "AvgEquity_cell": "DCF!B74",
                "UFCF_row": 33, "TV_Gordon_row": 43, "TV_Exit_row": 49,
                "NetDebt_row": 70, "Rf_cell": "DCF!B6", "ERP_cell": "DCF!B7",
                "BetaU_cell": "DCF!B8", "g_cell": "DCF!B41", "ExitMult_cell": "DCF!B47"}
```

---

## _model_log.md Checkpoint

```markdown
### SESSION F — DCF Tab

**Date/Time:** [auto]
**WACC inputs:** Rf=2.5%, ERP=7.0%, βU=1.20, Kd=5.0%, tax=15%, We/Wd from FY_LAST_HIST
**Computed WACC:** ~XX.X% (from DCF!B21)
**Forecast period:** FY{FCST+1}E – FY{FCST+5}E (5 years)
**Terminal methods:** Gordon (g=3%) + EV/EBITDA exit (10×)
**TV% Gordon:** ~XX%
**EV Gordon:** ~X,XXX 万元
**EV Exit:**   ~X,XXX 万元
**Net Debt (FY_LAST_HIST):** ~XXX 万元
**Equity Value (avg):** ~X,XXX 万元  (~X.X 亿元)
**Sensitivity:** Table1 WACC 9%–14% × g 2%–4%; Table2 WACC 9%–14% × EV/EBITDA 7×–12×
**PHASE_DONE:** SESSION_F ✅
```

---

## Common Errors (R12 — DCF-specific)

| # | Error | Fix |
|---|-------|-----|
| 1 | `g ≥ WACC` → Gordon TV blows up | Use `IF((WACC-g)>0,...)` guard; ensure g ≤ 4% |
| 2 | Double-negative Capex | CF Capex row is already negative — don't negate again |
| 3 | Wrong Net Debt column | Must use FY_LAST_HIST hist col, not first forecast col |
| 4 | Sensitivity cells reference B21/B41 (not hardcoded) | Each sensitivity cell must embed the scenario WACC/g as literal numbers |
| 5 | TV% > 95% | Check if forecast UFCF is near-zero — may need to extend projection period |
| 6 | Equity Value < 0 | Net Debt exceeds EV — verify IBD vs Cash balance signs |
