"""Tests for aicp.core.memory_extract — auto-extraction of facts from task history."""

from unittest.mock import patch

from aicp.core.memory_extract import (
    ExtractedFact,
    _classify_fact,
    _slugify,
    _split_sentences,
    extract_facts_heuristic,
    run_extraction,
    save_extracted_fact,
)


class TestClassifyFact:
    def test_error_fix(self):
        mem_type, cat, conf = _classify_fact("Fixed the connection timeout by increasing retries")
        assert cat == "error_fix"
        assert conf >= 0.5

    def test_decision(self):
        mem_type, cat, conf = _classify_fact("Decided to use PostgreSQL over SQLite")
        assert cat == "decision"
        assert conf >= 0.5

    def test_learning(self):
        mem_type, cat, conf = _classify_fact("Discovered that the API rate limits at 100 req/s")
        assert cat == "learning"
        assert conf >= 0.5

    def test_low_confidence(self):
        _, _, conf = _classify_fact("Just a regular sentence with nothing special")
        assert conf < 0.5

    def test_workaround(self):
        _, cat, _ = _classify_fact("Workaround: set the timeout to 60 seconds")
        assert cat == "error_fix"

    def test_preference_is_feedback(self):
        mem_type, _, _ = _classify_fact("User prefers snake_case naming convention")
        assert mem_type == "feedback"

    def test_url_is_reference(self):
        mem_type, _, _ = _classify_fact("Found that the docs at https://example.com have details")
        assert mem_type == "reference"

    def test_upgrade_is_decision(self):
        _, cat, _ = _classify_fact("Upgraded to v4.1.3 for Gemma 4 architecture support")
        assert cat == "decision"


class TestSplitSentences:
    def test_basic_split(self):
        text = "First sentence. Second sentence. Third one here."
        result = _split_sentences(text)
        assert len(result) >= 2

    def test_paragraph_split(self):
        text = "First paragraph.\n\nSecond paragraph."
        result = _split_sentences(text)
        assert len(result) == 2

    def test_empty_string(self):
        assert _split_sentences("") == []

    def test_single_sentence(self):
        result = _split_sentences("Just one sentence here.")
        assert len(result) == 1


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello_world"

    def test_special_chars(self):
        slug = _slugify("Fix: the 'timeout' bug!")
        assert "'" not in slug
        assert "!" not in slug

    def test_long_text_truncated(self):
        slug = _slugify("x" * 100)
        assert len(slug) <= 50

    def test_empty(self):
        assert _slugify("") == ""


class TestExtractFactsHeuristic:
    def test_extracts_errors(self):
        tasks = [
            {"id": "t1", "response": "Everything is fine.", "error": "Connection refused"},
        ]
        facts = extract_facts_heuristic(tasks)
        assert any(f.category == "error_fix" for f in facts)

    def test_extracts_from_response(self):
        tasks = [
            {"id": "t1", "response": "Fixed the issue by reverting the migration.", "prompt": ""},
        ]
        facts = extract_facts_heuristic(tasks)
        assert len(facts) >= 1

    def test_extracts_decisions(self):
        tasks = [
            {"id": "t1", "response": "Decided to use Qwen3 over Hermes for better reasoning.", "prompt": ""},
        ]
        facts = extract_facts_heuristic(tasks)
        assert any(f.category == "decision" for f in facts)

    def test_skips_short_sentences(self):
        tasks = [
            {"id": "t1", "response": "OK. Done. Fixed it.", "prompt": ""},
        ]
        facts = extract_facts_heuristic(tasks)
        # Short sentences should be skipped
        assert all(len(f.content) >= 20 for f in facts)

    def test_deduplicates(self):
        tasks = [
            {"id": "t1", "response": "Fixed the timeout issue.", "prompt": ""},
            {"id": "t2", "response": "Fixed the timeout issue.", "prompt": ""},
        ]
        facts = extract_facts_heuristic(tasks)
        contents = [f.content for f in facts]
        assert len(contents) == len(set(contents))

    def test_caps_at_20(self):
        """Should not return more than 20 facts."""
        tasks = [
            {"id": f"t{i}", "response": f"Discovered that fact number {i} is important and worth remembering.", "prompt": ""}
            for i in range(50)
        ]
        facts = extract_facts_heuristic(tasks)
        assert len(facts) <= 20

    def test_empty_tasks(self):
        assert extract_facts_heuristic([]) == []

    def test_no_response(self):
        tasks = [{"id": "t1", "prompt": "test"}]
        facts = extract_facts_heuristic(tasks)
        assert len(facts) == 0


