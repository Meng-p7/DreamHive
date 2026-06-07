---
name: dreamhive-status
description: "显示 DreamHive 状态 — 技能数量、最近调用、热门技能"
argument-hint: ""
allowed-tools: [Bash]
---

# /dreamhive status — 显示集群状态

用户调用了 `/dreamhive status`。显示 DreamHive 的当前状态。

## 指令

1. 运行状态命令:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" status
```

2. 将输出直接展示给用户 — 不要总结或重新格式化。

3. 如果索引显示 0 个技能，提醒用户运行:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
```
