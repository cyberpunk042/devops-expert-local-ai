"""Auto-indexing pipeline — watch project files and re-embed on change.

Monitors a project directory for file changes and automatically re-ingests
modified files into the RAG knowledge base. Runs as a background thread.

Usage:
    from aicp.core.indexer import AutoIndexer

    indexer = AutoIndexer(kb, project_path, extensions=[".py", ".md"])
    indexer.start()       # background thread
    indexer.index_all()   # one-shot full re-index
    indexer.stop()
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger("aicp.indexer")

# Default file types to index
DEFAULT_EXTENSIONS = [
    ".py", ".md", ".txt", ".rst", ".yaml", ".yml",
    ".json", ".toml", ".sh", ".go", ".rs", ".js", ".ts",
]

# Directories to always skip
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".aicp", ".claude", "backends",
}


class AutoIndexer:
    """Watches a project directory and auto-indexes changed files into KB.

    Uses polling (stat-based) rather than inotify for portability across
    WSL2, macOS, and Linux. Checks file mtimes every `poll_interval` seconds.
    """

    def __init__(
        self,
        kb,
        project_path: Path,
        extensions: Optional[List[str]] = None,
        poll_interval: float = 30.0,
        max_file_size: int = 500_000,  # 500KB max per file
    ) -> None:
        self.kb = kb
        self.project_path = Path(project_path)
        self.extensions = set(extensions or DEFAULT_EXTENSIONS)
        self.poll_interval = poll_interval
        self.max_file_size = max_file_size
        self._file_mtimes: Dict[str, float] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._indexed_count = 0
        self._error_count = 0

    def _scan_files(self) -> List[Path]:
        """Scan project directory for indexable files."""
        files = []
        for root, dirs, filenames in os.walk(self.project_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in filenames:
                p = Path(root) / name
                if p.suffix.lower() in self.extensions and p.stat().st_size <= self.max_file_size:
                    files.append(p)
        return files

    def _get_changed_files(self) -> List[Path]:
        """Return files that have changed since last check."""
        changed = []
        current_files: Dict[str, float] = {}

        for f in self._scan_files():
            key = str(f)
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            current_files[key] = mtime
            old_mtime = self._file_mtimes.get(key)
            if old_mtime is None or mtime > old_mtime:
                changed.append(f)

        # Detect deleted files (remove from index)
        deleted = set(self._file_mtimes) - set(current_files)
        for key in deleted:
            try:
                self.kb.delete_source(key)
                logger.info("De-indexed deleted file: %s", key)
            except Exception:
                pass

        self._file_mtimes = current_files
        return changed

    def index_changed(self) -> dict:
        """Index files that changed since last check. Returns summary."""
        changed = self._get_changed_files()
        if not changed:
            return {"files_indexed": 0, "chunks": 0, "errors": 0}

        total_chunks = 0
        errors = 0
        for f in changed:
            try:
                # Remove old chunks for this file first
                self.kb.delete_source(str(f))
                count = self.kb.ingest_file(f)
                total_chunks += count
                self._indexed_count += 1
            except Exception as e:
                logger.warning("Failed to index %s: %s", f, e)
                errors += 1
                self._error_count += 1

        if changed:
            logger.info(
                "Auto-indexed %d files (%d chunks, %d errors)",
                len(changed), total_chunks, errors,
            )

        return {
            "files_indexed": len(changed) - errors,
            "chunks": total_chunks,
            "errors": errors,
        }

    def index_all(self) -> dict:
        """Full re-index of the entire project. Returns summary."""
        self._file_mtimes.clear()
        return self.index_changed()

    def _poll_loop(self) -> None:
        """Background polling loop."""
        logger.info(
            "Auto-indexer started: %s (poll every %.0fs, %d extensions)",
            self.project_path, self.poll_interval, len(self.extensions),
        )
        # Initial full index
        self.index_all()

        while not self._stop_event.wait(self.poll_interval):
            try:
                self.index_changed()
            except Exception as e:
                logger.error("Auto-indexer error: %s", e)

    def start(self) -> None:
        """Start the background auto-indexing thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background auto-indexing thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    @property
    def stats(self) -> dict:
        return {
            "running": self._thread.is_alive() if self._thread else False,
            "tracked_files": len(self._file_mtimes),
            "total_indexed": self._indexed_count,
            "total_errors": self._error_count,
            "project": str(self.project_path),
            "poll_interval": self.poll_interval,
        }
