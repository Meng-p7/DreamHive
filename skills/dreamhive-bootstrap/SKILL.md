---
name: dreamhive-bootstrap
description: "会话启动时自动加载 — 建立 DreamHive 能力和技能调度规则。请勿手动调用。"
version: 1.0.0
---

# 🐝 DreamHive — 智能技能调度

你已启用 **DreamHive** —— 一个智能调度层，可自动发现、索引和推荐
最适合每个任务的技能。

## DreamHive 的功能

当用户安装了大量 skill 时，很难知道该用哪个。DreamHive 通过以下方式解决：

1. **索引** — 会话启动时索引所有已安装的技能
2. **推荐** — 为每个任务推荐最相关的 Top-3 技能
3. **追踪** — 记录每次调用（成功/失败）用于学习
4. **学习** — 从重复模式中建议创建新的组合技能
5. **串联** — 将多个技能串联执行复杂工作流

## 快速参考

| 命令                | 功能                                    |
|---------------------|-----------------------------------------|
| `/dreamhive status`     | 显示技能数、最近调用、热门技能            |
| `/dreamhive list`       | 按来源分组列出所有已索引技能              |
| `/dreamhive suggest`    | 为当前任务推荐 Top-3 技能                |
| `/dreamhive learn`      | 分析模式，建议创建新的组合技能            |

## 使用方法

### 自动调度

对于任何复杂任务，DreamHive 可以自动找到并调用最佳技能。
当任务可能受益于专业技能时，使用 `dreamhive-dispatch` 技能。

### 手动发现

查看某个任务有哪些可用技能：

```
/dreamhive suggest 部署 Docker 容器到 AWS
```

### 技能串联

对于多步骤任务，集群会串联技能：

```
用户: "构建一个新的 API 端点并编写测试"
集群: plan → implement → test → review (串联 4 个技能)
```

### 从模式中学习

随着时间推移，集群会检测重复的技能序列，并通过
`/dreamhive learn` 建议创建组合技能。

## CLI 访问

所有集群操作都可通过 Python 引擎访问：

```bash
DREAMHIVE="${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py"

python3 "$DREAMHIVE" index              # 重建技能索引
python3 "$DREAMHIVE" invoke <skill> ok  # 记录调用
python3 "$DREAMHIVE" suggest "查询"     # 获取推荐
python3 "$DREAMHIVE" learn              # 分析模式
python3 "$DREAMHIVE" generate <N>       # 生成组合技能
```

## 集成说明

- 使用 **Skill 工具** 调用技能（与手动调用相同）
- 使用 **Bash** 运行 Python 引擎进行索引和分析
- 通过 **SessionStart** 钩子自动重建索引
- 不会替换或冲突任何已安装的技能
