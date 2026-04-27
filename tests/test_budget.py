"""Tests for budget limits."""


from aicp.core.budget import BudgetLimits, load_budget_from_config


def test_budget_no_limits_exceeded():
    b = BudgetLimits()
    b.start()
    assert b.check() is None


def test_budget_cost_exceeded():
    b = BudgetLimits(max_cost_usd=1.0)
    b.start()
    b.update(cost=1.5)
    result = b.check()
    assert result is not None
    assert "Cost" in result


def test_budget_step_exceeded():
    b = BudgetLimits(max_steps=3)
    b.start()
    b.update(steps=3)
    result = b.check()
    assert result is not None
    assert "Step" in result


def test_budget_file_exceeded():
    b = BudgetLimits(max_file_changes=5)
    b.start()
    b.update(files=6)
    result = b.check()
    assert result is not None
    assert "File" in result


def test_budget_summary():
    b = BudgetLimits(max_cost_usd=5.0, max_steps=10)
    b.start()
    b.update(cost=1.23, steps=3, files=2)
    summary = b.summary()
    assert "$1.23" in summary
    assert "3 / 10" in summary


def test_load_budget_from_config():
    config = {"budget": {"max_cost_usd": 2.5, "max_steps": 5}}
    b = load_budget_from_config(config)
    assert b.max_cost_usd == 2.5
    assert b.max_steps == 5


def test_load_budget_defaults():
    b = load_budget_from_config({})
    assert b.max_cost_usd == 10.0
    assert b.max_steps == 20
