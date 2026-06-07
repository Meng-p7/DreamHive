#!/usr/bin/env python3
"""
DreamHive — Core Engine
========================
Index skills, track invocations, detect patterns, generate skill suggestions.
Called by Claude Code hooks and slash commands via CLI.

Usage:
    python3 dreamhive.py index                     # Scan and rebuild skill index
    python3 dreamhive.py invoke <skill> [ok|fail]  # Record a skill invocation
    python3 dreamhive.py status                    # Show cluster status
    python3 dreamhive.py list                      # List all indexed skills
    python3 dreamhive.py suggest <query>           # Recommend Top-3 skills for a query
    python3 dreamhive.py learn                     # Analyze patterns, suggest new skills
    python3 dreamhive.py stats <skill>             # Show usage stats for a skill
"""

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

# ── Path Configuration ────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INDEX_FILE = DATA_DIR / "skill-index.json"
HISTORY_FILE = DATA_DIR / "invocation-history.json"
PATTERNS_FILE = DATA_DIR / "learned-patterns.json"

# Skill search paths (ordered by priority)
SKILL_SEARCH_PATHS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".claude" / "plugins" / "cache",
]

def ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── Index Management ──────────────────────────────────────────────────────

def parse_skill_frontmatter(skill_path: Path) -> dict:
    """Extract YAML frontmatter from a SKILL.md file."""
    try:
        content = skill_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return {}

    # Match YAML frontmatter between --- delimiters
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    meta = {}
    block = match.group(1)
    for key in ('name', 'description', 'version'):
        # Match key: "quoted value" or key: 'quoted value' or key: unquoted value
        m = re.search(
            rf'^{key}:\s*(?:"([^"]*)"|\'([^\']*)\'|(.*\S))',
            block, re.MULTILINE
        )
        if m:
            meta[key] = m.group(1) or m.group(2) or m.group(3).strip()
    return meta


def detect_source(skill_path: Path) -> str:
    """Detect plugin source by walking up to find .claude-plugin/plugin.json."""
    current = skill_path.parent
    for _ in range(10):  # Limit traversal depth
        manifest = current / ".claude-plugin" / "plugin.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text())
                return data.get("name", "unknown")
            except (json.JSONDecodeError, OSError):
                pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    return "user"


def scan_skills() -> list[dict]:
    """Scan all skill search paths and return a list of skill descriptors."""
    skills = []
    seen_names = set()

    for search_path in SKILL_SEARCH_PATHS:
        if not search_path.exists():
            continue

        # Recursively find all SKILL.md files
        for skill_file in search_path.rglob("SKILL.md"):
            # Skip overly deep paths (avoid scanning node_modules etc.)
            rel = skill_file.relative_to(search_path)
            if len(rel.parts) > 6:
                continue

            meta = parse_skill_frontmatter(skill_file)
            name = meta.get("name", skill_file.parent.name)

            # Deduplicate by name (higher-priority paths scanned first)
            if name in seen_names:
                continue
            seen_names.add(name)

            # Detect source from plugin manifest
            source = detect_source(skill_file)

            # Extract keywords from description and skill name
            desc = meta.get("description", "")
            keywords = extract_keywords(desc)
            # Name parts are high-value keywords
            # e.g. "systematic-debugging" → ["systematic", "debugging"]
            for part in name.lower().replace('_', '-').split('-'):
                if len(part) > 2 and part not in keywords:
                    keywords.append(part)

            skills.append({
                "name": name,
                "description": desc,
                "version": meta.get("version", ""),
                "path": str(skill_file),
                "source": source,
                "keywords": keywords,
            })

    return skills


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a description text."""
    if not text:
        return []

    # Common stop words (filtered out)
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
        'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
        'once', 'this', 'that', 'these', 'those', 'and', 'but', 'or', 'nor',
        'not', 'so', 'very', 'just', 'than', 'too', 'also', 'about', 'when',
        'where', 'how', 'what', 'which', 'who', 'whom', 'whose', 'why', 'if',
        'because', 'while', 'although', 'until', 'unless', 'since', 'each',
        'every', 'all', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'only', 'own', 'same', 'it', 'its', 'he', 'she', 'they', 'them',
        'his', 'her', 'my', 'your', 'our', 'me', 'you', 'him', 'us', 'i',
        'use', 'using', 'used', 'user', 'tool', 'command', 'skill', 'agent',
    }

    # Extract words, lowercase, filter stop words
    words = re.findall(r'[a-z][a-z0-9_-]{2,}', text.lower())
    keywords = [w for w in words if w not in stop_words]

    # Extract quoted phrases as high-value keywords
    quoted = re.findall(r'"([^"]+)"', text)
    for phrase in quoted:
        keywords.append(phrase.lower())

    return list(dict.fromkeys(keywords))  # Preserve order, deduplicate


# ── TF-IDF Scoring ───────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase word tokens for TF-IDF."""
    if not text:
        return []
    return re.findall(r'[a-z][a-z0-9_-]+', text.lower())


