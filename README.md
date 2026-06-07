# 🐝 DreamHive — Claude Code 智能技能调度

**解决技能过载问题。** 当你安装了几十个 skill 时，Claude 不知道该用哪个。
DreamHive 自动发现、索引、推荐最适合每个任务的技能 —— 并从你的使用模式中学习。

## ✨ 功能特性

- **🔍 自动发现** — 每次会话启动时扫描 `~/.claude/skills/` 和所有插件
- **🎯 智能调度** — 关键词匹配 + 模糊搜索 + 使用频率 → Top-3 推荐
- **🔗 技能串联** — 自动将多个技能串联执行复杂任务
- **📊 调用追踪** — 记录每次调用（成功/失败）用于学习
- **🧠 模式学习** — 检测重复的技能序列，建议创建组合技能
- **⚡ 零配置** — 开箱即用，无需任何设置

## 📦 安装方式

### 方式一：从 GitHub 安装

```bash
claude plugin install dreamhive
```

### 方式二：从本地路径安装

```bash
claude plugin install --path ~/dreamhive
```

### 方式三：开发模式（单次会话加载）

```bash
claude --plugin-dir ~/dreamhive
```

## 🚀 快速开始

安装后打开新的 Claude Code 会话，你会看到：

```
🐝 DreamHive 已激活：已索引 42 个技能，共 0 次调用。
```

### 发现适合任务的技能

```
/dreamhive suggest 审查代码并修复 bug
```

输出示例：
```
🐝 DreamHive — "审查代码并修复 bug" 的最佳匹配
============================================================

  #1  requesting-code-review  (得分: 35.2, 已调用 12x)
      在 PR 上请求代码审查的触发条件

  #2  systematic-debugging  (得分: 28.7, 已调用 8x)
      四阶段根因调试：先理解问题再修复

  #3  test-driven-development  (得分: 18.3, 已调用 5x)
      强制红-绿-重构，先写测试再写代码
```

### 查看集群状态

```
/dreamhive status
```

输出示例：
```
╔══════════════════════════════════════════════╗
║         🐝  DreamHive 状态                 ║
╠══════════════════════════════════════════════╣
║  已索引技能:           42                    ║
║  总调用次数:          156                    ║
║  检测到的模式:          3                    ║
╠══════════════════════════════════════════════╣
║  热门技能:                                    ║
║    systematic-debugging            24次       ║
║    writing-plans                   18次       ║
║    requesting-code-review          15次       ║
╚══════════════════════════════════════════════╝
```

### 从使用模式中学习

```
/dreamhive learn
```

输出示例：
```
🐝 DreamHive — 模式分析
============================================================
  总调用次数:  156
  分析的会话数:  23
  已使用的技能: 15 / 42

🔗 检测到的模式:
  systematic-debugging → test-driven-development → github-pr-workflow  (4次)
  writing-plans → systematic-debugging  (3次)

💡 建议创建的组合技能:
  #1  auto-debugging-tdd-pr
      链路: systematic-debugging → test-driven-development → github-pr-workflow
      触发次数: 4

  如需自动生成建议的技能，运行:
  python3 dreamhive.py generate <建议编号>
```

## 📋 命令参考

