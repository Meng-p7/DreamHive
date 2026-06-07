---
name: dreamhive-status
description: "Show DreamHive status — skill count, recent invocations, top skills"
argument-hint: ""
allowed-tools: [Bash]
---

# /dreamhive status — Show Cluster Status

The user invoked `/dreamhive status`. Show DreamHive's current status.

## Instructions

1. Run the status command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" status
```

2. Show the output directly to the user — do not summarize or reformat.

3. If the index shows 0 skills, remind the user to run:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
```