def compute_doc_freq(skills: list[dict]) -> tuple:
    """Build document frequency table and per-skill token lists for TF-IDF."""
    df = Counter()
    doc_tokens = {}
    for skill in skills:
        text = skill.get("description", "") + " " + " ".join(skill.get("keywords", []))
        tokens = tokenize(text)
        doc_tokens[skill["name"]] = tokens
        for term in set(tokens):
            df[term] += 1
    return dict(df), doc_tokens


def tfidf_similarity(query_tokens: list, doc_tokens: list, df: dict, n_docs: int) -> float:
    """Compute cosine similarity between query and document using TF-IDF."""
    if not query_tokens or not doc_tokens:
        return 0.0

    query_tf = Counter(query_tokens)
    doc_tf = Counter(doc_tokens)
    all_terms = set(query_tf.keys()) | set(doc_tf.keys())

    dot = 0.0
    q_mag = 0.0
    d_mag = 0.0

    for term in all_terms:
        idf = math.log2(n_docs / (df.get(term, 0) + 0.5)) + 1.0
        q_val = query_tf.get(term, 0) * idf
        d_val = doc_tf.get(term, 0) * idf
        dot += q_val * d_val
        q_mag += q_val * q_val
        d_mag += d_val * d_val

    mag = math.sqrt(q_mag) * math.sqrt(d_mag)
    return dot / mag if mag else 0.0


def build_index():
    """Scan skills and write the index file."""
    ensure_data_dir()
    skills = scan_skills()

    # Load existing index to preserve call counts
    existing = load_index()
    existing_map = {s["name"]: s for s in existing.get("skills", [])}

    # Merge call counts from existing data
    for skill in skills:
        if skill["name"] in existing_map:
            old = existing_map[skill["name"]]
            skill["call_count"] = old.get("call_count", 0)
            skill["last_called"] = old.get("last_called", "")
            skill["success_count"] = old.get("success_count", 0)
            skill["fail_count"] = old.get("fail_count", 0)
        else:
            skill["call_count"] = 0
            skill["last_called"] = ""
            skill["success_count"] = 0
            skill["fail_count"] = 0

    index = {
        "version": 2,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "total_skills": len(skills),
        "skills": skills,
    }

    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    return index


def load_index() -> dict:
    """Load the skill index from disk."""
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": 2, "skills": [], "total_skills": 0}


# ── Invocation Tracking ───────────────────────────────────────────────────

ARCHIVE_PATTERN = "invocation-history-*.json"


