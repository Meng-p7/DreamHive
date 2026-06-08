"""DreamHive core engine tests."""
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts directory to path so we can import dreamhive
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import dreamhive as dh


@pytest.fixture(autouse=True)
def isolated_env(tmp_path):
    """Redirect all data files to a temp directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    index_file = data_dir / "skill-index.json"
    history_file = data_dir / "invocation-history.json"
    patterns_file = data_dir / "learned-patterns.json"
    term_file = data_dir / "term-map.json"

    with (
        patch.object(dh, "DATA_DIR", data_dir),
        patch.object(dh, "INDEX_FILE", index_file),
        patch.object(dh, "HISTORY_FILE", history_file),
        patch.object(dh, "PATTERNS_FILE", patterns_file),
    ):
        # Reset term map cache between tests
        dh._TERM_MAP_CACHE = None
        yield tmp_path


# ── extract_keywords ───────────────────────────────────────────────────────

class TestExtractKeywords:
    def test_basic_english(self):
        kw = dh.extract_keywords("A powerful debugging tool for Python")
        assert "powerful" in kw
        assert "debugging" in kw
        assert "python" in kw
        # Stop words removed
        assert "for" not in kw
        assert "a" not in kw

    def test_chinese_translates_via_term_map(self, isolated_env):
        term_file = isolated_env / "data" / "term-map.json"
        term_file.write_text('{"排错": "debug troubleshoot", "测试": "test"}')
        dh._TERM_MAP_CACHE = None

        kw = dh.extract_keywords("帮我排错和测试")
        assert "debug" in kw
        assert "troubleshoot" in kw
        assert "test" in kw

    def test_mixed_chinese_english(self, isolated_env):
        term_file = isolated_env / "data" / "term-map.json"
        term_file.write_text('{"部署": "deploy"}')
        dh._TERM_MAP_CACHE = None

        kw = dh.extract_keywords("部署 Python 应用")
        assert "deploy" in kw
        assert "python" in kw

    def test_empty_string(self):
        assert dh.extract_keywords("") == []

    def test_quoted_phrases(self):
        kw = dh.extract_keywords('Use "code review" for quality')
        assert "code review" in kw

    def test_no_duplicates(self):
        kw = dh.extract_keywords("debug debug debug")
        assert kw.count("debug") == 1


# ── tokenize ───────────────────────────────────────────────────────────────

class TestTokenize:
    def test_basic(self):
        tokens = dh.tokenize("Hello World test-case")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test-case" in tokens

    def test_cjk_with_term_map(self, isolated_env):
        term_file = isolated_env / "data" / "term-map.json"
        term_file.write_text('{"安全": "security"}')
        dh._TERM_MAP_CACHE = None

        tokens = dh.tokenize("安全检查")
        assert "security" in tokens

    def test_empty(self):
        assert dh.tokenize("") == []


# ── _display_width ─────────────────────────────────────────────────────────

class TestDisplayWidth:
    def test_ascii(self):
        assert dh._display_width("hello") == 5

    def test_cjk(self):
        # CJK chars are 2 columns each
        assert dh._display_width("你好") == 4

    def test_mixed(self):
        assert dh._display_width("hi你好") == 6

    def test_emoji(self):
        # Bee emoji is double-width
        assert dh._display_width("\U0001f41d") == 2

    def test_empty(self):
        assert dh._display_width("") == 0


# ── _compute_file_hash ─────────────────────────────────────────────────────

class TestComputeFileHash:
    def test_deterministic(self, isolated_env):
        f = isolated_env / "test.txt"
        f.write_text("hello")
        assert dh._compute_file_hash(f) == dh._compute_file_hash(f)

    def test_different_content(self, isolated_env):
        a = isolated_env / "a.txt"
        b = isolated_env / "b.txt"
        a.write_text("hello")
        b.write_text("world")
        assert dh._compute_file_hash(a) != dh._compute_file_hash(b)

    def test_length(self, isolated_env):
        f = isolated_env / "test.txt"
        f.write_text("x")
        assert len(dh._compute_file_hash(f)) == 16


# ── load_term_map ──────────────────────────────────────────────────────────

class TestLoadTermMap:
    def test_loads_valid_json(self, isolated_env):
        term_file = isolated_env / "data" / "term-map.json"
        term_file.write_text('{"调试": "debug"}')
        dh._TERM_MAP_CACHE = None

        tm = dh.load_term_map()
        assert tm == {"调试": "debug"}

    def test_missing_file_returns_empty(self, isolated_env):
        dh._TERM_MAP_CACHE = None
        tm = dh.load_term_map()
        assert tm == {}

    def test_caches_after_first_load(self, isolated_env):
        term_file = isolated_env / "data" / "term-map.json"
        term_file.write_text('{"x": "y"}')
        dh._TERM_MAP_CACHE = None

        first = dh.load_term_map()
        # Mutate cache to prove second call uses it
        first["added"] = True
        second = dh.load_term_map()
        assert second is first


# ── parse_skill_frontmatter ────────────────────────────────────────────────

class TestParseSkillFrontmatter:
    def test_valid(self, isolated_env):
        f = isolated_env / "SKILL.md"
        f.write_text(textwrap.dedent("""\
            ---
            name: test-skill
            description: "A test skill"
            version: 1.0.0
            ---

            # Test
        """))
        meta = dh.parse_skill_frontmatter(f)
        assert meta["name"] == "test-skill"
        assert "A test skill" in meta["description"]

    def test_missing_frontmatter(self, isolated_env):
        f = isolated_env / "SKILL.md"
        f.write_text("# No frontmatter\nJust content.")
        meta = dh.parse_skill_frontmatter(f)
        assert meta.get("name") is None

    def test_nonexistent_file(self, isolated_env):
        f = isolated_env / "nonexistent.md"
        meta = dh.parse_skill_frontmatter(f)
        assert meta == {}


# ── build_index (incremental) ─────────────────────────────────────────────

class TestBuildIndex:
    def _make_skill(self, path: Path, name: str, desc: str):
        skill_dir = path / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(textwrap.dedent(f"""\
            ---
            name: {name}
            description: "{desc}"
            version: 1.0.0
            ---
            # {name}
        """))

    def test_builds_index(self, isolated_env):
        skills_dir = isolated_env / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        self._make_skill(skills_dir, "alpha", "Alpha skill")
        self._make_skill(skills_dir, "beta", "Beta skill")

        with patch.object(dh, "SKILL_SEARCH_PATHS", [skills_dir]):
            index = dh.build_index()

        assert index["total_skills"] == 2
        names = {s["name"] for s in index["skills"]}
        assert "alpha" in names
        assert "beta" in names

    def test_preserves_call_counts(self, isolated_env):
        skills_dir = isolated_env / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        self._make_skill(skills_dir, "gamma", "Gamma skill")

        with patch.object(dh, "SKILL_SEARCH_PATHS", [skills_dir]):
            idx1 = dh.build_index()
            # Manually set call count
            idx1["skills"][0]["call_count"] = 42
            dh.INDEX_FILE.write_text(json.dumps(idx1))

            idx2 = dh.build_index()
            gamma = next(s for s in idx2["skills"] if s["name"] == "gamma")
            assert gamma["call_count"] == 42

    def test_includes_file_hash(self, isolated_env):
        skills_dir = isolated_env / ".claude" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        self._make_skill(skills_dir, "delta", "Delta skill")

        with patch.object(dh, "SKILL_SEARCH_PATHS", [skills_dir]):
            index = dh.build_index()

        delta = index["skills"][0]
        assert "file_hash" in delta
        assert len(delta["file_hash"]) == 16


# ── suggest_skills ─────────────────────────────────────────────────────────

class TestSuggestSkills:
    def _seed_index(self, isolated_env, skills_data):
        index = {
            "version": 2,
            "built_at": "2026-01-01T00:00:00+00:00",
            "total_skills": len(skills_data),
            "skills": skills_data,
        }
        dh.INDEX_FILE.write_text(json.dumps(index))

    def test_keyword_match(self, isolated_env):
        self._seed_index(isolated_env, [
            {"name": "debug-helper", "description": "Debug Python code",
             "keywords": ["debug", "python", "code"], "call_count": 0},
            {"name": "deploy-bot", "description": "Deploy to production",
             "keywords": ["deploy", "production"], "call_count": 0},
        ])
        results = dh.suggest_skills("debug my python code")
        assert len(results) > 0
        assert results[0]["name"] == "debug-helper"

    def test_chinese_query_translates(self, isolated_env):
        term_file = isolated_env / "data" / "term-map.json"
        term_file.write_text('{"调试": "debug", "部署": "deploy"}')
        dh._TERM_MAP_CACHE = None

        self._seed_index(isolated_env, [
            {"name": "debug-helper", "description": "Debug Python code",
             "keywords": ["debug", "python"], "call_count": 0},
            {"name": "deploy-bot", "description": "Deploy to production",
             "keywords": ["deploy", "production"], "call_count": 0},
        ])
        results = dh.suggest_skills("帮我调试代码")
        assert len(results) > 0
        assert results[0]["name"] == "debug-helper"

    def test_empty_index(self, isolated_env):
        self._seed_index(isolated_env, [])
        assert dh.suggest_skills("anything") == []

    def test_usage_bonus_tiebreaker(self, isolated_env):
        self._seed_index(isolated_env, [
            {"name": "skill-a", "description": "Test skill A",
             "keywords": ["test"], "call_count": 10},
            {"name": "skill-b", "description": "Test skill B",
             "keywords": ["test"], "call_count": 0},
        ])
        results = dh.suggest_skills("test")
        assert results[0]["name"] == "skill-a"


# ── format_status ──────────────────────────────────────────────────────────

class TestFormatStatus:
    def test_box_alignment(self, isolated_env):
        # Seed a minimal index
        index = {
            "version": 2,
            "built_at": "2026-01-01T12:00:00+00:00",
            "total_skills": 42,
            "skills": [
                {"name": "test-skill", "call_count": 5, "keywords": []},
            ],
        }
        dh.INDEX_FILE.write_text(json.dumps(index))

        output = dh.format_status()
        lines = output.split("\n")

        # All lines should have same display width (box alignment)
        widths = {dh._display_width(l) for l in lines}
        assert len(widths) == 1, f"Lines have different widths: {widths}"

    def test_with_recent_invocations(self, isolated_env):
        history = {
            "total_invocations": 1,
            "entries": [
                {"skill": "test-skill", "result": "ok",
                 "timestamp": "2026-01-01T12:00:00+00:00"},
            ],
        }
        dh.HISTORY_FILE.write_text(json.dumps(history))

        output = dh.format_status()
        assert "Recent invocations" in output
        lines = output.split("\n")
        widths = {dh._display_width(l) for l in lines}
        assert len(widths) == 1

    def test_minimal_state(self, isolated_env):
        output = dh.format_status()
        assert "DreamHive Status" in output
        lines = output.split("\n")
        widths = {dh._display_width(l) for l in lines}
        assert len(widths) == 1


# ── generate_skill_file ────────────────────────────────────────────────────

class TestGenerateSkillFile:
    def test_generates_with_context_rules(self, isolated_env):
        index = {
            "version": 2,
            "built_at": "2026-01-01T00:00:00+00:00",
            "total_skills": 2,
            "skills": [
                {"name": "step-a", "description": "Step A",
                 "keywords": [], "call_count": 0},
                {"name": "step-b", "description": "Step B",
                 "keywords": [], "call_count": 0},
            ],
        }
        dh.INDEX_FILE.write_text(json.dumps(index))

        with patch.object(Path, "home", return_value=isolated_env):
            suggestion = {
                "skills_chain": ["step-a", "step-b"],
                "suggested_name": "test-composite",
                "suggested_description": "A test composite skill",
                "trigger_count": 5,
            }
            path_str = dh.generate_skill_file(suggestion)
            content = Path(path_str).read_text()

        assert "Context Passing Rules" in content
        assert "Prerequisites" in content
        assert "Error Degradation" in content
        assert "step-a" in content
        assert "step-b" in content
        assert "All preceding steps completed successfully" in content

    def test_prereq_detection(self, isolated_env):
        index = {
            "version": 2,
            "built_at": "2026-01-01T00:00:00+00:00",
            "total_skills": 1,
            "skills": [
                {"name": "test-runner", "description": "Run unit tests",
                 "keywords": [], "call_count": 0},
            ],
        }
        dh.INDEX_FILE.write_text(json.dumps(index))

        with patch.object(Path, "home", return_value=isolated_env):
            suggestion = {
                "skills_chain": ["test-runner"],
                "suggested_name": "test-prereq",
                "suggested_description": "Test prereq detection",
                "trigger_count": 3,
            }
            path_str = dh.generate_skill_file(suggestion)
            content = Path(path_str).read_text()

        assert "Test suite must be available" in content


# ── record_invocation & archive ────────────────────────────────────────────

class TestInvocationTracking:
    def test_record_invocation(self, isolated_env):
        index = {"version": 2, "skills": [
            {"name": "test-skill", "call_count": 0, "success_count": 0,
             "fail_count": 0, "keywords": []}
        ]}
        dh.INDEX_FILE.write_text(json.dumps(index))

        dh.record_invocation("test-skill", "ok")

        history = json.loads(dh.HISTORY_FILE.read_text())
        assert history["total_invocations"] == 1
        assert history["entries"][0]["skill"] == "test-skill"
        assert history["entries"][0]["result"] == "ok"

        idx = json.loads(dh.INDEX_FILE.read_text())
        skill = idx["skills"][0]
        assert skill["call_count"] == 1
        assert skill["success_count"] == 1

    def test_archive_triggers_at_501(self, isolated_env):
        entries = [
            {"skill": "x", "result": "ok", "timestamp": f"2026-01-{d:02d}T00:00:00+00:00"}
            for d in range(1, 32)
        ] * 17  # 527 entries
        history = {"total_invocations": len(entries), "entries": entries}
        dh.HISTORY_FILE.write_text(json.dumps(history))

        index = {"version": 2, "skills": [
            {"name": "x", "call_count": 0, "success_count": 0,
             "fail_count": 0, "keywords": []}
        ]}
        dh.INDEX_FILE.write_text(json.dumps(index))

        dh.record_invocation("x", "ok")

        history = json.loads(dh.HISTORY_FILE.read_text())
        assert len(history["entries"]) <= 501


# ── _display_width with CJK in box ────────────────────────────────────────

class TestStatusBoxWithCJK:
    def test_cjk_content_aligns(self, isolated_env):
        index = {
            "version": 2,
            "built_at": "2026-01-01T12:00:00+00:00",
            "total_skills": 5,
            "skills": [],
        }
        dh.INDEX_FILE.write_text(json.dumps(index))

        output = dh.format_status()
        lines = output.split("\n")
        widths = {dh._display_width(l) for l in lines}
        assert len(widths) == 1, f"Misaligned box with widths: {widths}"
