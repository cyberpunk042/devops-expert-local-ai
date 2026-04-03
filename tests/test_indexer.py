"""Tests for auto-indexing pipeline."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from aicp.core.indexer import AutoIndexer, DEFAULT_EXTENSIONS, SKIP_DIRS


def _mock_kb():
    kb = MagicMock()
    kb.ingest_file.return_value = 5
    kb.delete_source.return_value = 0
    return kb


def test_scan_finds_python_files(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "readme.md").write_text("# Hello")
    (tmp_path / "data.bin").write_bytes(b"\x00" * 100)

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path)
    files = indexer._scan_files()
    names = {f.name for f in files}
    assert "main.py" in names
    assert "readme.md" in names
    assert "data.bin" not in names  # .bin not in default extensions


def test_scan_skips_excluded_dirs(tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "lib.py").write_text("pass")
    (tmp_path / "app.py").write_text("pass")

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path)
    files = indexer._scan_files()
    paths = {str(f) for f in files}
    assert any("app.py" in p for p in paths)
    assert not any(".venv" in p for p in paths)


def test_index_all(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path)
    result = indexer.index_all()

    assert result["files_indexed"] == 2
    assert result["chunks"] == 10  # 5 per file
    assert kb.ingest_file.call_count == 2


def test_index_changed_detects_modification(tmp_path):
    f = tmp_path / "app.py"
    f.write_text("v1")

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path)

    # First call indexes everything
    indexer.index_all()
    kb.reset_mock()

    # No change — should index nothing
    result = indexer.index_changed()
    assert result["files_indexed"] == 0

    # Modify file
    time.sleep(0.05)
    f.write_text("v2")

    result = indexer.index_changed()
    assert result["files_indexed"] == 1


def test_index_changed_detects_new_file(tmp_path):
    (tmp_path / "existing.py").write_text("pass")

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path)
    indexer.index_all()
    kb.reset_mock()

    # Add new file
    (tmp_path / "new.py").write_text("pass")
    result = indexer.index_changed()
    assert result["files_indexed"] == 1


def test_index_handles_ingest_error(tmp_path):
    (tmp_path / "bad.py").write_text("bad")

    kb = _mock_kb()
    kb.ingest_file.side_effect = RuntimeError("embed failed")
    indexer = AutoIndexer(kb, tmp_path)
    result = indexer.index_all()
    assert result["errors"] == 1
    assert indexer.stats["total_errors"] == 1


def test_stats(tmp_path):
    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path)
    stats = indexer.stats
    assert stats["running"] is False
    assert stats["tracked_files"] == 0
    assert str(tmp_path) in stats["project"]


def test_max_file_size_filter(tmp_path):
    small = tmp_path / "small.py"
    small.write_text("x = 1")
    big = tmp_path / "big.py"
    big.write_text("x" * 1000)

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path, max_file_size=500)
    files = indexer._scan_files()
    names = {f.name for f in files}
    assert "small.py" in names
    assert "big.py" not in names


def test_custom_extensions(tmp_path):
    (tmp_path / "code.py").write_text("pass")
    (tmp_path / "doc.md").write_text("# doc")

    kb = _mock_kb()
    indexer = AutoIndexer(kb, tmp_path, extensions=[".md"])
    files = indexer._scan_files()
    names = {f.name for f in files}
    assert "doc.md" in names
    assert "code.py" not in names