| 命令 | 说明 |
|------|------|
| `/dreamhive status` | 仪表盘：技能数、调用次数、热门技能 |
| `/dreamhive list [过滤词]` | 列出所有已索引的技能，可选过滤 |
| `/dreamhive suggest [查询]` | 为任务推荐 Top-3 技能 |
| `/dreamhive learn [generate N]` | 分析模式，生成组合技能 |

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────┐
│                   用户请求                        │
│          "帮我修复这个测试失败"                     │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│            DreamHive 调度层                     │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │  分析任务  │→ │  推荐Top3 │→ │  通过Skill   │  │
│  │           │  │           │  │  工具执行     │  │
│  └───────────┘  └───────────┘  └──────┬──────┘  │
│                                 ┌──────┴──────┐  │
│  ┌───────────┐  ┌───────────┐  │             │  │
│  │  记录结果  │← │  学习模式  │←─┘             │  │
│  └───────────┘  └───────────┘                  │
└─────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              已安装的技能                          │
│  ~/.claude/skills/*  +  插件技能                  │
│  systematic-debugging, writing-plans, ...        │
└─────────────────────────────────────────────────┘
```

## 🧠 评分算法

每个技能获得一个综合得分（0-100），基于以下维度：

| 维度 | 权重 | 方法 |
|------|------|------|
| 关键词重叠 | 0-40 分 | Jaccard 相似度 + 双向子串匹配 |
| 名称匹配 | 0-25 分 | 查询中直接/间接包含技能名称 |
| 文本相似度 | 0-10 分 | SequenceMatcher 模糊匹配描述 |
| 子串命中 | 0-10 分 | 查询词在技能描述中的命中率 |
| 使用频率 | 0-5 分 | log2(调用次数) — 热门技能小幅加分 |

## 📁 文件结构

```
dreamhive/
├── .claude-plugin/
│   └── plugin.json              # 插件清单
├── hooks/
│   ├── hooks.json               # 钩子配置
│   └── session-start            # SessionStart 钩子（重建索引）
├── scripts/
│   └── dreamhive.py                 # 核心引擎（CLI）
├── skills/
│   ├── dreamhive-bootstrap/
│   │   └── SKILL.md             # 会话启动时注入的能力说明
│   ├── dreamhive-dispatch/
│   │   └── SKILL.md             # 智能调度技能
│   └── dreamhive-learn/
│       └── SKILL.md             # 学习与进化技能
├── commands/
│   ├── dreamhive-status.md          # /dreamhive status
│   ├── dreamhive-list.md            # /dreamhive list
│   ├── dreamhive-suggest.md         # /dreamhive suggest
│   └── dreamhive-learn.md           # /dreamhive learn
├── agents/
│   └── dreamhive-orchestrator.md    # 调度 Agent 定义
├── data/                        # 持久化状态（自动生成）
│   ├── skill-index.json         # 技能目录 + 统计
│   ├── invocation-history.json  # 调用日志（最近 500 条）
│   └── learned-patterns.json    # 检测到的使用模式
├── LICENSE                      # MIT 许可证
└── README.md                    # 本文档
```

## 🔧 开发指南

### 手动重建索引

```bash
python3 ~/dreamhive/scripts/dreamhive.py index
```

### 手动记录调用

```bash
python3 ~/dreamhive/scripts/dreamhive.py invoke "my-skill" ok "用于处理 X"
```

### 测试推荐效果

```bash
python3 ~/dreamhive/scripts/dreamhive.py suggest "调试 Python 测试"
```

### 验证插件结构

```bash
claude plugin validate ~/dreamhive
```

## 📝 工作原理

1. **会话启动**：`session-start` 钩子运行 `dreamhive.py index`，扫描
   `~/.claude/skills/` 和所有插件技能目录。读取每个 `SKILL.md` 的
   前置元数据，构建可搜索的索引。

2. **对话过程中**：当用户提出任务时，Claude 可以调用 `dreamhive-dispatch`
   技能，该技能调用 `dreamhive.py suggest "<查询>"` 找到最匹配的技能。
   Python 引擎使用混合评分算法，结合关键词重叠、名称匹配、文本相似度
   和使用历史。

3. **执行后**：每次技能调用通过 `dreamhive.py invoke` 记录，逐步积累历史
   数据，用于优化未来的推荐和模式检测。

4. **学习进化**：`dreamhive learn` 命令分析调用历史，找出重复的技能序列。
   当同一序列出现 3 次以上时，建议创建一个自动化该链路的组合技能。

## 🤝 贡献指南

欢迎贡献！主要改进方向：

- 更好的评分算法（TF-IDF、基于嵌入的相似度）
- 更多模式检测策略
- 状态/列表输出的 UI 改进
- 与其他插件市场的集成

## 📄 许可证

MIT — 详见 [LICENSE](LICENSE)
