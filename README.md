# 🐝 DreamHive — Intelligent Skill Dispatch for Claude Code

**Solves skill overload.** When you install dozens of skills, Claude doesn't know which one to use.
DreamHive auto-discovers, indexes, and recommends the best skill for each task — and learns from your usage patterns.

> 📖 [中文文档](README_ZH.md)

## ✨ Features

- **🔍 Auto-discovery** — Scans `~/.claude/skills/` and all plugins at session start
- **🎯 Smart dispatch** — Keyword matching + fuzzy search + usage frequency → Top-3 recommendations
- **🔗 Skill chaining** — Automatically chains multiple skills for complex tasks
- **📊 Invocation tracking** — Records every call (success/failure) for learning
- **🧠 Pattern learning** — Detects repeated skill sequences, suggests creating composite skills
- **⚡ Zero config** — Works out of the box, no setup needed

## 📦 Installation

### Option 1: Development mode (recommended, instant)

```bash
claude --plugin-dir ~/DreamHive
```

### Option 2: Install from marketplace

```bash
claude plugin marketplace add https://github.com/Meng-p7/DreamHive
claude plugin install dreamhive@dreamhive-marketplace
```

> Open a new Claude Code session after installation to activate.

## 🚀 Quick Start

After installation, open a new Claude Code session and you'll see:

```
🐝 DreamHive active: 42 skills indexed, 0 invocations.
```

### Discover skills for a task

```
/dreamhive suggest review code and fix bugs
```

Example output:
```
🐝 DreamHive — Best matches for "review code and fix bugs"
============================================================

  #1  requesting-code-review  (35.2pts, 12x)
  #2  systematic-debugging  (28.7pts, 8x)
  #3  test-driven-development  (18.3pts, 5x)
```

### View cluster status

```
/dreamhive status
```

Example output:
```
╔══════════════════════════════════════════════╗
║         🐝  DreamHive Status               ║
╠══════════════════════════════════════════════╣
║  Skills indexed:        42                    ║
║  Total invocations:    156                    ║
║  Patterns detected:      3                    ║
╠══════════════════════════════════════════════╣
║  Top skills:                                  ║
║    systematic-debugging            24 calls    ║
║    writing-plans                   18 calls    ║
║    requesting-code-review          15 calls    ║
╚══════════════════════════════════════════════╝
```

### Learn from usage patterns

```
/dreamhive learn
```

Example output:
```
🐝 DreamHive — Pattern Analysis
============================================================
  Total invocations:  156
  Sessions analyzed:  23
  Skills used: 15 / 42

🔗 Detected patterns:
  systematic-debugging → test-driven-development → github-pr-workflow  (4x)
  writing-plans → systematic-debugging  (3x)

💡 Suggested composite skills:
  #1  auto-debugging-tdd-pr
      Chain: systematic-debugging → test-driven-development → github-pr-workflow
      Triggered: 4x

  To auto-generate a suggested skill, run:
  python3 ~/DreamHive/scripts/dreamhive.py generate <number>
```

## 📋 Command Reference

