---
name: dreamhive-suggest
description: "Recommend the top 3 most relevant skills for the current task or a given query"
argument-hint: "[query — if empty, uses current conversation context]"
allowed-tools: [Bash]
---

# /dreamhive suggest — Recommend Skills

The user invoked `/dreamhive suggest`. Find and recommend the most relevant skills.

## Instructions

1. **Determine the query.** If the user provided `$ARGUMENTS`, use that as the query.
   If no arguments, analyze the current conversation to determine what the user is doing
   and use that as the query (e.g. "debug Python test failure", "deploy Docker container",
   "write API endpoint").

2. Run the recommendation engine:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" suggest "<query>"
```

3. Show the results.

4. For each recommended skill, offer invocation options:
   - If the user says "use <skill-name>", invoke it via the Skill tool.
   - If the user says "use all", invoke them in order (highest recommendation first).

5. After invoking any skill, record the invocation:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" invoke "<skill-name>" ok "auto-recommended for: <query>"
```
