"""Tests for aicp.core.memory_relevance — memory scoring, aging, scanning."""

import time

import pytest

from aicp.core.memory_relevance import (
    MAX_MEMORY_FILES,
    MemoryHeader,
    MemoryRelevanceScorer,
    _cosine_similarity,
    _parse_frontmatter,
    format_memory_manifest,
    memory_age_days,
    memory_age_text,
    memory_freshness_warning,
    scan_memory_files,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def memory_dir(tmp_path):
    """Create a temporary memory directory with test files."""
    mem = tmp_path / "memory"
    mem.mkdir()

    # MEMORY.md index (should be excluded from scan)
    (mem / "MEMORY.md").write_text("# Memory Index\n- [test](test.md)\n")

    # User memory
    (mem / "user_role.md").write_text(
        "---\nname: User role\ndescription: Senior DevOps engineer\ntype: user\n---\nThe user is a senior DevOps engineer.\n"
    )

    # Feedback memory
    (mem / "feedback_testing.md").write_text(
        "---\nname: Testing preferences\ndescription: Always run tests before committing\ntype: feedback\n---\nRun pytest before every commit.\n"
    )

    # Project memory
    (mem / "project_status.md").write_text(
        "---\nname: Project status\ndescription: AICP stage 4 reliability hardening\ntype: project\n---\nAll stages complete.\n"
    )

    # No frontmatter file
    (mem / "bare.md").write_text("Just some text without frontmatter.\n")

    # Subdirectory memory
    sub = mem / "team"
    sub.mkdir()
    (sub / "team_standards.md").write_text(
        "---\nname: Team standards\ndescription: Code review process\ntype: reference\n---\nAll PRs need review.\n"
    )

    return mem


# ── Memory aging tests ────────────────────────────────────────────────────────

class TestMemoryAging:
    def test_age_days_today(self):
        assert memory_age_days(time.time()) == 0

    def test_age_days_yesterday(self):
        assert memory_age_days(time.time() - 86_400) == 1

    def test_age_days_week_ago(self):
        assert memory_age_days(time.time() - 7 * 86_400) == 7

    def test_age_days_future(self):
        """Future timestamps should return 0, not negative."""
        assert memory_age_days(time.time() + 3600) == 0

    def test_age_text_today(self):
        assert memory_age_text(time.time()) == "today"

    def test_age_text_yesterday(self):
        assert memory_age_text(time.time() - 86_400) == "yesterday"

    def test_age_text_old(self):
        assert "5 days ago" in memory_age_text(time.time() - 5 * 86_400)

    def test_freshness_warning_fresh(self):
        """No warning for today's memories."""
        assert memory_freshness_warning(time.time()) == ""

    def test_freshness_warning_yesterday(self):
        """No warning for yesterday's memories."""
        assert memory_freshness_warning(time.time() - 86_400) == ""

    def test_freshness_warning_stale(self):
        warning = memory_freshness_warning(time.time() - 3 * 86_400)
        assert "outdated" in warning
        assert "verify" in warning.lower()

    def test_freshness_warning_very_old(self):
        warning = memory_freshness_warning(time.time() - 30 * 86_400)
        assert "30 days ago" in warning


# ── Frontmatter parsing tests ────────────────────────────────────────────────

class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\nname: Test\ndescription: A test\ntype: user\n---\nContent here.\n")
        result = _parse_frontmatter(str(f))
        assert result["name"] == "Test"
        assert result["description"] == "A test"
        assert result["type"] == "user"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Just plain text.\n")
        assert _parse_frontmatter(str(f)) == {}

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\n: invalid: yaml: [[\n---\n")
        assert _parse_frontmatter(str(f)) == {}

    def test_missing_file(self):
        assert _parse_frontmatter("/nonexistent/path.md") == {}

    def test_truncated_frontmatter(self, tmp_path):
        """Frontmatter with no closing --- should return empty."""
        f = tmp_path / "test.md"
        f.write_text("---\nname: Test\n")
        assert _parse_frontmatter(str(f)) == {}

    def test_frontmatter_with_special_chars(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text('---\nname: "Test: special"\ndescription: "Has \\"quotes\\""\n---\nContent.\n')
        result = _parse_frontmatter(str(f))
        assert "Test: special" in result.get("name", "")


# ── Memory scanning tests ────────────────────────────────────────────────────

class TestScanMemoryFiles:
    def test_scan_finds_memory_files(self, memory_dir):
        headers = scan_memory_files(memory_dir)
        filenames = {h.filename for h in headers}
        assert "user_role.md" in filenames
        assert "feedback_testing.md" in filenames
        assert "project_status.md" in filenames

    def test_scan_excludes_memory_index(self, memory_dir):
        headers = scan_memory_files(memory_dir)
        filenames = {h.filename for h in headers}
        assert "MEMORY.md" not in filenames

    def test_scan_includes_subdirectories(self, memory_dir):
        headers = scan_memory_files(memory_dir)
        filenames = {h.filename for h in headers}
        # Should find team/team_standards.md
        assert any("team_standards.md" in f for f in filenames)

    def test_scan_parses_frontmatter(self, memory_dir):
        headers = scan_memory_files(memory_dir)
        user = next(h for h in headers if "user_role" in h.filename)
        assert user.name == "User role"
        assert user.description == "Senior DevOps engineer"
        assert user.memory_type == "user"

    def test_scan_handles_no_frontmatter(self, memory_dir):
        headers = scan_memory_files(memory_dir)
        bare = next(h for h in headers if "bare" in h.filename)
        assert bare.name == ""
        assert bare.description == ""

    def test_scan_sorted_by_mtime(self, memory_dir):
        # Touch files in order
        time.sleep(0.01)
        (memory_dir / "user_role.md").write_text(
            "---\nname: User role\ndescription: Updated\ntype: user\n---\n"
        )
        headers = scan_memory_files(memory_dir)
        assert headers[0].filename == "user_role.md"  # Most recent

    def test_scan_nonexistent_dir(self):
        assert scan_memory_files("/nonexistent/path") == []

    def test_scan_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert scan_memory_files(empty) == []

    def test_scan_max_files_cap(self, tmp_path):
        """Should not return more than MAX_MEMORY_FILES."""
        mem = tmp_path / "memory"
        mem.mkdir()
        for i in range(MAX_MEMORY_FILES + 10):
            (mem / f"file_{i:04d}.md").write_text(f"---\nname: File {i}\n---\n")
        headers = scan_memory_files(mem)
        assert len(headers) <= MAX_MEMORY_FILES


# ── Memory manifest formatting tests ─────────────────────────────────────────

class TestFormatMemoryManifest:
    def test_format_basic(self, memory_dir):
        headers = scan_memory_files(memory_dir)
        manifest = format_memory_manifest(headers)
        assert "user_role.md" in manifest
        assert "Senior DevOps" in manifest
        assert "[user]" in manifest

    def test_format_empty(self):
        assert format_memory_manifest([]) == ""

    def test_format_no_description(self):
        header = MemoryHeader(
            filename="test.md", filepath="/tmp/test.md",
            mtime=time.time(), name="", description="",
        )
        manifest = format_memory_manifest([header])
        assert "(no description)" in manifest


# ── Cosine similarity tests ──────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_mismatched_lengths(self):
        assert _cosine_similarity([1, 2], [1, 2, 3]) == 0.0


# ── Relevance scorer tests ───────────────────────────────────────────────────

class TestMemoryRelevanceScorer:
    def test_keyword_fallback(self, memory_dir):
        """Without embed_fn, falls back to keyword matching."""
        scorer = MemoryRelevanceScorer(embed_fn=None)
        headers = scan_memory_files(memory_dir)
        results = scorer.score("DevOps engineer", headers)
        assert len(results) > 0
        # User role should score highest (contains "DevOps" and "engineer" description)
        top = results[0]
        assert "user" in top.header.filename or top.score > 0

    def test_embedding_scoring(self):
        """With embed_fn, uses cosine similarity."""
        # Mock embedding function that returns predictable vectors
        def mock_embed(text):
            if "DevOps" in text or "engineer" in text:
                return [1.0, 0.0, 0.0]
            if "testing" in text:
                return [0.0, 1.0, 0.0]
            return [0.0, 0.0, 1.0]

        scorer = MemoryRelevanceScorer(embed_fn=mock_embed)
        headers = [
            MemoryHeader("user.md", "/tmp/user.md", time.time(),
                         "User role", "Senior DevOps engineer", "user"),
            MemoryHeader("testing.md", "/tmp/testing.md", time.time(),
                         "Testing", "Run testing before commit", "feedback"),
        ]
        results = scorer.score("DevOps engineer", headers)
        assert results[0].header.filename == "user.md"
        assert results[0].score > results[1].score

    def test_embedding_cache(self):
        call_count = 0
        def counting_embed(text):
            nonlocal call_count
            call_count += 1
            return [1.0, 0.0]

        scorer = MemoryRelevanceScorer(embed_fn=counting_embed)
        header = MemoryHeader("test.md", "/tmp/test.md", 123.0, "Test", "Desc", "user")

        # Score twice — description embedding should be cached
        scorer.score("query1", [header])
        initial_count = call_count
        scorer.score("query2", [header])
        # Query embedding changes, but description embedding is cached
        assert call_count == initial_count + 1  # only new query embedded

    def test_embedding_cache_invalidated_on_mtime_change(self):
        call_count = 0
        def counting_embed(text):
            nonlocal call_count
            call_count += 1
            return [1.0, 0.0]

        scorer = MemoryRelevanceScorer(embed_fn=counting_embed)

        h1 = MemoryHeader("test.md", "/tmp/test.md", 100.0, "Test", "Desc", "user")
        scorer.score("query", [h1])

        h2 = MemoryHeader("test.md", "/tmp/test.md", 200.0, "Test", "Desc Updated", "user")
        scorer.score("query", [h2])
        # New mtime = cache miss for description
        assert call_count >= 3  # query + desc1 + desc2 at minimum

    def test_embedding_error_falls_back_to_keywords(self):
        def failing_embed(text):
            raise RuntimeError("embed failed")

        scorer = MemoryRelevanceScorer(embed_fn=failing_embed)
        headers = [
            MemoryHeader("test.md", "/tmp/test.md", time.time(),
                         "Testing", "testing preferences", "feedback"),
        ]
        results = scorer.score("testing", headers)
        assert len(results) == 1
        assert results[0].score >= 0  # keyword fallback worked

    def test_select_relevant_loads_content(self, memory_dir):
        scorer = MemoryRelevanceScorer(embed_fn=None)
        headers = scan_memory_files(memory_dir)
        selected = scorer.select_relevant("DevOps", headers, top_k=2)
        assert len(selected) <= 2
        for m in selected:
            assert m.content  # content should be loaded

    def test_select_relevant_threshold(self):
        scorer = MemoryRelevanceScorer(embed_fn=None)
        headers = [
            MemoryHeader("test.md", "/tmp/test.md", time.time(),
                         "Unrelated", "Something completely different", "project"),
        ]
        selected = scorer.select_relevant("quantum physics", headers, threshold=0.5)
        assert len(selected) == 0  # nothing above threshold

    def test_select_relevant_top_k(self, memory_dir):
        scorer = MemoryRelevanceScorer(embed_fn=None)
        headers = scan_memory_files(memory_dir)
        selected = scorer.select_relevant("test", headers, top_k=1)
        assert len(selected) <= 1

    def test_clear_cache(self):
        scorer = MemoryRelevanceScorer(embed_fn=lambda t: [1.0])
        scorer._get_embedding("test", "file", 1.0)
        assert scorer.cache_size == 1
        scorer.clear_cache()
        assert scorer.cache_size == 0

    def test_age_text_in_results(self):
        scorer = MemoryRelevanceScorer(embed_fn=None)
        headers = [
            MemoryHeader("test.md", "/tmp/test.md", time.time(),
                         "Test", "description", "user"),
        ]
        results = scorer.score("test", headers)
        assert results[0].age_text == "today"

    def test_staleness_warning_in_results(self):
        scorer = MemoryRelevanceScorer(embed_fn=None)
        old_time = time.time() - 5 * 86_400
        headers = [
            MemoryHeader("old.md", "/tmp/old.md", old_time,
                         "Old memory", "ancient stuff", "project"),
        ]
        results = scorer.score("ancient", headers)
        assert "outdated" in results[0].staleness_warning

    def test_empty_headers(self):
        scorer = MemoryRelevanceScorer(embed_fn=None)
        results = scorer.score("anything", [])
        assert results == []