def record_invocation(skill_name: str, result: str = "ok", context: str = ""):
    """Record a skill invocation to the history log."""
    ensure_data_dir()
    history = load_history()

    entry = {
        "skill": skill_name,
        "result": result,
        "context": context[:200],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history["entries"].append(entry)

    # Archive old entries if buffer exceeds 500
    if len(history["entries"]) > 500:
        history = _archive_old_entries(history)

    history["total_invocations"] = len(history["entries"])
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    # Update stats in the index
    update_skill_stats(skill_name, result)


def _archive_old_entries(history: dict) -> dict:
    """Move entries from previous months to monthly archive files."""
    entries = history.get("entries", [])
    if not entries:
        return history

    # Determine current month from the latest entry
    try:
        latest = datetime.fromisoformat(entries[-1]["timestamp"].replace('Z', '+00:00'))
        current_month = latest.strftime("%Y-%m")
    except (ValueError, KeyError):
        return history

    # Split: current month stays, older entries grouped by month
    current_entries = []
    by_month = {}
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
            month = ts.strftime("%Y-%m")
        except (ValueError, KeyError):
            month = current_month

        if month == current_month:
            current_entries.append(entry)
        else:
            by_month.setdefault(month, []).append(entry)

    # Write each month group to its archive file
    for month, month_entries in by_month.items():
        archive_file = DATA_DIR / f"invocation-history-{month}.json"
        if archive_file.exists():
            try:
                existing = json.loads(archive_file.read_text())
                existing_entries = existing.get("entries", [])
            except (json.JSONDecodeError, OSError):
                existing_entries = []
        else:
            existing_entries = []

        # Merge and deduplicate by (timestamp, skill, context)
        seen = {(e.get("timestamp",""), e.get("skill",""), e.get("context","")) for e in existing_entries}
        for e in month_entries:
            key = (e.get("timestamp",""), e.get("skill",""), e.get("context",""))
            if key not in seen:
                existing_entries.append(e)
                seen.add(key)
        existing_entries.sort(key=lambda e: e.get("timestamp", ""))

        archive = {"version": 1, "month": month, "entries": existing_entries}
        archive_file.write_text(json.dumps(archive, indent=2, ensure_ascii=False))

    history["entries"] = current_entries
    return history


def load_history(months_back: int = 0) -> dict:
    """Load invocation history.

    Args:
        months_back: How many months of history to load.
            0 = current active file only (default, fast)
            N = active file + last N archive months
           -1 = all archives + active file (full history)
    """
    entries = []

    # Load archive files if requested
    if months_back != 0:
        archive_files = sorted(DATA_DIR.glob(ARCHIVE_PATTERN))
        if months_back > 0:
            # Keep only the N most recent archive files
            archive_files = archive_files[-months_back:]
        for f in archive_files:
            try:
                data = json.loads(f.read_text())
                entries.extend(data.get("entries", []))
            except (json.JSONDecodeError, OSError):
                pass

    # Load active file
    if HISTORY_FILE.exists():
        try:
            active = json.loads(HISTORY_FILE.read_text())
            entries.extend(active.get("entries", []))
        except (json.JSONDecodeError, OSError):
            pass

    # Sort by timestamp
    entries.sort(key=lambda e: e.get("timestamp", ""))

    return {"version": 1, "entries": entries, "total_invocations": len(entries)}


def update_skill_stats(skill_name: str, result: str):
    """Update call count for a specific skill in the index."""
    index = load_index()
    for skill in index.get("skills", []):
        if skill["name"] == skill_name:
            skill["call_count"] = skill.get("call_count", 0) + 1
            skill["last_called"] = datetime.now(timezone.utc).isoformat()
            if result == "ok":
                skill["success_count"] = skill.get("success_count", 0) + 1
            else:
                skill["fail_count"] = skill.get("fail_count", 0) + 1
            break
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False))


# ── Dispatch / Recommendation ─────────────────────────────────────────────

