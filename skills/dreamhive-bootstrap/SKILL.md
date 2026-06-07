---
name: dreamhive-bootstrap
description: "会话启动时自动加载 — 建立 DreamHive 能力和技能调度规则。请勿手动调用。"
version: 1.0.0
---

# DreamHive — 智能技能调度

自动发现、索引、推荐最适合任务的已安装技能，并从使用模式中学习。

## 行为规则

- **复杂任务** → 用 `dreamhive-dispatch` 技能调度最佳技能
- **发现技能** → 运行 `python3 "$DREAMHIVE" suggest "<任务描述>"`
- **记录每次调用** → 运行 `python3 "$DREAMHIVE" invoke "<技能>" ok|fail "<上下文>"`
- **分析模式** → 用户要求优化工作流时，用 `dreamhive-learn`
- **尊重用户** → 用户覆盖推荐时，遵循用户选择并记录

## 命令

`/dreamhive status` · `/dreamhive list` · `/dreamhive suggest` · `/dreamhive learn`
