"""Knowledge Map Navigator — reads map metadata, selects content, assembles context.

The navigator is the runtime engine of the knowledge map. It:
  1. Analyzes the prompt to determine intent (via intent-map.yaml)
  2. Selects an injection profile based on the target model
  3. Reads _map.yaml entries to find relevant content
  4. Assembles the context block within the token budget
  5. Returns the augmented prompt

This connects the static knowledge map (YAML metadata) to the dynamic
context assembly pipeline (RAG, KB, prompt augmentation).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from aicp.core.modes import Mode

logger = logging.getLogger("aicp.navigator")

# Default paths relative to project root
_MAP_DIR = Path("docs/knowledge-map")
_PROFILES_FILE = _MAP_DIR / "injection-profiles.yaml"
_INTENT_MAP_FILE = _MAP_DIR / "intent-map.yaml"


class Navigator:
    """Reads the knowledge map and assembles context for prompts.

    Args:
        project_path: Root path of the AICP project.
        kb: Optional KnowledgeBase for RAG augmentation.
        config: AICP config dict.
    """

    def __init__(
        self,
        project_path: Path,
        kb=None,
        config: Optional[Dict] = None,
    ) -> None:
        self.project_path = Path(project_path)
        self.kb = kb
        self.config = config or {}
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
        if any(p in model_lower for p in ["qwen3-8b", "qwen3-4b", "hermes", "phi"]):
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
          2. Gathers relevant content from KB
          3. Assembles within token budget
          4. Returns the augmented prompt

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

        parts: List[str] = []
        total = 0

        # KB/RAG augmentation
        if spec["inject_kb"] and self.kb:
            try:
                kb_results = self.kb.search(prompt, top_k=3)
                for r in kb_results:
                    text = r["text"]
                    if total + len(text) > max_chars:
                        break
                    source = Path(r["source"]).name if "/" in r["source"] else r["source"]
                    parts.append(f"[kb:{source}] {text}")
                    total += len(text)
            except Exception as e:
                logger.warning("KB search for context assembly failed: %s", e)

        if not parts:
            return prompt

        context_block = "\n---\n".join(parts)
        return (
            f"Use the following context to help answer.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {prompt}"
        )

    def stats(self) -> Dict[str, Any]:
        """Return navigator status."""
        return {
            "profiles_loaded": bool(self._profiles),
            "intent_map_loaded": bool(self._intent_map),
            "profile_count": len(self._profiles),
            "intent_count": len(self._intent_map.get("intents", {})),
            "kb_available": self.kb is not None,
            "map_dir": str(self.project_path / _MAP_DIR),
        }
