"""Tests for tool safety metadata and validation pipeline."""

import json

from aicp.core.tools import (
    ALL_TOOLS,
    EDIT_TOOLS,
    THINK_TOOLS,
    _meta,
    check_tool_permissions,
    execute_tool,
    get_tool_meta,
    validate_tool_input,
)


class TestToolSafetyMetadata:
    """Tests for tool safety metadata."""

    def test_all_tools_have_safety_metadata(self):
        """Every tool in ALL_TOOLS must have safety metadata."""
        tool_names = {t["function"]["name"] for t in ALL_TOOLS}
        for name in tool_names:
            meta = get_tool_meta(name)
            assert isinstance(meta, dict), f"Missing metadata for {name}"
            assert "is_read_only" in meta
            assert "is_destructive" in meta
            assert "is_concurrent_safe" in meta

    def test_fail_closed_defaults(self):
        """Unknown tools get fail-closed defaults (not safe, not read-only)."""
        meta = get_tool_meta("unknown_tool")
        assert meta["is_read_only"] is False
        assert meta["is_destructive"] is False
        assert meta["is_concurrent_safe"] is False
        assert meta["requires_backend"] is False

    def test_shell_is_destructive(self):
        meta = get_tool_meta("shell")
        assert meta["is_destructive"] is True
        assert meta["is_read_only"] is False

    def test_file_read_is_read_only(self):
        meta = get_tool_meta("file_read")
        assert meta["is_read_only"] is True
        assert meta["is_destructive"] is False
        assert meta["is_concurrent_safe"] is True

    def test_grep_is_concurrent_safe(self):
        meta = get_tool_meta("grep")
        assert meta["is_concurrent_safe"] is True
        assert meta["is_read_only"] is True

    def test_image_generate_requires_backend(self):
        meta = get_tool_meta("image_generate")
        assert meta["requires_backend"] is True

    def test_meta_factory_defaults(self):
        m = _meta()
        assert m["is_read_only"] is False
        assert m["is_destructive"] is False
        assert m["is_concurrent_safe"] is False
        assert m["requires_backend"] is False
        assert m["requires_path"] is False

    def test_meta_factory_overrides(self):
        m = _meta(is_read_only=True, is_destructive=True)
        assert m["is_read_only"] is True
        assert m["is_destructive"] is True

    def test_think_tools_all_read_only(self):
        """All tools in THINK_TOOLS should be marked read_only."""
        for tool in THINK_TOOLS:
            name = tool["function"]["name"]
            meta = get_tool_meta(name)
            assert meta["is_read_only"] is True, f"{name} in THINK_TOOLS but not read_only"

    def test_shell_not_in_think_tools(self):
        think_names = {t["function"]["name"] for t in THINK_TOOLS}
        assert "shell" not in think_names

    def test_shell_not_in_edit_tools(self):
        edit_names = {t["function"]["name"] for t in EDIT_TOOLS}
        assert "shell" not in edit_names


class TestValidateToolInput:
    """Tests for input validation (pipeline stage 1)."""

    def test_valid_input(self):
        assert validate_tool_input("file_read", '{"path": "/tmp/test.txt"}') is None

    def test_valid_input_dict(self):
        assert validate_tool_input("file_read", {"path": "/tmp/test.txt"}) is None

    def test_invalid_json(self):
        result = validate_tool_input("file_read", "not json")
        assert result is not None
        assert "invalid arguments" in result

    def test_missing_required_param(self):
        result = validate_tool_input("file_read", "{}")
        assert result is not None
        assert "Missing required parameter" in result
        assert "path" in result

    def test_unknown_tool(self):
        result = validate_tool_input("nonexistent", "{}")
        assert result is not None
        assert "unknown tool" in result

    def test_non_dict_arguments(self):
        result = validate_tool_input("file_read", '"just a string"')
        assert result is not None
        assert "JSON object" in result

    def test_null_byte_in_path(self):
        result = validate_tool_input("file_read", '{"path": "/tmp/test\\u0000.txt"}')
        assert result is not None
        assert "null bytes" in result

    def test_optional_params_ok(self):
        """Tools with no required params should validate with empty args."""
        result = validate_tool_input("file_list", "{}")
        assert result is None

    def test_grep_requires_pattern(self):
        result = validate_tool_input("grep", "{}")
        assert result is not None
        assert "pattern" in result

    def test_grep_valid(self):
        assert validate_tool_input("grep", '{"pattern": "TODO"}') is None

    def test_shell_requires_command(self):
        result = validate_tool_input("shell", "{}")
        assert result is not None
        assert "command" in result

    def test_empty_path_rejected(self):
        result = validate_tool_input("file_read", '{"path": ""}')
        assert result is not None
        assert "requires" in result


class TestCheckToolPermissions:
    """Tests for permission checking (pipeline stage 2)."""

    def test_file_read_allowed_in_think(self):
        assert check_tool_permissions("file_read", "think") is None

    def test_shell_denied_in_think(self):
        result = check_tool_permissions("shell", "think")
        assert result is not None
        assert "destructive" in result or "not available" in result

    def test_shell_denied_in_edit(self):
        result = check_tool_permissions("shell", "edit")
        assert result is not None

    def test_shell_allowed_in_act(self):
        assert check_tool_permissions("shell", "act") is None

    def test_kb_search_allowed_in_think(self):
        assert check_tool_permissions("kb_search", "think") is None

    def test_image_generate_denied_in_think(self):
        result = check_tool_permissions("image_generate", "think")
        assert result is not None


class TestExecuteToolPipeline:
    """Tests for the full 3-stage execute pipeline."""

    def test_validation_error_returns_error_string(self, tmp_path):
        result = execute_tool("file_read", "{}", tmp_path)
        assert result.startswith("Error:")
        assert "Missing required" in result

    def test_permission_error_returns_error_string(self, tmp_path):
        result = execute_tool("shell", '{"command": "ls"}', tmp_path, mode="think")
        assert result.startswith("Error:")
        assert "not available" in result or "destructive" in result

    def test_successful_execution(self, tmp_path):
        test_file = tmp_path / "hello.txt"
        test_file.write_text("world")
        result = execute_tool("file_read", json.dumps({"path": str(test_file)}), tmp_path)
        assert result == "world"

    def test_mode_none_skips_permission_check(self, tmp_path):
        """When mode is None, skip permission check (backward compat)."""
        result = execute_tool("shell", '{"command": "echo ok"}', tmp_path, mode=None)
        assert "ok" in result

    def test_unknown_tool_error(self, tmp_path):
        result = execute_tool("bogus", '{"x": 1}', tmp_path)
        assert "Error:" in result
