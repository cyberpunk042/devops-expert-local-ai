"""Tests for permission modes."""

from aicp.core.modes import Mode


def test_think_mode_permissions():
    assert Mode.THINK.can_read is True
    assert Mode.THINK.can_edit is False
    assert Mode.THINK.can_execute is False


def test_edit_mode_permissions():
    assert Mode.EDIT.can_read is True
    assert Mode.EDIT.can_edit is True
    assert Mode.EDIT.can_execute is False


def test_act_mode_permissions():
    assert Mode.ACT.can_read is True
    assert Mode.ACT.can_edit is True
    assert Mode.ACT.can_execute is True
