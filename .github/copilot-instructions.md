# 3-Statements-Ultra — VS Code Copilot Instructions

> **本文件作用**: 等效于 Claude Code 的 CLAUDE.md + SKILL.md，让 VS Code Copilot 在本项目目录下自动加载三表建模的核心规则。
> **Session 详细指令**: 每个 session 的详细步骤在 `_skill_extracted/references/session-{a,b,c,d,e,f}.md`，需要时手动打开或让 LLM 读取。
> **完整 SKILL.md**: `_skill_extracted/SKILL.md` 包含所有原始规则，本文件是其精简注入版。

---

## 项目概述

使用 **3-statements-ultra v4.7** skill 构建机构级三表模型（IS/BS/CF），
支持 CN GAAP / IFRS / US GAAP，季度/半年/年频自适应。
输出质量目标: IPO 招股书 / 卖方初始覆盖级别。

**9-Session 构建流程:**
```
SESSION A  — Raw_Info + Assumptions           → 读取 _skill_extracted/references/session-a.md
SESSION B  — IS (Income Statement)            → 读取 _skill_extracted/references/session-b.md
SESSION C  — BS (Balance Sheet, Cash=占位)    → 读取 _skill_extracted/references/session-c.md
SESSION D  — CF + 回填 _pending_links         → 读取 _skill_extracted/references/session-d.md
SESSION E  — Returns + Cross_Check + Summary  → 读取 _skill_extracted/references/session-e.md
SESSION F  — DCF Valuation                    → 读取 _skill_extracted/references/session-f.md
SESSION G  — Sensitivity + Scenario           → 读取 _skill_extracted/references/session-g.md
SESSION H  — Comps (可比公司估值分析)       → 读取 _skill_extracted/references/session-h.md
SESSION J  — Valuation_Summary (综合估值)    → 读取 _skill_extracted/references/session-j.md
```

**Excel 文件结构:**
```
[1] Summary        ← 最后构建; 所有数字链接到模型单元格
[2] Assumptions    ← 所有预测驱动因子; 唯一真实来源
[3] IS             ← 利润表
[4] BS             ← 资产负债表
[5] CF             ← 现金流量表 (间接法)
[6] Returns        ← WIND风格 7大类: 盈利/成长/运营/杠杆/现金流质量/DuPont/绝对值
[7] Cross_Check    ← 假设验证 + 修订记录
[8] Raw_Info       ← 源数据提取 (首次构建后不再重读源文件)
[9] DCF            ← WACC计算 + UFCF预测 + Terminal Value + EV→权益桥接 + 敏感性分析
[_Registry]        ← 数据血缘登记
[_State]           ← Session 元数据
```

**辅助文件 (与 Excel 同目录):**
```
_model_log.md        ← 每个 tab section 完成后的检查点 (只追加)
_pending_links.json  ← 延迟跨表引用 (SESSION C 写入, SESSION D 消费)
```

---

## ██ 新项目初始化 ██

为新公司建模时，必须遵循以下步骤：
1. 在 `DCF agent/` 下创建公司目录（如 `DCF agent/<company>/`）
2. 复制 `project_config_template.yaml` → `project_config.yaml`，填写所有 TODO 字段
3. 所有 build 脚本必须从 `shared/` 导入样式、工具函数和配置加载器
4. **禁止**在新 build 脚本中内联定义 `fill()`、`fnt()`、`nv()` 等工具函数
5. 历史项目脚本仅用于参考**业务逻辑**（Block 布局、数据处理流程）
6. `project_config.yaml` 是项目参数的唯一来源

## ██ shared/ 模块导入规则 ██

所有 build 脚本必须从 `shared/` 导入，禁止内联定义样式/工具函数：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import (
    fill, fnt, fnt_yahei, aln, bdr,
    C_BLK, C_COLHDR, C_WHITE, FMT_TEXT, FMT_N2, FMT_PCT,
    write_blk_hdr, write_col_hdrs, write_cell,
    nv, stat, exch,
    read_state, write_state_key,
)
from shared.config_loader import ProjectConfig
cfg = ProjectConfig.from_yaml('project_config.yaml')
```

**遗留脚本注意:** 部分历史 build 脚本（如 `build_comps_sheet.py`）是在 `shared/` 抽取前写的，
仍含内联 `fill()`/`fnt()` 等定义 —— 这些是历史代码，新项目 **不得复制**。

---

## ██ RULE ZERO — 硬编码禁令 ██

**三表模型最常见的致命错误就是硬编码预测单元格。**

```
正确 — 历史单元格:  ws["B5"].value = '=Raw_Info!C12'
正确 — 预测单元格:  ws["E5"].value = '=Assumptions!B8'

