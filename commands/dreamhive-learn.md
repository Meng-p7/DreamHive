---
name: dreamhive-learn
description: "分析调用历史，检测模式并建议创建新的组合技能"
argument-hint: "[generate <编号>]"
allowed-tools: [Bash, Read, Write]
---

# /dreamhive learn — 分析模式与进化

用户调用了 `/dreamhive learn`。分析技能使用模式，根据重复序列
建议创建新的组合技能。

## 指令

### 模式一：分析（默认）

如果没有参数或 `$ARGUMENTS` 为空:

1. 运行模式分析:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" learn
```

2. 将结果展示给用户。

3. 如果有可用建议，询问用户:
   > "检测到一个重复模式。要我为建议 #N 自动生成组合技能吗？
   > 回复编号，或 'all' 生成全部。"

4. 用户选择编号后，切换到模式二。

### 模式二：生成（当 $ARGUMENTS 以 "generate" 开头时）

1. 从 `$ARGUMENTS` 中提取建议编号（例如 "generate 1" → 1）。

2. 运行生成器:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" generate <编号>
```

3. 显示生成的文件路径。

4. 读取生成的文件并向用户展示内容。

5. 提供自定义选项 — 编辑描述、重命名、添加上下文等。

6. 生成后，运行 `index` 以纳入新技能:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
```
