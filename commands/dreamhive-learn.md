---
name: dreamhive-learn
description: "Analyze invocation history, detect patterns, and suggest creating new composite skills"
argument-hint: "[generate <number>]"
allowed-tools: [Bash, Read, Write]
---

# /dreamhive learn — Pattern Analysis & Evolution

The user invoked `/dreamhive learn`. Analyze skill usage patterns and suggest
creating new composite skills based on repeated sequences.

## Instructions

### Mode 1: Analyze (default)

If no arguments or `$ARGUMENTS` is empty:

1. Run pattern analysis:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" learn
```

2. Show the results to the user.

3. If suggestions are available, ask the user:
   > "A repeated pattern was detected. Want me to auto-generate a composite
   > skill for suggestion #N? Reply with the number, or 'all' to generate all."

4. Once the user chooses a number, switch to Mode 2.

### Mode 2: Generate (when $ARGUMENTS starts with "generate")

1. Extract the suggestion number from `$ARGUMENTS` (e.g. "generate 1" → 1).

2. Run the generator:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" generate <number>
```

3. Show the generated file path.

4. Read the generated file and show its contents to the user.

5. Offer customization options — edit description, rename, add context, etc.

6. After generation, run `index` to include the new skill:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dreamhive.py" index
```
