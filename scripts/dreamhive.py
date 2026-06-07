#!/usr/bin/env python3
"""
DreamHive — 核心引擎
======================
索引技能、追踪调用、检测模式、生成技能建议。
通过 CLI 被 Claude Code 钩子和斜杠命令调用。

用法:
    python3 dreamhive.py index                     # 扫描并重建技能索引
    python3 dreamhive.py invoke <skill> [ok|fail]  # 记录一次技能调用
    python3 dreamhive.py status                    # 显示集群状态
    python3 dreamhive.py list                      # 列出所有已索引技能
    python3 dreamhive.py suggest <query>           # 为查询推荐 Top-3 技能
    python3 dreamhive.py learn                     # 分析模式，建议新技能
    python3 dreamhive.py stats <skill>             # 显示某个技能的使用统计
"""

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter

# ── 路径配置 ──────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INDEX_FILE = DATA_DIR / "skill-index.json"
HISTORY_FILE = DATA_DIR / "invocation-history.json"
PATTERNS_FILE = DATA_DIR / "learned-patterns.json"

# 技能搜索路径（按优先级排序）
SKILL_SEARCH_PATHS = [
    Path.home() / ".claude" / "skills",
    Path.home() / ".claude" / "plugins" / "cache",
]

def ensure_data_dir():
    """创建数据目录（如果不存在）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── 索引管理 ─────────────────────────────────────────────────────────────

def parse_skill_frontmatter(skill_path: Path) -> dict:
    """从 SKILL.md 文件中提取 YAML 前置元数据。"""
    try:
        content = skill_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return {}

    # 匹配 --- 分隔符之间的 YAML 前置元数据
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    meta = {}
    block = match.group(1)
    for key in ('name', 'description', 'version'):
        # 匹配 key: "quoted value" 或 key: 'quoted value' 或 key: unquoted value
        m = re.search(
            rf'^{key}:\s*(?:"([^"]*)"|\'([^\']*)\'|(.*\S))',
            block, re.MULTILINE
        )
        if m:
            meta[key] = m.group(1) or m.group(2) or m.group(3).strip()
    return meta


def scan_skills() -> list[dict]:
    """扫描所有技能搜索路径，返回技能描述列表。"""
    skills = []
    seen_names = set()

    for search_path in SKILL_SEARCH_PATHS:
        if not search_path.exists():
            continue

        # 递归查找所有 SKILL.md 文件
        for skill_file in search_path.rglob("SKILL.md"):
            # 跳过过深的路径（避免扫描 node_modules 等）
            rel = skill_file.relative_to(search_path)
            if len(rel.parts) > 6:
                continue

            meta = parse_skill_frontmatter(skill_file)
            name = meta.get("name", skill_file.parent.name)

            # 按名称去重（优先级高的路径先扫描）
            if name in seen_names:
                continue
            seen_names.add(name)

            # 判断来源（插件名或 "user"）
            source = "user"
            rel_str = str(rel)
            # 对于 plugins/cache/ 下的技能，提取插件名
            # 例如 superpowers-marketplace/superpowers/5.1.0/skills/foo/SKILL.md
            if search_path.name == "cache" and "plugins" in str(search_path):
                parts = list(rel.parts)
                if len(parts) >= 2:
                    source = parts[1]  # 例如 "superpowers"
            elif search_path.name == "skills":
                source = "user"

            # 从描述和技能名称中提取关键词
            desc = meta.get("description", "")
            keywords = extract_keywords(desc)
            # 将技能名称各部分也作为高价值关键词
            # 例如 "systematic-debugging" → ["systematic", "debugging"]
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
    """从描述文本中提取有意义的关键词。"""
    if not text:
        return []

    # 常见停用词（过滤掉）
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

    # 提取单词、转小写、过滤停用词
    words = re.findall(r'[a-z][a-z0-9_-]{2,}', text.lower())
    keywords = [w for w in words if w not in stop_words]

    # 提取引号中的短语作为高价值关键词
    quoted = re.findall(r'"([^"]+)"', text)
    for phrase in quoted:
        keywords.append(phrase.lower())

    return list(dict.fromkeys(keywords))  # 保持顺序，去重


def build_index():
    """扫描技能并写入索引文件。"""
    ensure_data_dir()
    skills = scan_skills()

    # 加载已有索引以保留调用计数
    existing = load_index()
    existing_map = {s["name"]: s for s in existing.get("skills", [])}

    # 合并已有数据的调用计数
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
    """从磁盘加载技能索引。"""
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": 2, "skills": [], "total_skills": 0}


# ── 调用追踪 ─────────────────────────────────────────────────────────────

def record_invocation(skill_name: str, result: str = "ok", context: str = ""):
    """记录一次技能调用到历史日志。"""
    ensure_data_dir()
    history = load_history()

    entry = {
        "skill": skill_name,
        "result": result,  # "ok" 或 "fail"
        "context": context[:200],  # 截断以节省存储
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    history["entries"].append(entry)

    # 只保留最近 500 条记录
    if len(history["entries"]) > 500:
        history["entries"] = history["entries"][-500:]

    history["total_invocations"] = len(history["entries"])
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    # 更新索引中的统计信息
    update_skill_stats(skill_name, result)


def load_history() -> dict:
    """加载调用历史。"""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": 1, "entries": [], "total_invocations": 0}


def update_skill_stats(skill_name: str, result: str):
    """更新索引中指定技能的调用计数。"""
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


# ── 调度 / 推荐 ─────────────────────────────────────────────────────────

def suggest_skills(query: str, top_n: int = 3) -> list[dict]:
    """
    为给定查询推荐最相关的技能。
    使用混合评分方法：
      1. 关键词重叠（含子串容错）
      2. 名称匹配
      3. 描述文本相似度
      4. 使用频率加成
    """
    index = load_index()
    skills = index.get("skills", [])

    if not skills:
        return []

    query_lower = query.lower()
    query_words = set(extract_keywords(query_lower))
    # 保留原始单词用于子串匹配
    raw_words = set(re.findall(r'[a-z]{3,}', query_lower))

    scored = []
    for skill in skills:
        score = 0.0
        name = skill.get("name", "")
        desc = skill.get("description", "").lower()
        keywords = set(skill.get("keywords", []))

        # --- 评分 1: 关键词重叠（含子串容错）(0-40 分) ---
        if query_words and keywords:
            # 精确重叠
            intersection = query_words & keywords
            # 子串匹配（例如 "debug" 匹配 "debugging"）
            substring_matches = set()
            for qw in query_words:
                for kw in keywords:
                    if qw in kw or kw in qw:
                        substring_matches.add(qw)
                        break
            effective_overlap = len(intersection | substring_matches)
            union_size = len(query_words)  # 按查询大小归一化
            jaccard = effective_overlap / union_size if union_size else 0
            score += jaccard * 40

        # --- 评分 2: 名称匹配加分 (0-25 分) ---
        # 直接提及名称是强信号
        if name.lower() in query_lower:
            score += 25
        else:
            # 检查查询词是否为名称各部分的子串，或反之
            # 例如 "debug" (查询) vs "debugging" (名称)；"TDD" (查询) vs "test" (名称)
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
            # 部分名称匹配（原始逻辑，降低权重）
            elif any(part in query_lower for part in name_parts):
                score += 10

        # --- 评分 3: 描述文本相似度 (0-20 分) ---
        sim = SequenceMatcher(None, query_lower[:100], desc[:100]).ratio()
        score += sim * 20

        # --- 评分 4: 描述中的子串命中 (0-10 分) ---
        hits = 0
        for w in raw_words:
            if w in desc:
                hits += 1
            else:
                # 检查描述中的词是否包含查询词，或反之
                for dw in desc.split():
                    if w in dw or dw in w:
                        hits += 1
                        break
        if raw_words:
            score += (hits / len(raw_words)) * 10

        # --- 评分 5: 使用频率加成 (0-5 分) ---
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

    # 按得分降序排列，得分相同时按调用次数排序
    scored.sort(key=lambda s: (-s["score"], -s["call_count"]))

    return scored[:top_n]


# ── 模式学习 ─────────────────────────────────────────────────────────────

def analyze_patterns() -> dict:
    """
    分析调用历史，找出重复的技能序列。
    返回检测到的模式和新组合技能的建议。
    """
    history = load_history()
    entries = history.get("entries", [])

    if len(entries) < 3:
        return {
            "status": "insufficient_data",
            "message": f"需要至少 3 次调用才能分析模式，当前有 {len(entries)} 次。",
            "patterns": [],
            "suggestions": [],
        }

    # ── 检测顺序模式（按顺序调用的技能）──
    # 按会话分组（间隔 30 分钟以内算同一会话）
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

        if gap > 1800:  # 30 分钟间隔 = 新会话
            if current_session:
                sessions.append(current_session)
            current_session = [entry]
        else:
            current_session.append(entry)
    if current_session:
        sessions.append(current_session)

    # 从会话中提取技能序列
    sequence_counter = Counter()
    for session in sessions:
        skill_seq = tuple(e["skill"] for e in session if e.get("skill"))
        if len(skill_seq) >= 2:
            # 统计长度为 2 和 3 的所有子序列
            for window_size in (2, 3):
                for i in range(len(skill_seq) - window_size + 1):
                    subseq = skill_seq[i:i + window_size]
                    sequence_counter[subseq] += 1

    # ── 检测高频技能 ──
    skill_counter = Counter()
    for entry in entries:
        skill_counter[entry.get("skill", "")] += 1

    # ── 构建模式列表 ──
    patterns = []
    for seq, count in sequence_counter.most_common(10):
        if count >= 2:  # 至少出现两次
            patterns.append({
                "type": "sequence",
                "skills": list(seq),
                "count": count,
                "label": " → ".join(seq),
            })

    # ── 构建建议 ──
    suggestions = []
    for pattern in patterns:
        if pattern["count"] >= 3:  # 建议创建新技能的阈值
            skills_list = pattern["skills"]
            suggestion = {
                "type": "composite_skill",
                "trigger_count": pattern["count"],
                "skills_chain": skills_list,
                "suggested_name": f"auto-{'-'.join(skills_list[:3])}",
                "suggested_description": f"自动化链路: {' → '.join(skills_list)}。"
                                        f"在最近的会话中检测到 {pattern['count']} 次。",
            }
            suggestions.append(suggestion)

    # ── 检测未使用的技能 ──
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
    根据模式建议生成新的组合 SKILL.md 文件。
    返回文件写入路径。
    """
    skills_chain = suggestion.get("skills_chain", [])
    name = suggestion.get("suggested_name", "auto-composite")
    desc = suggestion.get("suggested_description", "")

    # 加载链路中每个技能的描述
    index = load_index()
    skill_map = {s["name"]: s for s in index.get("skills", [])}

    steps = []
    for i, skill_name in enumerate(skills_chain, 1):
        skill_info = skill_map.get(skill_name, {})
        skill_desc = skill_info.get("description", f"执行 {skill_name}")
        steps.append(f"{i}. 调用 `{skill_name}` — {skill_desc}")

    content = f"""---
name: {name}
description: "{desc}"
version: 1.0.0
---

# {name}

由 DreamHive 自动生成的组合技能。

## 使用场景

此技能被自动检测到，因为以下序列在最近的会话中出现了
{suggestion.get('trigger_count', '?')} 次:

{' → '.join(skills_chain)}

## 执行步骤

{chr(10).join(steps)}

## 注意事项

- 此技能为自动生成，请根据需要审查和自定义。
- 每一步的输出会作为下一步的输入。
- 编辑: 直接修改此文件，或通过 `/dreamhive learn` 重新生成。
"""

    # 写入用户技能目录
    user_skills_dir = Path.home() / ".claude" / "skills" / name
    user_skills_dir.mkdir(parents=True, exist_ok=True)
    skill_path = user_skills_dir / "SKILL.md"
    skill_path.write_text(content, encoding="utf-8")

    return str(skill_path)