def suggest_skills(query: str, top_n: int = 3) -> list[dict]:
    """
    Recommend the most relevant skills for a given query.
    Uses a hybrid scoring method:
      1. Keyword overlap (with substring tolerance)
      2. Name matching
      3. TF-IDF cosine similarity
      4. Substring hits in description
      5. Usage frequency bonus
    """
    index = load_index()
    skills = index.get("skills", [])

    if not skills:
        return []

    query_lower = query.lower()
    query_words = set(extract_keywords(query_lower))
    # Keep raw words for substring matching
    raw_words = set(re.findall(r'[a-z]{3,}', query_lower))

    # Pre-compute TF-IDF corpus data (once for all skills)
    n_docs = len(skills)
    df, doc_tokens_map = compute_doc_freq(skills)
    query_tokens = tokenize(query_lower)

    scored = []
    for skill in skills:
        score = 0.0
        name = skill.get("name", "")
        desc = skill.get("description", "").lower()
        keywords = set(skill.get("keywords", []))

        # --- Score 1: Keyword overlap with substring tolerance (0-40) ---
        if query_words and keywords:
            # Exact overlap
            intersection = query_words & keywords
            # Substring matching (e.g. "debug" matches "debugging")
            substring_matches = set()
            for qw in query_words:
                for kw in keywords:
                    if qw in kw or kw in qw:
                        substring_matches.add(qw)
                        break
            effective_overlap = len(intersection | substring_matches)
            union_size = len(query_words)  # Normalize by query size
            jaccard = effective_overlap / union_size if union_size else 0
            score += jaccard * 40

        # --- Score 2: Name match bonus (0-25) ---
        # Direct name mention is a strong signal
        if name.lower() in query_lower:
            score += 25
        else:
            # Check if query words are substrings of name parts, or vice versa
            # e.g. "debug" (query) vs "debugging" (name); "TDD" (query) vs "test" (name)
            name_parts = [p for p in name.lower().replace('_', '-').split('-') if len(p) > 2]
            name_hit = False
            for part in name_parts:
                if part in query_lower:
                    name_hit = True
                    break
                for qw in raw_words:
                    if qw in part or part in qw:
                        name_hit = True
                        break
                if name_hit:
                    break
            if name_hit:
                score += 18
            # Partial name match (original logic, lower weight)
            elif any(part in query_lower for part in name_parts):
                score += 10

        # --- Score 3: TF-IDF cosine similarity (0-20) ---
        skill_tokens = doc_tokens_map.get(name, [])
        tfidf_sim = tfidf_similarity(query_tokens, skill_tokens, df, n_docs)
        score += tfidf_sim * 20

        # --- Score 4: Substring hits in description (0-10) ---
        hits = 0
        for w in raw_words:
            if w in desc:
                hits += 1
            else:
                # Check if description words contain query words, or vice versa
                for dw in desc.split():
                    if w in dw or dw in w:
                        hits += 1
                        break
        if raw_words:
            score += (hits / len(raw_words)) * 10

        # --- Score 5: Usage frequency bonus (0-5) ---
        call_count = skill.get("call_count", 0)
        if call_count > 0:
            score += min(5, math.log2(call_count + 1))

        scored.append({
            "name": name,
            "description": skill.get("description", ""),
            "score": round(score, 2),
            "call_count": skill.get("call_count", 0),
            "path": skill.get("path", ""),
        })

    # Sort by score descending, break ties by call count
    scored.sort(key=lambda s: (-s["score"], -s["call_count"]))

    return scored[:top_n]


# ── Pattern Learning ──────────────────────────────────────────────────────