错误:  ws["E5"].value = 0.30                     ← 硬编码, 模型已废
错误:  ws["E5"].value = float(revenue * 0.30)    ← 硬编码, 模型已废
错误:  ws["E5"].value = prev_value * growth       ← 硬编码, 模型已废
```

**允许持有硬编码数值的单元格 (仅以下):**
- Assumptions tab 输入行 (蓝色文字, 浅蓝底色) ← 这些就是模型输入
- Raw_Info tab (源数据提取) ← 历史事实
- 列标题、行标签、检查标签

---

## ██ 断点恢复协议 ██

当使用 3-statements-ultra skill 构建三表模型时，
每次发生 context compaction 或开启新对话后，你必须:

1. 重新读取 `_skill_extracted/SKILL.md`，再写任何代码
2. 打开 Excel 文件，读取 `_State` tab，确认精确的恢复点
3. 读取 `_model_log.md`，恢复上一 session 的关键输出数字
4. 读取 `_pending_links.json`，检查 BS→CF 的 Cash 回填是否待处理
5. 用 RAW_MAP + ASM_MAP spot-check 验证行号，再使用任何行号
6. IS/BS/CF 预测列单元格不得硬编码，每个单元格必须是字符串公式
7. 只从下一个未完成步骤继续，不重跑已完成的部分

不得依赖对话记忆来还原行号或中间计算结果。
磁盘状态 (`_State`、`_model_log.md`、`_pending_links.json`) 永远是权威来源。

---

## ██ 代码生成协议 ██

**第二常见致命错误: 一次生成太多代码。**

规则: 每次写一个逻辑单元的代码 → 执行 → 验证输出 → 写检查点到 `_model_log.md` → 再写下一个。

```
每个代码块覆盖一个完整的 tab section:
  IS:  Revenue | COGS+GP | OpEx | EBIT+below+NCI+checks
  BS:  Current Assets | Non-Current Assets | Current Liab | NCL+Equity
  CF:  每年一次循环 (CFO → CFI → CFF → Others → Cash → 回填)
```

- 目标: 200-350 行/代码块
- 上限: **400 行，绝不超过**
- 超过 350 行时在自然边界拆分

---

## ██ 核心规则 (R1-R10) ██

**R1 — 单一来源:** Raw_Info 完成后，不再重读源文件。所有数据经 `=Raw_Info!` 链接。

**R2 — 禁止自由 plug:** 不得用 `= Total_LE − Total_Assets` 强制平衡 BS。
仅允许一个 plug: CFO 的 `Non-cash Adj – Others` (R3)。CN GAAP IS 允许一个 R8 plug。

**R3 — Others plug (非循环):**
```
CF!Others = BS!Total_LE − BS!Total_NCA − SUM(BS!CA_excl_Cash) − BS!Prior_Cash
          − CF!NI − CF!DA − CF!SBC − CF!Impairment − CF!JV
          − CF!WC_Total − CF!CFI_Total − CF!CFF_Total