# ── 状态与格式化 ─────────────────────────────────────────────────────────

def format_status() -> str:
    """格式化人类可读的状态报告。"""
    index = load_index()
    history = load_history()
    patterns = load_patterns()

    total_skills = index.get("total_skills", 0)
    total_invocations = history.get("total_invocations", 0)
    built_at = index.get("built_at", "从未")

    # 最近 10 次调用
    recent = history.get("entries", [])[-10:]
    recent_lines = []
    for entry in recent:
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        skill = entry.get("skill", "?")
        result = entry.get("result", "?")
        icon = "✓" if result == "ok" else "✗"
        recent_lines.append(f"  {icon} {skill:30s}  {ts}")

    # 使用次数最多的技能
    top_skills = sorted(
        index.get("skills", []),
        key=lambda s: s.get("call_count", 0),
        reverse=True
    )[:5]
    top_lines = []
    for s in top_skills:
        count = s.get("call_count", 0)
        if count > 0:
            top_lines.append(f"  {s['name']:30s}  调用 {count}次")

    # 模式数量
    pattern_count = len(patterns.get("patterns", []))

    lines = [
        "╔══════════════════════════════════════════════╗",
        "║         🐝  DreamHive 状态                 ║",
        "╠══════════════════════════════════════════════╣",
        f"║  已索引技能:      {total_skills:>6}                    ║",
        f"║  总调用次数:      {total_invocations:>6}                    ║",
        f"║  检测到的模式:    {pattern_count:>6}                    ║",
        f"║  索引构建时间: {built_at[:19]}    ║",
        "╠══════════════════════════════════════════════╣",
    ]

    if top_lines:
        lines.append("║  热门技能:                                    ║")
        for line in top_lines:
            lines.append(f"║  {line:44s}║")
        lines.append("╠══════════════════════════════════════════════╣")

    if recent_lines:
        lines.append("║  最近调用:                                    ║")
        for line in recent_lines:
            lines.append(f"║  {line:44s}║")

    lines.append("╚══════════════════════════════════════════════╝")
    return "\n".join(lines)