def analyze_patterns() -> dict:
    """
    Analyze invocation history to find repeated skill sequences.
    Returns detected patterns and suggestions for new composite skills.
    """
    history = load_history(months_back=3)
    entries = history.get("entries", [])

    if len(entries) < 3:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 3 invocations to analyze patterns, currently have {len(entries)}.",
            "patterns": [],
            "suggestions": [],
        }

    # ── Detect sequential patterns (skills called in order) ──
    # Group by session (gap ≤ 30 minutes = same session)
    sessions = []
    current_session = []
    for i, entry in enumerate(entries):
        if i == 0:
            current_session.append(entry)
            continue
        try:
            prev_time = datetime.fromisoformat(entries[i-1]["timestamp"].replace('Z', '+00:00'))
            curr_time = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
            gap = (curr_time - prev_time).total_seconds()
        except (ValueError, KeyError):
            gap = 999999

        if gap > 1800:  # 30-minute gap = new session
            if current_session:
                sessions.append(current_session)
            current_session = [entry]
        else:
            current_session.append(entry)
    if current_session:
        sessions.append(current_session)

    # Extract skill sequences from sessions
    sequence_counter = Counter()
    for session in sessions:
        skill_seq = tuple(e["skill"] for e in session if e.get("skill"))
        if len(skill_seq) >= 2:
            # Count all subsequences of length 2 and 3
            for window_size in (2, 3):
                for i in range(len(skill_seq) - window_size + 1):
                    subseq = skill_seq[i:i + window_size]
                    sequence_counter[subseq] += 1

    # ── Detect high-frequency skills ──
    skill_counter = Counter()
    for entry in entries:
        skill_counter[entry.get("skill", "")] += 1

    # ── Build pattern list ──
    patterns = []
    for seq, count in sequence_counter.most_common(10):
        if count >= 2:  # At least 2 occurrences
            patterns.append({
                "type": "sequence",
                "skills": list(seq),
                "count": count,
                "label": " → ".join(seq),
            })

    # ── Build suggestions ──
    suggestions = []
    for pattern in patterns:
        if pattern["count"] >= 3:  # Threshold for suggesting a new skill
            skills_list = pattern["skills"]
            suggestion = {
                "type": "composite_skill",
                "trigger_count": pattern["count"],
                "skills_chain": skills_list,
                "suggested_name": f"auto-{'-'.join(skills_list[:3])}",
                "suggested_description": f"Automated chain: {' → '.join(skills_list)}. "
                                        f"Detected {pattern['count']} times in recent sessions.",
            }
            suggestions.append(suggestion)

    # ── Detect unused skills ──
    index = load_index()
    all_skills = {s["name"] for s in index.get("skills", [])}
    used_skills = set(skill_counter.keys())
    never_used = all_skills - used_skills

    result = {
        "status": "ok",
        "total_invocations": len(entries),
        "total_sessions": len(sessions),
        "unique_skills_used": len(used_skills),
        "total_skills_indexed": len(all_skills),
        "top_skills": [
            {"name": name, "count": count}
            for name, count in skill_counter.most_common(10)
        ],
        "patterns": patterns,
        "suggestions": suggestions,
        "never_used_count": len(never_used),
        "never_used_sample": list(never_used)[:10],
    }

    return result


def generate_skill_file(suggestion: dict) -> str:
    """
    Generate a new composite SKILL.md file from a pattern suggestion.
    Returns the path where the file was written.
    """
    skills_chain = suggestion.get("skills_chain", [])
    name = suggestion.get("suggested_name", "auto-composite")
    desc = suggestion.get("suggested_description", "")

    # Load descriptions for each skill in the chain
    index = load_index()
    skill_map = {s["name"]: s for s in index.get("skills", [])}

    steps = []
    for i, skill_name in enumerate(skills_chain, 1):
        skill_info = skill_map.get(skill_name, {})
        skill_desc = skill_info.get("description", f"Execute {skill_name}")
        steps.append(f"{i}. Invoke `{skill_name}` — {skill_desc}")

    content = f"""---
name: {name}
description: "{desc}"
version: 1.0.0
---

# {name}

Auto-generated composite skill by DreamHive.

## Use Case

This skill was auto-detected because the following sequence appeared
{suggestion.get('trigger_count', '?')} times in recent sessions:

{' → '.join(skills_chain)}

## Steps

{chr(10).join(steps)}

## Notes

- This skill is auto-generated. Review and customize as needed.
- Each step's output is passed as context to the next step.
- Edit: modify this file directly, or regenerate via `/dreamhive learn`.
"""

    # Write to user skills directory
    user_skills_dir = Path.home() / ".claude" / "skills" / name
    user_skills_dir.mkdir(parents=True, exist_ok=True)
    skill_path = user_skills_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")

    return str(skill_path)


# ── Status & Formatting ───────────────────────────────────────────────────

