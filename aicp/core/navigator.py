"""Knowledge Map Navigator — reads map metadata, selects content, assembles context.

The navigator is the runtime engine of the knowledge map. It:
  1. Analyzes the prompt to determine intent (via intent-map.yaml)
  2. Selects an injection profile based on the target model
  3. Queries LocalAI Collections for relevant content
  4. Assembles the context block within the token budget
  5. Returns the augmented prompt

KB content lives in LocalAI Collections (persistent, synced via make kb-sync).
The navigator queries it via /api/agents/collections/{name}/search.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml

from aicp.core.modes import Mode

logger = logging.getLogger("aicp.navigator")

# Default paths relative to project root
_MAP_DIR = Path("docs/knowledge-map")
_PROFILES_FILE = _MAP_DIR / "injection-profiles.yaml"
_INTENT_MAP_FILE = _MAP_DIR / "intent-map.yaml"


class Navigator:
    """Reads the knowledge map and assembles context for prompts.

    Queries LocalAI Collections API for KB content (persistent, synced
    via make kb-sync). Falls back gracefully if LocalAI is unreachable.

    Args:
        project_path: Root path of the AICP project.
        config: AICP config dict.
        base_url: LocalAI base URL (for collections search).
        collection: Collection name (default: aicp-kb).
    """

    def __init__(
        self,
        project_path: Path,
        config: Optional[Dict] = None,
        base_url: str = "",
        collection: str = "aicp-kb",
        kb=None,  # legacy — ignored, kept for API compat
    ) -> None:
        self.project_path = Path(project_path)
        self.config = config or {}
        local_cfg = self.config.get("backends", {}).get("local", {})
        self.base_url = base_url or local_cfg.get("base_url", "http://localhost:8090")
        self.collection = collection
        self._profiles = self._load_yaml(_PROFILES_FILE)
        self._intent_map = self._load_yaml(_INTENT_MAP_FILE)

    def _load_yaml(self, relative_path: Path) -> Dict:
        """Load a YAML file relative to project root."""
        full_path = self.project_path / relative_path
        if not full_path.exists():
            logger.debug("Knowledge map file not found: %s", full_path)
            return {}
        try:
            return yaml.safe_load(full_path.read_text()) or {}
        except Exception as e:
            logger.warning("Failed to load %s: %s", full_path, e)
            return {}

    def select_profile(self, model: str, context_window: int = 0) -> str:
        """Select the injection profile for a given model.

        Returns profile name: opus-1m, sonnet-200k, localai-8k, heartbeat.
        """
        # Fast models and heartbeat patterns
        if "fast" in model.lower() or "heartbeat" in model.lower():
            return "heartbeat"

        # By context window
        if context_window >= 500_000:
            return "opus-1m"
        if context_window >= 32_000:
            return "sonnet-200k"
        if context_window >= 4_000:
            return "localai-8k"

        # By model name patterns
        model_lower = model.lower()
        if any(p in model_lower for p in ["opus", "claude-opus"]):
            return "opus-1m"
        if any(p in model_lower for p in ["sonnet", "claude-sonnet", "qwen3-32b", "qwen3-30b"]):
            return "sonnet-200k"
        if any(p in model_lower for p in ["qwen3-8b", "qwen3-4b", "hermes", "phi", "gemma4"]):
            return "localai-8k"

        return "localai-8k"

    def match_intent(self, prompt: str, mode: Mode) -> str:
        """Match a prompt to an intent from the intent-map.

        Returns intent name (e.g. 'code_task', 'simple_qa', 'fleet_ops').

        Matching order: keyword intents first (specific), then complexity-based
        (general), then default.
        """
        intents = self._intent_map.get("intents", {})
        prompt_lower = prompt.lower()

        # Pass 1: keyword-triggered intents (most specific)
        for name, intent in intents.items():
            if name == "default":
                continue
            triggers = intent.get("triggers", {})
            keywords = triggers.get("has_keywords", [])
            if not keywords:
                continue  # skip non-keyword intents in pass 1

            if any(kw.lower() in prompt_lower for kw in keywords):
                # Check mode constraint if present
                mode_constraint = triggers.get("mode")
                if mode_constraint:
                    if isinstance(mode_constraint, list):
                        if mode.value not in mode_constraint:
                            continue
                    elif mode.value != mode_constraint:
                        continue
                return name

        # Pass 2: complexity-triggered intents
        from aicp.core.router import analyze_complexity
        complexity = analyze_complexity(prompt, mode)

        for name, intent in intents.items():
            if name == "default":
                continue
            triggers = intent.get("triggers", {})
            if "has_keywords" in triggers:
                continue  # already checked in pass 1

            if "complexity_below" in triggers:
                if complexity.score < triggers["complexity_below"]:
                    return name
            if "complexity_above" in triggers:
                if complexity.score > triggers["complexity_above"]:
                    return name

        return "default"

    def get_injection_spec(
        self,
        prompt: str,
        mode: Mode,
        model: str = "",
        context_window: int = 0,
    ) -> Dict[str, Any]:
        """Get the full injection specification for a prompt.

        Returns a dict describing what should be injected:
          - profile: which tier (opus-1m, localai-8k, etc.)
          - intent: what type of task
          - branches: what content from each branch
          - model_hint: suggested model override
          - budget_tokens: token budget for injection
        """
        profile_name = self.select_profile(model, context_window)
        intent_name = self.match_intent(prompt, mode)
        intent = self._intent_map.get("intents", {}).get(intent_name, {})
        profile = self._profiles.get(profile_name, {})

        return {
            "profile": profile_name,
            "intent": intent_name,
            "budget_tokens": profile.get("context_budget_tokens", 0),
            "model_hint": intent.get("model_hint"),
            "inject_kb": intent.get("inject", {}).get("kb_context", False),
            "inject_systems": intent.get("inject", {}).get("systems", []),
            "inject_modules": intent.get("inject", {}).get("modules", []),
            "branches": profile.get("branches", {}),
        }

    def assemble_context(
        self,
        prompt: str,
        mode: Mode,
        model: str = "",
        context_window: int = 0,
        max_chars: int = 10000,
    ) -> str:
        """Assemble an augmented prompt with knowledge map context.

        This is the main entry point. It:
          1. Determines intent and profile
          2. Reads system/module docs based on intent (E-M31)
          3. Gathers KB content from LocalAI Collections
          4. Applies profile branch levels (full/condensed/minimal/none)
          5. Assembles within token budget
          6. Returns the augmented prompt

        Args:
            prompt: Original user prompt.
            mode: AICP mode (think/edit/act).
            model: Target model name.
            context_window: Model's context window size.
            max_chars: Max characters for injected context.

        Returns:
            Augmented prompt with knowledge context prepended.
        """
        spec = self.get_injection_spec(prompt, mode, model, context_window)

        # Heartbeat profile — no injection
        if spec["profile"] == "heartbeat" or spec["budget_tokens"] == 0:
            return prompt

        branches = spec.get("branches", {})
        parts: List[str] = []
        total = 0

        # 1. System docs (based on intent + profile branch level)
        systems_branch = branches.get("systems", {})
        systems_level = systems_branch.get("level", "none") if isinstance(systems_branch, dict) else "none"
        if systems_level != "none":
            inject_systems = spec.get("inject_systems", [])
            for sys_name in inject_systems:
                if total >= max_chars:
                    break
                content = self._load_system_doc(sys_name, systems_level)
                if content:
                    parts.append(f"[system:{sys_name}] {content}")
                    total += len(content)

        # 2. Module docs (based on intent + profile branch level)
        modules_branch = branches.get("modules", {})
        modules_level = modules_branch.get("level", "none") if isinstance(modules_branch, dict) else "none"
        if modules_level != "none":
            inject_modules = spec.get("inject_modules", [])
            if inject_modules and total < max_chars:
                content = self._load_module_docs(inject_modules, modules_level, max_chars - total)
                if content:
                    parts.append(f"[modules] {content}")
                    total += len(content)

        # 3. KB context from LocalAI Collections (E-M32: map-boosted reranking)
        kb_branch = branches.get("kb_context", {})
        kb_level = kb_branch.get("level", "none") if isinstance(kb_branch, dict) else "none"
        if kb_level != "none" and spec.get("inject_kb", False):
            top_k = {"full": 5, "condensed": 3, "minimal": 1}.get(kb_level, 3)
            try:
                results = self._search_collection(prompt, top_k=top_k * 2)
                # Apply map-aware boosting based on intent cross-references
                if results:
                    results = self.map_boost(results, spec["intent"])
                    results = results[:top_k]
                for r in results:
                    text = r.get("content", r.get("text", ""))
                    if not text or total + len(text) > max_chars:
                        break
                    parts.append(f"[kb] {text}")
                    total += len(text)
            except Exception as e:
                logger.warning("Collection search failed: %s", e)

        if not parts:
            return prompt

        context_block = "\n---\n".join(parts)
        return (
            f"Use the following context to help answer.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {prompt}"
        )

    def _load_system_doc(self, name: str, level: str) -> Optional[str]:
        """Load a system manual at the requested detail level.

        Supports fuzzy matching: 'router' matches 'routing.md',
        'controller' matches 'controller.md', etc.

        Levels:
          - full: entire document
          - condensed: first section (up to first ## heading)
          - minimal: first paragraph only
          - none: skip
        """
        systems_dir = self.project_path / _MAP_DIR / "systems"
        path = systems_dir / f"{name}.md"
        if not path.exists():
            # Fallback: try substring match (e.g. "cluster" matches "cluster.md")
            if systems_dir.is_dir():
                name_lower = name.lower()
                for candidate in systems_dir.glob("*.md"):
                    stem = candidate.stem.lower()
                    if name_lower in stem or stem in name_lower:
                        path = candidate
                        break
        if not path.exists():
            return None
        try:
            text = path.read_text().strip()
        except Exception:
            return None
        if not text:
            return None

        if level == "full":
            return text
        if level == "condensed":
            # Up to second ## heading
            lines = text.split("\n")
            result = []
            heading_count = 0
            for line in lines:
                if line.startswith("## "):
                    heading_count += 1
                    if heading_count > 1:
                        break
                result.append(line)
            return "\n".join(result).strip()
        if level == "minimal":
            # First non-empty paragraph
            for para in text.split("\n\n"):
                stripped = para.strip()
                if stripped and not stripped.startswith("#"):
                    return stripped
            return text[:200]
        return None

    def _load_module_docs(
        self, modules: List[str], level: str, max_chars: int,
    ) -> Optional[str]:
        """Load module documentation at the requested detail level.

        Reads from docs/knowledge-map/module-manual.md and extracts
        sections matching the requested module names.
        """
        path = self.project_path / _MAP_DIR / "module-manual.md"
        if not path.exists():
            return None
        try:
            text = path.read_text()
        except Exception:
            return None

        if level == "full":
            return text[:max_chars]

        # Extract sections matching module names
        sections: List[str] = []
        current_section = ""
        current_name = ""

        for line in text.split("\n"):
            if line.startswith("### "):
                if current_name and current_section:
                    sections.append((current_name, current_section.strip()))
                current_name = line.lstrip("# ").strip().lower()
                current_section = line + "\n"
            elif current_name:
                current_section += line + "\n"
        if current_name and current_section:
            sections.append((current_name, current_section.strip()))

        # Filter to requested modules
        matched = []
        total = 0
        for name, content in sections:
            if total >= max_chars:
                break
            # Match module names loosely
            for mod in modules:
                mod_lower = mod.lower().replace("_", "").replace("-", "")
                name_clean = name.replace("_", "").replace("-", "").replace(".py", "")
                if mod_lower in name_clean or name_clean in mod_lower:
                    if level == "condensed":
                        # First 3 lines of section
                        content = "\n".join(content.split("\n")[:3])
                    elif level == "minimal":
                        # Just the heading
                        content = content.split("\n")[0]
                    matched.append(content)
                    total += len(content)
                    break

        return "\n\n".join(matched) if matched else None

    def _search_collection(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search the LocalAI collection for relevant content."""
        resp = httpx.post(
            f"{self.base_url}/api/agents/collections/{self.collection}/search",
            json={"query": query, "max_results": top_k},
            timeout=15.0,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        # Response format varies — handle list or dict with results key
        if isinstance(data, list):
            return data
        return data.get("results", data.get("chunks", []))

    def _collection_entries(self) -> int:
        """Count entries in the collection."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/agents/collections/{self.collection}/entries",
                timeout=5.0,
            )
            if resp.status_code == 200:
                return resp.json().get("count", 0)
        except Exception:
            pass
        return 0

    def map_boost(
        self,
        results: List[Dict],
        intent: str,
        boost_factor: float = 0.15,
    ) -> List[Dict]:
        """Boost search result scores based on knowledge map cross-references.

        Results whose source file belongs to a system/module referenced by the
        intent get a score boost. This re-ranks pure embedding results using
        structured metadata from the knowledge map.

        Args:
            results: Search results with 'source', 'score' keys.
            intent: Intent name from match_intent() (e.g. 'code_task').
            boost_factor: Score boost for matching sources (0.0-1.0).

        Returns:
            Results re-sorted with boosted scores.
        """
        if not results or not intent:
            return results

        # Get systems and modules this intent cares about
        intent_cfg = self._intent_map.get("intents", {}).get(intent, {})
        inject = intent_cfg.get("inject", {})
        relevant_systems = inject.get("systems", [])
        relevant_modules = inject.get("modules", [])

        # Build set of relevant source file stems from cross-references
        xrefs = self._load_yaml(Path("docs/knowledge-map/cross-references.yaml"))
        relevant_sources: set = set()

        for sys_name in relevant_systems:
            sys_data = xrefs.get("systems", {}).get(sys_name, {})
            for mod in sys_data.get("modules", []):
                relevant_sources.add(mod.lower().replace(".py", ""))
            # Also add connected systems' modules
            for connected in sys_data.get("connected_systems", []):
                conn_data = xrefs.get("systems", {}).get(connected, {})
                for mod in conn_data.get("modules", []):
                    relevant_sources.add(mod.lower().replace(".py", ""))

        for mod in relevant_modules:
            relevant_sources.add(mod.lower().replace(".py", ""))

        if not relevant_sources:
            return results

        # Apply boost
        boosted = []
        for r in results:
            source = r.get("source", "")
            source_stem = Path(source).stem.lower() if source else ""
            score = r.get("score", r.get("similarity", 0.0))

            if any(rs in source_stem or source_stem in rs for rs in relevant_sources):
                score = min(1.0, score + boost_factor)

            boosted.append({**r, "score": round(score, 4)})

        boosted.sort(key=lambda x: x["score"], reverse=True)
        return boosted

    def stats(self) -> Dict[str, Any]:
        """Return navigator status."""
        return {
            "profiles_loaded": bool(self._profiles),
            "intent_map_loaded": bool(self._intent_map),
            "profile_count": len(self._profiles),
            "intent_count": len(self._intent_map.get("intents", {})),
            "collection": self.collection,
            "collection_entries": self._collection_entries(),
            "base_url": self.base_url,
            "map_dir": str(self.project_path / _MAP_DIR),
        }