def format_list() -> str:
    """格式化技能列表。"""
    index = load_index()
    skills = index.get("skills", [])

    if not skills:
        return "尚未索引任何技能。运行: python3 dreamhive.py index"

    lines = [
        f"🐝 DreamHive — 已索引 {len(skills)} 个技能",
        "=" * 60,
        "",
    ]

    # 按来源分组
    by_source = {}
    for s in skills:
        src = s.get("source", "unknown")
        by_source.setdefault(src, []).append(s)

    for source, group in sorted(by_source.items()):
        lines.append(f"📦 {source} ({len(group)} 个技能)")
        lines.append("-" * 40)
        for s in sorted(group, key=lambda x: x["name"]):
            calls = s.get("call_count", 0)
            desc = s.get("description", "")[:60]
            call_str = f"[{calls}次]" if calls > 0 else ""
            lines.append(f"  {s['name']:35s} {call_str:>8s}  {desc}")
        lines.append("")

    return "\n".join(lines)


def format_suggestions(query: str) -> str:
    """格式化技能推荐结果。"""
    suggestions = suggest_skills(query)

    if not suggestions:
        return "尚未索引任何技能。运行: python3 dreamhive.py index"

    lines = [
        f"🐝 DreamHive — \"{query}\" 的最佳匹配",
        "=" * 60,
        "",
    ]

    for i, s in enumerate(suggestions, 1):
        lines.append(f"  #{i}  {s['name']}  (得分: {s['score']}, 已调用 {s['call_count']}次)")
        desc = s.get("description", "")
        if desc:
            # 自动换行
            words = desc.split()
            line = "      "
            for word in words:
                if len(line) + len(word) + 1 > 58:
                    lines.append(line)
                    line = "      " + word
                else:
                    line += " " + word if line.strip() else "      " + word
            if line.strip():
                lines.append(line)
        lines.append("")

    return "\n".join(lines)