def format_status() -> str:
    """Format a human-readable status report."""
    index = load_index()
    history = load_history()
    patterns = load_patterns()

    total_skills = index.get("total_skills", 0)
    total_invocations = history.get("total_invocations", 0)
    built_at = index.get("built_at", "never")

    # Most recent 10 invocations
    recent = history.get("entries", [])[-10:]
    recent_lines = []
    for entry in recent:
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        skill = entry.get("skill", "?")
        result = entry.get("result", "?")
        icon = "✓" if result == "ok" else "✗"
        recent_lines.append(f"  {icon} {skill:30s}  {ts}")

    # Most-used skills
    top_skills = sorted(
        index.get("skills", []),
        key=lambda s: s.get("call_count", 0),
        reverse=True
    )[:5]
    top_lines = []
    for s in top_skills:
        count = s.get("call_count", 0)
        if count > 0:
            top_lines.append(f"  {s['name']:30s}  {count} calls")

    # Pattern count
    pattern_count = len(patterns.get("patterns", []))

    lines = [
        "╔══════════════════════════════════════════════╗",
        "║         🐝  DreamHive Status               ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Skills indexed:   {total_skills:>6}                    ║",
        f"║  Total invocations:{total_invocations:>6}                    ║",
        f"║  Patterns detected:{pattern_count:>6}                    ║",
        f"║  Index built at: {built_at[:19]}    ║",
        "╠══════════════════════════════════════════════╣",
    ]

    if top_lines:
        lines.append("║  Top skills:                                  ║")
        for line in top_lines:
            lines.append(f"║  {line:44s}║")
        lines.append("╠══════════════════════════════════════════════╣")

    if recent_lines:
        lines.append("║  Recent invocations:                          ║")
        for line in recent_lines:
            lines.append(f"║  {line:44s}║")

    lines.append("╚══════════════════════════════════════════════╝")
    return "\n".join(lines)


def format_list() -> str:
    """Format the skill list."""
    index = load_index()
    skills = index.get("skills", [])

    if not skills:
        return "No skills indexed yet. Run: python3 dreamhive.py index"

    lines = [
        f"🐝 DreamHive — {len(skills)} skills indexed",
        "=" * 60,
        "",
    ]

    # Group by source
    by_source = {}
    for s in skills:
        src = s.get("source", "unknown")
        by_source.setdefault(src, []).append(s)

    for source, group in sorted(by_source.items()):
        lines.append(f"📦 {source} ({len(group)} skills)")
        lines.append("-" * 40)
        for s in sorted(group, key=lambda x: x["name"]):
            calls = s.get("call_count", 0)
            desc = s.get("description", "")[:60]
            call_str = f"[{calls}x]" if calls > 0 else ""
            lines.append(f"  {s['name']:35s} {call_str:>8s}  {desc}")
        lines.append("")

    return "\n".join(lines)


def format_suggestions(query: str) -> str:
    """Format skill recommendation results (compact mode)."""
    suggestions = suggest_skills(query)

    if not suggestions:
        return "No skills indexed yet. Run: python3 dreamhive.py index"

    lines = [
        f"🐝 DreamHive — Best matches for \"{query}\"",
        "=" * 60,
        "",
    ]

    for i, s in enumerate(suggestions, 1):
        lines.append(f"  #{i}  {s['name']}  ({s['score']}pts, {s['call_count']}x)")

    return "\n".join(lines)


