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

### BLOCK 2 增强（可选）— Mid-Year Convention 折现开关

默认沿用**期末折现**（R34 = 1,2,3,4,5）。如需 mid-year（现金流年中到账，更贴近实务），加开关单元格：

- **H6 = Mid-Year Toggle**（浅蓝 input；`0` 或留空 = 期末法[默认]，`1` = mid-year），cell comment 注明含义。
- **R34（折现期 t）改为逐列公式**（覆盖原字面整数，5 列全写，不可残留旧值）：
  - B34 `=IF($H$6=1,0.5,1)`  C34 `=IF($H$6=1,1.5,2)`  D34 `=IF($H$6=1,2.5,3)`  E34 `=IF($H$6=1,3.5,4)`  F34 `=IF($H$6=1,4.5,5)`
- **R35 折现因子不变**：`=1/(1+$B$21)^{col}34`（仍引用 R34 期数单元格，Rule Zero 不变）。
- **终值 PV 指数按方法区分**（关键，勿一刀切）：
  - **Gordon 永续**（R44）：`=IF(ISNUMBER(B43), B43/(1+$B$21)^IF($H$6=1,4.5,5), "ERR")` —— 永续现金流也按年中，估值点 t=4.5，自洽。
  - **退出倍数**（R50）：**始终 `=B49/(1+$B$21)^5`，不随 H6 变** —— 退出倍数是第 5 年**年末**一次性交易市值（point-in-time）；若误用 ^4.5 会高估退出法 EV 约 (1+WACC)^0.5−1 ≈ +5.4%。
- **联动提醒**：H6=1 时，Session G 敏感性/情景表的 `^5` 字面量与 DCF 头条不再对账（其 QC `base=DCF!B60 ±1` 会失败）。**默认 H6=0 可规避**；若要默认 mid-year，须同步改 Session G 的 ^5 或放宽该 QC。

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

## BLOCK 7 — Per-Share Intrinsic Value & Implied Upside（每股内含价值，additive；R109–R118）

放在 Block 6 之后（R109 起，不与既有行冲突）。把 EV→权益桥的平均权益换算到**每股**并对比现价。全程公式（Rule Zero）；摊薄股本/汇率/现价为**浅蓝 input**（或链接 Raw_Info），均须 cell comment 注明来源。

| Row | Label | Formula / Input | 说明 |
|-----|-------|-----------------|------|
| R109 | `=== PER-SHARE INTRINSIC VALUE ===` | 段标题 | |
| R113 | Equity Value (avg, 万元, 报告币) | `=B74` | 复用 Block4 平均权益（已含 Net Debt，口径=BS Cash, FY_LAST_HIST） |
| R114 | Diluted Shares (M, 摊薄股本) | 浅蓝 input 或 `=Raw_Info!{cell}` | **comment 注明来源**（招股书/年报摊薄股数）；Raw_Info 已有则绿字链接 |
| R115 | FX 报告币→交易币 | 浅蓝 input | **comment 强制**：报告币=交易币时填 1；**港股(如 6871.HK 现价 HK$) 若报告币为 RMB，必须填 RMB→HKD 汇率，不可留 1** |
| R116 | Per-Share Intrinsic (交易币/股) | `=(B113*10000)*B115/(B114*1000000)` | 报告币万元→元(×10000)→×FX→交易币；÷(M股×1e6)=股 |
| R117 | Current Price (交易币/股) | 浅蓝 input | comment：行情来源 + 日期 |
| R118 | Implied Upside/(Downside) | `=B116/B117-1` | FMT_PCT；**仅当 R116 与现价同币种时才有意义**（见 R115） |

> 净现金时 B74 已含负 Net Debt，EV−NetDebt 自洽，无需特判。

## BLOCK 8 — DCF-Internal Scenario Selector（可选；H/I/J/K 列，不占既有 A–G 列）

DCF tab 内做 Bear/Base/Bull 一键切换，使关键驱动整组切换，且**所有受影响单元格仍是公式**（用 INDEX 整合，**禁止散落 IF**）。

- **H4 = Case Selector**（浅蓝 input，整数 `1`=Bear / `2`=Base / `3`=Bull；**默认 2**）。
- **H5 = Case Name** = `=IF($H$4=1,"Bear",IF($H$4=2,"Base","Bull"))`。
- **情景值放 I/J/K 列**，与各 driver 行**同排**（I=Bear, J=Base, K=Bull）。driver 行：R6 Rf、R7 ERP、R8 βU、R10 tax、R15 Kd、R41 g、R47 Exit Mult。
- **J 列(Base) 必须逐行复刻该行"现行实际来源"**（关键，勿一律写 Assumptions）：
  - 若该行现状是 `=Assumptions!F{n}` 链接 → `J{r}` 用**同一链接**；
  - 若该行现状是**硬输入**（如本规格的 Rf=0.025/ERP=0.070/βU=1.20/tax/Kd，及 Exit Mult=10）→ `J{r}` **复刻同一数值（浅蓝 input）**；
  - I/K(Bear/Bull) 为浅蓝 input（或链接 Assumptions 情景行）。
