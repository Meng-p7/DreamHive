---
name: dreamhive-list
description: "列出 DreamHive 已索引的所有技能，按来源分组"
argument-hint: "[过滤词]"
allowed-tools: [Bash]
---

# /dreamhive list — 列出所有已索引技能

用户调用了 `/dreamhive list`。显示集群索引中的所有技能。

## 指令

1. 运行列表命令:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" list
```

2. 将输出直接展示给用户。

3. 如果用户通过 `$ARGUMENTS` 提供了过滤词，运行:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" list | grep -i "$ARGUMENTS"
```

4. 如果索引为空，建议运行:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
```