def format_learn_results() -> str:
    """格式化模式分析结果。"""
    result = analyze_patterns()

    if result["status"] == "insufficient_data":
        return (
            f"🐝 DreamHive — 学习\n"
            f"{'=' * 40}\n\n"
            f"  {result['message']}\n\n"
            f"  继续使用技能，稍后再运行此命令。"
        )

    lines = [
        f"🐝 DreamHive — 模式分析",
        "=" * 60,
        f"  总调用次数:  {result['total_invocations']}",
        f"  分析的会话数:  {result['total_sessions']}",
        f"  已使用的技能: {result['unique_skills_used']} / {result['total_skills_indexed']}",
        "",
    ]

    # 热门技能
    if result.get("top_skills"):
        lines.append("📊 最常用的技能:")
        for s in result["top_skills"][:5]:
            lines.append(f"  {s['name']:30s}  {s['count']}次")
        lines.append("")

    # 模式
    if result.get("patterns"):
        lines.append("🔗 检测到的模式:")
        for p in result["patterns"]:
            lines.append(f"  {p['label']:50s}  ({p['count']}次)")
        lines.append("")

    # 建议
    if result.get("suggestions"):
        lines.append("💡 建议创建的组合技能:")
        for i, s in enumerate(result["suggestions"], 1):
            lines.append(f"  #{i}  {s['suggested_name']}")
            lines.append(f"      链路: {' → '.join(s['skills_chain'])}")
            lines.append(f"      触发次数: {s['trigger_count']}")
        lines.append("")
        lines.append("  如需自动生成建议的技能，运行:")
        lines.append(f"  python3 {Path(__file__).resolve()} generate <建议编号>")
    else:
        lines.append("  尚未检测到重复模式（需要 ≥3 次出现）。")

    # 未使用的技能
    if result.get("never_used_count", 0) > 0:
        lines.append("")
        lines.append(f"💤 {result['never_used_count']} 个技能从未被调用。")
        if result.get("never_used_sample"):
            for name in result["never_used_sample"][:5]:
                lines.append(f"  - {name}")

    return "\n".join(lines)