- **整合**：原 driver 格改为 `B{r}=INDEX(I{r}:K{r},1,$H$4)`，并**清除其浅蓝 FILL_INPUT 填充、字色改黑(FNT_DATA)**（它已是公式不再是输入）；仅 H4 与 I/J/K 保留浅蓝+蓝字。
- **默认 H4=2 时输出与增强前 byte-identical**（J 列=各行现行来源）。
- **⚠ 与 Session G 的硬约束**：交付或进入 Session G **前 H4 必须=2(Base)**，并在 `_model_log` 记录。Session G 的 grid 用字面量 WACC/g/m、Scenario Base 列 `=DCF!B72/B73/B74` 直链；H4≠2 时 DCF 头条漂移而 grid 不动 → Session G QC-S2/S3 失败。建议 Session G 加前置断言 `DCF!H4==2 否则 abort/警告`。

> Block 8 是 **DCF tab 内的快速情景切换**（单值组）；**多情景正式分析（全矩阵 + 三情景表）仍由 Session G 承担**，两者不冲突。

## Key Formula Rules (R12 enforcement)

1. **No hardcoded WACC in formulas.** Rf, ERP, Beta, Kd are allowed as input cells (light-blue fill). WACC itself must be computed `=We×Ke + Wd×Kd×(1-t)`.
2. **All FCF components link to IS/BS/CF rows** using KEY_CELLS from _State.
3. **Sensitivity grid cells are self-contained** — they do not reference the WACC/g input cells in Block 1 (to avoid circular Data Table issues and to ensure each scenario is truly independent).
4. **Net Debt uses last historical column** — not current-year forecast.
5. **g < WACC guard** — `IF((WACC−g)>0, formula, "ERR: g≥WACC")` on all Gordon TV cells.
6. **Mid-year (可选)** — H6=1 时：R34 期数逐列 `=IF($H$6=1,0.5,1)`…；Gordon 终值 PV 用 `^IF($H$6=1,4.5,5)`；**退出倍数终值 PV 始终 `^5`**（年末交易市值，不随 H6 变）；R35 仍引用 R34 期数单元格。
7. **Scenario selector 用 INDEX，禁散落 IF** — driver 格 `=INDEX(I{r}:K{r},1,$H$4)`；J(Base) 列逐行复刻现行来源（链接行用链接、硬输入行复刻值）；整合格转公式后清除浅蓝填充改黑字；**默认 H4=2，进 Session G 前 H4 必须=2**。
8. **每股链** — 仅摊薄股本/汇率/现价可为硬输入（浅蓝 + comment）；每股 `=(权益万元*10000)*FX/(摊薄M股*1e6)`，上行 `=每股/现价-1`，务必同币种。

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
                "BetaU_cell": "DCF!B8", "g_cell": "DCF!B41", "ExitMult_cell": "DCF!B47",
                "CaseSelector_cell": "DCF!H4", "CaseName_cell": "DCF!H5", "MidYearToggle_cell": "DCF!H6",
                "DilutedShares_cell": "DCF!B114", "FXrate_cell": "DCF!B115", "PerShare_cell": "DCF!B116",
                "CurrentPrice_cell": "DCF!B117", "ImpliedUpside_cell": "DCF!B118"}

（前缀约定：本规格 DCF_KEY_CELLS 统一带 `DCF!` 前缀；实现脚本如写裸地址需全表统一其一。新增键为 additive，未改动既有 WACC_cell/g_cell/ExitMult_cell/NetDebt_row/AvgEquity_cell 等 Session G 引用契约；既有 TV% 单元格 B45/B51 为既有产物、非本次新增。）
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
| 7 | mid-year 把退出倍数终值也用 ^4.5 | 退出倍数 TV 始终 `^5`(年末市值)；mid-year 的 4.5 只用于 Gordon 永续 |
| 8 | selector 用散落 IF / J(Base) 列一律写 Assumptions | 用 `=INDEX(I:K,1,$H$4)`；J 逐行复刻现行来源；进 Session G 前 H4=2 |
| 9 | 每股用基本股本、或 RMB/股 直接比港元现价 | 用摊薄股本；先用 FX 把每股换到现价币种再算上行% |
