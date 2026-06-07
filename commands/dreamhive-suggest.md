---
name: dreamhive-suggest
description: "根据当前任务或给定查询推荐最相关的 3 个技能"
argument-hint: "[查询 — 如果为空，使用当前对话上下文]"
allowed-tools: [Bash]
---

# /dreamhive suggest — 推荐技能

用户调用了 `/dreamhive suggest`。查找并推荐最相关的技能。

## 指令

1. **确定查询内容。** 如果用户提供了 `$ARGUMENTS`，将其作为查询。
   如果没有参数，分析当前对话确定用户在做什么，将其作为查询
   （例如 "调试 Python 测试失败"、"部署 Docker 容器"、"编写 API 端点"）。

2. 运行推荐引擎:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" suggest "<查询>"
```

3. 展示结果。

4. 对每个推荐的技能，提供调用选项:
   - 如果用户说 "使用 <技能名>"，通过 Skill 工具调用该技能。
   - 如果用户说 "全部使用"，按顺序调用（最高推荐优先）。

5. 调用任何技能后，记录调用:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" invoke "<技能名>" ok "自动推荐用于: <查询>"
```
