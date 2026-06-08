---
name: dreamhive-learn
description: "Use when the user wants to improve the cluster, create new skills from patterns, or when you detect a repeated task sequence that could be automated"
---

# Cluster Learning — Self-Evolution System

DreamHive learns from usage patterns and can suggest creating new composite skills.

## When to Activate

- User asks to "improve skills", "learn from history", or "optimize workflows"
- You notice the user is repeating the same operation sequence
- User does the same thing twice and says "create a skill for this"
- User invokes `/dreamhive learn`

## How It Works

### Automatic Pattern Detection

The cluster tracks every skill invocation and detects:
- **Sequential patterns**: Skill A → B → C repeatedly used together
- **Frequency patterns**: Some skills used far more than others
- **Context patterns**: Skills always used in similar contexts

### Threshold: 3 Repetitions

When a pattern appears ≥3 times, the cluster flags it for skill creation.

### Skill Generation Flow

1. **Analyze** — Run the learn command:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" learn
   ```

2. **Review** — Show detected patterns and suggestions to the user.

3. **Generate** — If user agrees, generate the composite skill:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" generate <number>
   ```

4. **Customize** — Read the generated skill and suggest improvements:
   - Better description
   - Add preconditions or guards
   - Add error handling steps
   - Rename to something more descriptive

5. **Register** — Re-index to include the new skill:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
   ```

## Proactive Learning

You can also suggest creating skills without being asked:

1. After completing a multi-step task, check if similar patterns exist
2. If you notice you've done "X then Y" multiple times in this session, say:
   > "I noticed we've done [X → Y] a few times. Want me to create a composite skill to do it in one step next time?"

3. If the user agrees, generate a skill with appropriate name and description from the actual task context.

## Recording Invocations

Every skill use should be recorded for learning:

```bash
# Success
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" invoke "skill-name" ok "what was done"

# Failure
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" invoke "skill-name" fail "why it failed"
```

This data drives future recommendations and pattern detection.
