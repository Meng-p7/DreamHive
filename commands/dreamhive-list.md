---
name: dreamhive-list
description: "List all skills indexed by DreamHive, grouped by source"
argument-hint: "[filter]"
allowed-tools: [Bash]
---

# /dreamhive list — List All Indexed Skills

The user invoked `/dreamhive list`. Display all skills in the cluster index.

## Instructions

1. Run the list command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" list
```

2. Show the output directly to the user.

3. If the user provided a filter via `$ARGUMENTS`, run:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" list | grep -i "$ARGUMENTS"
```

4. If the index is empty, suggest running:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
```
