## 3-Statements-Ultra — 断点恢复协议
当我在使用 3-statements-ultra skill 构建三表模型时，
每次发生 context compaction 后，你必须：
1. 重新读取 3-statements-ultra SKILL.md，再写任何代码
2. 打开 Excel 文件，读取 _State tab，确认精确的恢复点
3. 读取 _model_log.md，恢复上一 session 的关键输出数字
4. 读取 _pending_links.json，检查 BS→CF 的 Cash 回填是否待处理
5. 用 RAW_MAP + ASM_MAP spot-check 验证行号，再使用任何行号
6. IS/BS/CF 预测列单元格不得硬编码，每个单元格必须是字符串公式
7. 只从下一个未完成步骤继续，不重跑已完成的部分
不得依赖对话记忆来还原行号或中间计算结果。
磁盘状态（_State、_model_log.md、_pending_links.json）永远是权威来源。

## 新项目初始化规则
为新公司建模时，必须遵循以下步骤：
1. 在 `DCF agent/` 下创建公司目录（如 `DCF agent/<company>/`）
2. 复制 `project_config_template.yaml` → `project_config.yaml`，填写所有 TODO 字段
3. 所有 build 脚本必须从 `shared/` 导入样式、工具函数和配置加载器
4. **禁止**在 build 脚本中内联定义 `fill()`、`fnt()`、`nv()`、`stat()` 等工具函数
5. 历史项目脚本仅用于参考**业务逻辑**（Block 布局、数据处理流程），不复制其样式代码
6. `project_config.yaml` 是项目参数的唯一来源——公司名、同行列表、行号、权重等不得硬编码在脚本中

## shared/ 模块导入模板
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

## 9-Session 构建流程
```
SESSION A  — Raw_Info + Assumptions
SESSION B  — IS
SESSION C  — BS (Cash 占位)
SESSION D  — CF + 回填 Cash
SESSION E  — Returns + Cross_Check + Summary
SESSION F  — DCF Valuation
SESSION G  — Sensitivity + Scenario
SESSION H  — Comps (可比公司估值)        → 读取 _skill_extracted/references/session-h.md
SESSION J  — Valuation_Summary (综合估值) → 读取 _skill_extracted/references/session-j.md
```

## 债务/利息假设规则 (增强补丁)
1. **Assumptions 利率拆三个**: ST Interest Rate%、LT Interest Rate%、Cash Interest Rate%，不允许单一利率
2. **IS 利息用期初余额法**:
   - `Interest Expense = ST_Rate × BS.{prior_col}.ST_Borrowings + LT_Rate × BS.{prior_col}.LT_Payables`
   - `Interest Income  = Cash_Rate × BS.{prior_col}.Cash`
   - `Finance Cost     = Interest_Expense − Interest_Income`
3. **禁止**: 常量值、静态公式 (Rate × 固定年份借款)、冻结值 (`=上一列同行`)
4. **QC**: Cross_Check 应验证 Interest Expense ≈ Rate × Prior Year Debt

## VS Code Copilot 用户
VS Code Copilot 不会自动读取本文件。
等效指令在 `DCF agent/.github/copilot-instructions.md`，Copilot 会自动加载。
