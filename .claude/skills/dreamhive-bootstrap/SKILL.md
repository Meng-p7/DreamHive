---
name: dreamhive-bootstrap
description: "Auto-loaded at session start — establishes DreamHive capabilities and skill dispatch rules. Do not invoke manually."
version: 1.0.0
---

# DreamHive — Intelligent Skill Dispatch

Auto-discovers, indexes, and recommends the best installed skills for each task, and learns from usage patterns.

## Behavior Rules

- **Complex tasks** → use `dreamhive-dispatch` skill to route to best skills
- **Discover skills** → run `python3 "$DREAMHIVE" suggest "<task description>"`
- **Record every invocation** → run `python3 "$DREAMHIVE" invoke "<skill>" ok|fail "<context>"`
- **Analyze patterns** → when user asks to optimize workflows, use `dreamhive-learn`
- **Respect user choices** → when user overrides a recommendation, follow their choice and record it

## Commands

`/dreamhive status` · `/dreamhive list` · `/dreamhive suggest` · `/dreamhive learn`