```
- |Others| ≤ 15% of |CFO| → 接受 ✓
- |Others| > 15% of |CFO| → 存在遗漏的重大现金流项目，需显式建模

**R4 — NCI 必须滚动:** 若历史 NCI ≠ 0，每个预测期都必须滚动:
- `BS NCI_end = Prior + Attr_to_NCI − NCI_Dividends`

**R5 — CF 禁止重复计数:** 利息/税已在 NI 中，预测期不设单独 CFO 行。

**R5b — CFF 历史年 plug (防止重复计数):**
CFF 的 ST/LT/Lease 行用 BS 差额（已包含借/还款净效果）。
`Other CFF` **禁止**拆分源 CF 项（如 `借款收到 - 还款` ）— 会与 BS 差额重复计数。
```
Historical: Other CFF = Raw_Info!{col}{CFF_Net} - {col}{ST_chg} - {col}{LT_chg} - {col}{Lease} - {col}{Div}
Forecast:   Other CFF = 0（或 Assumptions 中的股权融资）
```

**R5c — 受限货币资金调整 (Restricted Cash Reconciliation):**
CN GAAP 下 BS"货币资金"含受限资金，CF"现金及现金等价物"不含。
在 CF 期末现金之后增加调整行，保持三表完整联动：
```
CF!R_EndCash:      = Beg + Net Change              (纯 CF 流量)
CF!R_RestrictAdj:  = Raw_Info!BS_Cash - R_EndCash   (历史) / 0 (预测)
CF!R_TotalCash:    = R_EndCash + R_RestrictAdj      (= 源 BS 货币资金)
CF!R_CHECK:        = R_TotalCash - BS!Cash          (应为 0)
BS!Cash:           = CF!R_TotalCash                 (所有年份统一)
CF!Beg_Cash(yr+1): = BS!Cash(yr)                    (逐年滚动，含受限)
```
如果源数据 BS Cash = CF End Cash（无受限资金），调整行 = 0，不影响任何公式。

**R6 — Cash 最后填:** 所有 BS 项目完成 → CF 按年完成 → `BS!Cash = CF!TotalCash` 立即回填。

**R7 — 每个 BS Δ 都有 CF 归属** (完整映射见 `_skill_extracted/SKILL.md` R7 表格)

**R8 — CN GAAP IS plug:**
```
Historical: Other Op Inc = Source 营业利润 − (Model Rev − COGS − OpEx − Impairment)
Forecast:   % of revenue 或 Assumptions tab 的绝对值
```

**R9 — 五项对账检查 (全部 = 0):**
- `BS CHECK = Total Assets − Total L+E`
- `CF CHECK = Total Cash (= End Cash + Restricted Adj) − BS Cash`
- `NI CHECK = Model NI − Source NI` (季度容差 ±10)
- `REV CHECK = Model Total Revenue − Source Total Revenue`
- `CFF CHECK = Model CFF Total − Source CFF Net` (仅历史年; 容差 ±0.01)

**R10 — 匹配最细披露粒度** (季度/半年/年度自动检测)

---

## ██ 关键公式 ██

```
Revenue:   Sub_curr = Sub_prior × (1 + YoY%)
WC → BS:   AR = Rev × AR_Days/365  |  Inv = COGS × Inv_Days/365  |  AP = COGS × AP_Days/365
CF WC:     Δ Asset = −(curr − prior)  |  Δ Liability = +(curr − prior)
PP&E:      Net = Prior × (1 − Depr_Rate) + |Capex|   ← PP&E 专用折旧率, 非总 D&A
Equity:    Reserves = Prior + Attr_Owners − Div  |  NCI = Prior + Attr_NCI − Div_NCI
CN GAAP:   Other Op Inc = Source 营业利润 − (Rev − COGS − Tax&Surcharge − OpEx − Impairment)
ROIC:      NOPAT / AVERAGE(IC_curr, IC_prior)
```

---

## ██ 债务/利息假设规则 (增强补丁) ██

> 此规则修复了原 skill 中 Finance Cost/Interest Expense 使用常量或静态公式的缺陷。
> 背景: 在某历史模型中曾发现 Finance Cost=常量、Interest Expense=Rate×固定借款额(静态)，
> Interest Income 冻结在 FY2025 水平，导致利息不随借款/现金变化。

### 1. Assumptions 模板规则 — 利率必须拆三个

Session A 的 Assumptions tab 中，【债务与融资】区域必须包含三个独立利率输入:
- **ST Interest Rate%** (短期借款利率)
- **LT Interest Rate%** (长期借款利率)
- **Cash Interest Rate%** (存款利率)

不允许使用单一 "Interest Rate on Debt%" 统一处理所有债务利息。

### 2. IS 公式规则 — 利息必须用期初余额法

IS 的 Finance Cost / Interest Expense / Interest Income 三行，
预测列公式**必须**使用**期初余额法** (Beginning-of-Period approach):

```
Interest Expense = ST_Rate × BS.{prior_col}.ST_Borrowings + LT_Rate × BS.{prior_col}.LT_Payables
Interest Income  = Cash_Rate × BS.{prior_col}.Cash
Finance Cost     = Interest_Expense − Interest_Income
```

**禁止:**
- ❌ 常量值 (`=Assumptions!Bxx` 指向某个固定数字)
- ❌ 静态公式 (Rate × 固定起始年借款额，不随年份变化)
- ❌ 冻结值 (`=上一列同行`，如 `=D44`)

**原因:** 期初余额法避免三表循环引用，同时确保利息随借款/现金变化动态调整。

### 3. QC 增强: 利息合理性检验

Cross_Check 中应增加:
- **INTEREST EXPENSE CHECK**: 每年 Interest Expense 应 ≈ Rate × Prior Year Debt
- **INTEREST MONOTONICITY**: 如果借款逐年递减，Interest Expense 也应逐年递减
- **FINANCE COST DECOMPOSITION**: Finance Cost 应 = Interest Expense − Interest Income (差值 < 0.01)

---

## ██ 高频错误清单 (精简版) ██

### 致命 — 模型静默产出错误数字
1. **[RULE ZERO]** 硬编码预测/历史单元格
2. **混淆裸引用和独立公式** — `f"=D5*(1+=Assumptions!B2)"` 是 Excel 解析错误
3. **用总 D&A 做 PP&E 滚动** — 用 PP&E 专用折旧率; 总 D&A 包含无形资产摊销
4. **预测期 NCI 设为 0** — 始终滚动
5. **利息使用常量或静态公式** — 必须用期初余额法 (见上方债务利息规则)
5b. **CFF Other 拆分源 CF 而非用 plug** — `=借款收到-还款` 与 BS 差额行重复计数; 用 R5b: `Other CFF = 源CFF净额 − 已建模CFF项`

### 严重 — 检查失败或不平
6. **在 CFI/CFF 完成前写 R3 Others** — R3 引用 CFI_Total 和 CFF_Total
7. **不按年回填 BS Cash** — 每年 CF 完成后立即回填
8. **自由 plug 强制平衡 BS** — 仅允许 R3 Others
9. **SESSION C 就验证 BS CHECK** — Cash=占位符时 BS CHECK 不为 0 是正常的

### 数据/来源
10. **Raw_Info 留空** — 下游公式引用空单元格静默返回 0
11. **Raw_Info 完成后仍重读源文件** — 违反 R1
12. **单位不匹配** — 万元 ≠ 千元 ≠ 百万元; 静默 100x 误差

### Session/_State
13. **不写进度标记** — IS_PROGRESS / BS_PROGRESS / CF_PROGRESS 必须每个 section 后写入
14. **跨 session 使用记忆中的行号** — 始终从 _State 读取 RAW_MAP / ASM_MAP 并 spot-check

---

## ██ Session 详细指令 — 按需读取 ██

每个 session 开始时，读取对应的参考文件:

```
SESSION A: 读取 _skill_extracted/references/session-a.md  (11K chars)
SESSION B: 读取 _skill_extracted/references/session-b.md  (6K chars)
SESSION C: 读取 _skill_extracted/references/session-c.md  (8K chars)
SESSION D: 读取 _skill_extracted/references/session-d.md  (13K chars)
SESSION E: 读取 _skill_extracted/references/session-e.md  (18K chars)
SESSION F: 读取 _skill_extracted/references/session-f.md  (10K chars)
SESSION G: 读取 _skill_extracted/references/session-g.md  (12K chars)
SESSION H: 读取 _skill_extracted/references/session-h.md  (6K chars)  ← Comps
SESSION J: 读取 _skill_extracted/references/session-j.md  (4K chars)  ← Valuation_Summary
```

完整规则参考: `_skill_extracted/SKILL.md`

---

## ██ 环境配置 ██

```bash
pip install openpyxl yfinance pandas
pip install tushare        # 可选 — A股首选数据源 (需要 .env 中设置 TUSHARE_TOKEN)
pip install pdfplumber     # 可选 — PDF 本地解析
pip install notebooklm    # 可选 — NotebookLM 数据源
```

Python 3.9+ 必需。A股用户: 在 `.env` 中设置 `TUSHARE_TOKEN`。