class TestSaveExtractedFact:
    def test_save_creates_file(self, tmp_path):
        fact = ExtractedFact(
            content="Fixed the timeout by adding retries",
            source_task_id="t123",
            memory_type="project",
            confidence=0.7,
            category="error_fix",
        )
        path = save_extracted_fact(fact, tmp_path)
        assert path is not None
        assert path.exists()
        content = path.read_text()
        assert "Fixed the timeout" in content
        assert "type: project" in content

    def test_save_no_overwrite(self, tmp_path):
        fact = ExtractedFact(
            content="Test fact content here that is long enough",
            source_task_id="t1",
            memory_type="project",
            confidence=0.5,
            category="learning",
        )
        path1 = save_extracted_fact(fact, tmp_path)
        path2 = save_extracted_fact(fact, tmp_path, overwrite=False)
        assert path1 is not None
        assert path2 is None  # skipped because exists

    def test_save_overwrite(self, tmp_path):
        fact = ExtractedFact(
            content="Updated fact content that should replace old",
            source_task_id="t1",
            memory_type="project",
            confidence=0.5,
            category="learning",
        )
        path1 = save_extracted_fact(fact, tmp_path)
        path2 = save_extracted_fact(fact, tmp_path, overwrite=True)
        assert path2 is not None
        assert path1 == path2

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "dir"
        fact = ExtractedFact(
            content="Fact in nested directory location test",
            source_task_id="t1",
            memory_type="feedback",
            confidence=0.6,
            category="decision",
        )
        path = save_extracted_fact(fact, nested)
        assert path is not None
        assert nested.exists()

    def test_save_frontmatter_format(self, tmp_path):
        fact = ExtractedFact(
            content="The API limits at 100 requests per second for testing",
            source_task_id="t42",
            memory_type="reference",
            confidence=0.8,
            category="learning",
        )
        path = save_extracted_fact(fact, tmp_path)
        content = path.read_text()
        assert content.startswith("---")
        assert "type: reference" in content
        assert "confidence: 0.8" in content


class TestRunExtraction:
    def test_too_few_tasks(self, tmp_path):
        with patch("aicp.core.history.list_tasks", return_value=[{"id": "t1"}]):
            results = run_extraction(tmp_path, task_count=10)
            assert results == []

    def test_dry_run(self, tmp_path):
        tasks = [
            {"id": f"t{i}", "response": f"Fixed the error in module {i} by reverting the change.", "prompt": "fix"}
            for i in range(10)
        ]
        with patch("aicp.core.history.list_tasks", return_value=tasks):
            results = run_extraction(tmp_path, dry_run=True)
            # Should have results but no files written
            for r in results:
                assert r.get("dry_run") is True
            assert not list(tmp_path.glob("*.md"))

    def test_saves_facts(self, tmp_path):
        tasks = [
            {"id": f"t{i}", "response": f"Discovered that module {i} needs the config flag enabled.", "prompt": "check"}
            for i in range(10)
        ]
        with patch("aicp.core.history.list_tasks", return_value=tasks):
            results = run_extraction(tmp_path)
            saved = [r for r in results if "saved_to" in r]
            assert len(saved) > 0

    def test_min_confidence_filter(self, tmp_path):
        tasks = [
            {"id": "t1", "response": "Just a normal response without any patterns.", "prompt": "test"}
            for _ in range(10)
        ]
        with patch("aicp.core.history.list_tasks", return_value=tasks):
            results = run_extraction(tmp_path, min_confidence=0.9)
            assert len(results) == 0  # nothing above 0.9 confidence