def load_patterns() -> dict:
    """从磁盘加载已学习的模式。"""
    if PATTERNS_FILE.exists():
        try:
            return json.loads(PATTERNS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"patterns": [], "suggestions": []}


# ── CLI 入口 ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "index":
        index = build_index()
        print(f"🐝 已索引 {index['total_skills']} 个技能，来自 {len(SKILL_SEARCH_PATHS)} 个搜索路径")
        print(f"   索引已保存到: {INDEX_FILE}")

    elif command == "invoke":
        if len(sys.argv) < 3:
            print("用法: dreamhive.py invoke <技能名> [ok|fail] [上下文]")
            sys.exit(1)
        skill_name = sys.argv[2]
        result = sys.argv[3] if len(sys.argv) > 3 else "ok"
        context = sys.argv[4] if len(sys.argv) > 4 else ""
        record_invocation(skill_name, result, context)
        print(f"✓ 已记录: {skill_name} ({result})")

    elif command == "status":
        print(format_status())

    elif command == "list":
        print(format_list())

    elif command == "suggest":
        if len(sys.argv) < 3:
            print("用法: dreamhive.py suggest <查询>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        print(format_suggestions(query))

    elif command == "learn":
        print(format_learn_results())

    elif command == "generate":
        if len(sys.argv) < 3:
            print("用法: dreamhive.py generate <建议编号>")
            sys.exit(1)
        result = analyze_patterns()
        suggestions = result.get("suggestions", [])
        idx = int(sys.argv[2]) - 1
        if 0 <= idx < len(suggestions):
            path = generate_skill_file(suggestions[idx])
            print(f"✓ 已生成组合技能: {path}")
        else:
            print(f"无效的建议编号。可选范围: 1-{len(suggestions)}")

    elif command == "stats":
        if len(sys.argv) < 3:
            print("用法: dreamhive.py stats <技能名>")
            sys.exit(1)
        skill_name = sys.argv[2]
        index = load_index()
        for s in index.get("skills", []):
            if s["name"] == skill_name:
                print(json.dumps(s, indent=2, ensure_ascii=False))
                return
        print(f"索引中未找到技能 '{skill_name}'。")

    elif command == "json-status":
        # 供钩子使用的机器可读输出
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
        # 供钩子使用的机器可读推荐
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        suggestions = suggest_skills(query)
        print(json.dumps(suggestions, indent=2, ensure_ascii=False))

    else:
        print(f"未知命令: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