| Command | Description |
|---------|-------------|
| `/dreamhive status` | Dashboard: skill count, invocations, top skills |
| `/dreamhive list [filter]` | List all indexed skills, with optional filter |
| `/dreamhive suggest [query]` | Recommend Top-3 skills for a task |
| `/dreamhive learn [generate N]` | Analyze patterns, generate composite skills |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                   User Request                    │
│          "Help me fix this test failure"          │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│            DreamHive Dispatch Layer              │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐  │
│  │  Analyze   │→ │  Top-3    │→ │  Execute     │  │
│  │  Task      │  │  Recommend│  │  via Skill   │  │
│  └───────────┘  └───────────┘  └──────┬──────┘  │
│                                 ┌──────┴──────┐  │
│  ┌───────────┐  ┌───────────┐  │             │  │
│  │  Record   │← │  Learn    │←─┘             │  │
│  │  Result   │  │  Patterns │                  │  │
│  └───────────┘  └───────────┘                  │
└─────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              Installed Skills                     │
│  ~/.claude/skills/*  +  plugin skills            │
│  systematic-debugging, writing-plans, ...        │
└─────────────────────────────────────────────────┘
```

## 🧠 Scoring Algorithm

Each skill receives a composite score (0-100) based on:

| Dimension | Weight | Method |
|-----------|--------|--------|
| Keyword overlap | 0-40 pts | Jaccard similarity + bidirectional substring matching |
| Name matching | 0-25 pts | Direct/indirect skill name presence in query |
| Text similarity | 0-20 pts | SequenceMatcher fuzzy match on description |
| Substring hits | 0-10 pts | Query word hit rate in skill description |
| Usage frequency | 0-5 pts | log2(call_count) — popular skills get a small boost |

## 📁 File Structure

```
DreamHive/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest
│   └── marketplace.json         # Marketplace listing
├── hooks/
│   ├── hooks.json               # Hook configuration
│   └── session-start            # SessionStart hook (rebuilds index)
├── scripts/
│   └── dreamhive.py             # Core engine (CLI)
├── skills/
│   ├── dreamhive-bootstrap/
│   │   └── SKILL.md             # Capability description injected at startup
│   ├── dreamhive-dispatch/
│   │   └── SKILL.md             # Intelligent dispatch skill
│   └── dreamhive-learn/
│       └── SKILL.md             # Learning & evolution skill
├── commands/
│   ├── dreamhive-status.md      # /dreamhive status
│   ├── dreamhive-list.md        # /dreamhive list
│   ├── dreamhive-suggest.md     # /dreamhive suggest
│   └── dreamhive-learn.md       # /dreamhive learn
├── agents/
│   └── dreamhive-orchestrator.md # Orchestrator agent definition
├── data/                        # Persistent state (auto-generated)
│   ├── skill-index.json         # Skill catalog + stats
│   ├── invocation-history.json  # Invocation log (last 500)
│   └── learned-patterns.json    # Detected usage patterns
├── README.md                    # This document
├── README_ZH.md                 # Chinese documentation
└── LICENSE                      # MIT License
```

## 🔧 Developer Guide

### Rebuild index manually

```bash
python3 ~/DreamHive/scripts/dreamhive.py index
```

### Record an invocation manually

```bash
python3 ~/DreamHive/scripts/dreamhive.py invoke "my-skill" ok "used for X"
```

### Test recommendation quality

```bash
python3 ~/DreamHive/scripts/dreamhive.py suggest "debug Python tests"
```

### Validate plugin structure

```bash
claude plugin validate ~/DreamHive
```

## 📝 How It Works

1. **Session start**: The `session-start` hook runs `dreamhive.py index`, scanning
   `~/.claude/skills/` and all plugin skill directories. It reads each `SKILL.md`'s
   frontmatter and builds a searchable index.

2. **During conversation**: When the user presents a task, Claude can invoke the
   `dreamhive-dispatch` skill, which calls `dreamhive.py suggest "<query>"` to find
   the best match. The Python engine uses a hybrid scoring algorithm combining
   keyword overlap, name matching, text similarity, and usage history.

3. **After execution**: Each skill invocation is recorded via `dreamhive.py invoke`,
   gradually building history data to improve future recommendations and pattern detection.

4. **Learning & evolution**: The `dreamhive learn` command analyzes invocation history
   to find repeated skill sequences. When the same sequence appears 3+ times, it
   suggests creating a composite skill that automates the chain.

## 🤝 Contributing

Contributions welcome! Key improvement areas:

- Better scoring algorithms (TF-IDF, embedding-based similarity)
- More pattern detection strategies
- UI improvements for status/list output
- Integration with other plugin marketplaces

## 📝 Changelog

### v1.0.2 — Context Optimization

- **Lean bootstrap skill** — Compressed from ~2,600 to ~800 bytes (-69%), removed usage examples, CLI reference, and integration notes while preserving core behavior rules
- **Compact suggest output** — Each recommended skill reduced from 3 lines to 1 (name + score + call count); Claude reads full skill descriptions on demand
- **Lean dispatch skill** — Compressed from ~2,400 to ~1,000 bytes (-57%), removed bash code examples and redundant explanations
- **SessionStart context reduced from ~900 to ~360 tokens** (-60%)

### v1.0.1 — Reliability Fixes

- **Fixed SessionStart hook JSON escaping** — Replaced manual bash string substitution with Python `json.dumps()`, eliminating risk of invalid JSON from special characters (quotes, backslashes, newlines, control characters)
- **Improved YAML frontmatter parsing** — Correctly handles quoted values and colons within values (e.g. `description: "Use when: starting work"`), improving skill index accuracy
- **Fixed `learn generate` command path** — Unified all CLI paths in docs and output to full absolute paths, users can copy-paste directly
- **Fixed scoring algorithm docs** — Text similarity score now matches code (0-20 pts)

### v1.0.0 — Initial Release

- Skill auto-discovery and indexing
- Hybrid scoring recommendation engine (Top-3)
- Invocation tracking (success/failure)
- Pattern detection and composite skill generation
- SessionStart hook for automatic index rebuild
- Slash commands: status, list, suggest, learn

## 📄 License

MIT — see [LICENSE](LICENSE)
