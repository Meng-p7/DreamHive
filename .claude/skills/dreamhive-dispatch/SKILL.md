---
name: dreamhive-dispatch
description: "Use when a user's task could benefit from installed skills — auto-dispatches the most relevant skills, supports chaining multiple skills"
---

# Cluster Dispatch — Intelligent Skill Routing

## When to Activate

- Task is complex and could benefit from specialized skills
- Unsure which skill to use
- Task involves multiple steps requiring different skills

## Dispatch Flow

1. **Split task** — Break user request into sub-tasks, identify required capabilities
2. **Query recommendations** — For each sub-task, run `python3 "$DREAMHIVE" suggest "<sub-task description>"`
3. **Select & execute** — Pick the highest-scoring match, invoke via Skill tool
4. **Chain outputs** — Pass previous step's output as context to the next step
5. **Record results** — After each invocation, run `python3 "$DREAMHIVE" invoke "<skill>" ok|fail "<context>"`

## Dispatch Rules

- Max 3 skills per task — don't over-dispatch
- Skip skills quickly if they don't fit — don't force a match
- When user overrides a recommendation, follow their choice and record it