def format_learn_results() -> str:
    """Format pattern analysis results."""
    result = analyze_patterns()

    if result["status"] == "insufficient_data":
        return (
            f"🐝 DreamHive — Learn\n"
            f"{'=' * 40}\n\n"
            f"  {result['message']}\n\n"
            f"  Keep using skills and run this command later."
        )

    lines = [
        f"🐝 DreamHive — Pattern Analysis",
        "=" * 60,
        f"  Total invocations:  {result['total_invocations']}",
        f"  Sessions analyzed:  {result['total_sessions']}",
        f"  Skills used: {result['unique_skills_used']} / {result['total_skills_indexed']}",
        "",
    ]

    # Top skills
    if result.get("top_skills"):
        lines.append("📊 Most used skills:")
        for s in result["top_skills"][:5]:
            lines.append(f"  {s['name']:30s}  {s['count']}x")
        lines.append("")

    # Patterns
    if result.get("patterns"):
        lines.append("🔗 Detected patterns:")
        for p in result["patterns"]:
            lines.append(f"  {p['label']:50s}  ({p['count']}x)")
        lines.append("")

    # Suggestions
    if result.get("suggestions"):
        lines.append("💡 Suggested composite skills:")
        for i, s in enumerate(result["suggestions"], 1):
            lines.append(f"  #{i}  {s['suggested_name']}")
            lines.append(f"      Chain: {' → '.join(s['skills_chain'])}")
            lines.append(f"      Triggered: {s['trigger_count']}x")
        lines.append("")
        lines.append("  To auto-generate a suggested skill, run:")
        lines.append(f"  python3 {Path(__file__).resolve()} generate <number>")
    else:
        lines.append("  No repeated patterns detected yet (requires ≥3 occurrences).")

    # Unused skills
    if result.get("never_used_count", 0) > 0:
        lines.append("")
        lines.append(f"💤 {result['never_used_count']} skills have never been invoked.")
        if result.get("never_used_sample"):
            for name in result["never_used_sample"][:5]:
                lines.append(f"  - {name}")

    return "\n".join(lines)


def load_patterns() -> dict:
    """Load learned patterns from disk."""
    if PATTERNS_FILE.exists():
        try:
            return json.loads(PATTERNS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"patterns": [], "suggestions": []}


# ── CLI Entry Point ───────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "index":
        index = build_index()
        print(f"🐝 Indexed {index['total_skills']} skills from {len(SKILL_SEARCH_PATHS)} search paths")
        print(f"   Index saved to: {INDEX_FILE}")

    elif command == "invoke":
        if len(sys.argv) < 3:
            print("Usage: dreamhive.py invoke <skill-name> [ok|fail] [context]")
            sys.exit(1)
        skill_name = sys.argv[2]
        result = sys.argv[3] if len(sys.argv) > 3 else "ok"
        context = sys.argv[4] if len(sys.argv) > 4 else ""
        record_invocation(skill_name, result, context)
        print(f"✓ Recorded: {skill_name} ({result})")

    elif command == "status":
        print(format_status())

    elif command == "list":
        print(format_list())

    elif command == "suggest":
        if len(sys.argv) < 3:
            print("Usage: dreamhive.py suggest <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        print(format_suggestions(query))

    elif command == "learn":
        print(format_learn_results())

    elif command == "generate":
        if len(sys.argv) < 3:
            print("Usage: dreamhive.py generate <number>")
            sys.exit(1)
        result = analyze_patterns()
        suggestions = result.get("suggestions", [])
        idx = int(sys.argv[2]) - 1
        if 0 <= idx < len(suggestions):
            path = generate_skill_file(suggestions[idx])
            print(f"✓ Generated composite skill: {path}")
        else:
            print(f"Invalid suggestion number. Valid range: 1-{len(suggestions)}")

    elif command == "stats":
        if len(sys.argv) < 3:
            print("Usage: dreamhive.py stats <skill-name>")
            sys.exit(1)
        skill_name = sys.argv[2]
        index = load_index()
        for s in index.get("skills", []):
            if s["name"] == skill_name:
                print(json.dumps(s, indent=2, ensure_ascii=False))
                return
        print(f"Skill '{skill_name}' not found in index.")

    elif command == "json-status":
        # Machine-readable output for hooks
        index = load_index()
        history = load_history()
        output = {
            "total_skills": index.get("total_skills", 0),
            "total_invocations": history.get("total_invocations", 0),
            "recent_skills": [
                e["skill"] for e in history.get("entries", [])[-5:]
            ],
        }
        print(json.dumps(output))

    elif command == "json-suggest":
        # Machine-readable suggestions for hooks
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        suggestions = suggest_skills(query)
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
