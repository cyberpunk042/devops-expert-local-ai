"""Tests for aicp.core.events — event emitter system."""

import threading
from unittest.mock import MagicMock

import pytest

from aicp.core.events import EventEmitter, get_emitter, reset_emitter


class TestEventEmitter:
    """Unit tests for EventEmitter."""

    def setup_method(self):
        self.emitter = EventEmitter()

    # ── Basic registration and emission ──

    def test_on_and_emit(self):
        cb = MagicMock()
        self.emitter.on("task_start", cb)
        self.emitter.emit("task_start", {"prompt": "hello"})
        cb.assert_called_once_with("task_start", {"prompt": "hello"})

    def test_emit_returns_callback_count(self):
        self.emitter.on("x", MagicMock())
        self.emitter.on("x", MagicMock())
        assert self.emitter.emit("x") == 2

    def test_emit_no_listeners_returns_zero(self):
        assert self.emitter.emit("nothing") == 0

    def test_emit_default_data_is_empty_dict(self):
        cb = MagicMock()
        self.emitter.on("test", cb)
        self.emitter.emit("test")
        cb.assert_called_once_with("test", {})

    # ── Multiple listeners ──

    def test_multiple_listeners_same_event(self):
        cb1, cb2 = MagicMock(), MagicMock()
        self.emitter.on("e", cb1)
        self.emitter.on("e", cb2)
        self.emitter.emit("e", {"k": "v"})
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_different_events_isolated(self):
        cb_a, cb_b = MagicMock(), MagicMock()
        self.emitter.on("a", cb_a)
        self.emitter.on("b", cb_b)
        self.emitter.emit("a")
        cb_a.assert_called_once()
        cb_b.assert_not_called()

    # ── Removal ──

    def test_off_removes_callback(self):
        cb = MagicMock()
        self.emitter.on("x", cb)
        self.emitter.off("x", cb)
        self.emitter.emit("x")
        cb.assert_not_called()

    def test_off_nonexistent_is_noop(self):
        self.emitter.off("x", MagicMock())  # should not raise

    def test_off_wrong_event_is_noop(self):
        cb = MagicMock()
        self.emitter.on("a", cb)
        self.emitter.off("b", cb)  # wrong event
        self.emitter.emit("a")
        cb.assert_called_once()

    # ── Once ──

    def test_once_fires_once(self):
        cb = MagicMock()
        self.emitter.once("x", cb)
        self.emitter.emit("x")
        self.emitter.emit("x")
        cb.assert_called_once()

    def test_once_auto_removes(self):
        cb = MagicMock()
        self.emitter.once("x", cb)
        self.emitter.emit("x")
        assert self.emitter.listener_count("x") == 0

    # ── Error handling ──

    def test_callback_error_swallowed(self):
        """Failing callback should not prevent other callbacks from running."""
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        self.emitter.on("x", bad_cb)
        self.emitter.on("x", good_cb)
        count = self.emitter.emit("x")
        good_cb.assert_called_once()
        assert count == 1  # bad_cb didn't count

    def test_callback_exception_logged(self, caplog):
        bad_cb = MagicMock(side_effect=ValueError("test error"))
        self.emitter.on("x", bad_cb)
        import logging
        with caplog.at_level(logging.ERROR, logger="aicp.events"):
            self.emitter.emit("x")
        assert "Event callback failed" in caplog.text

    # ── Max listeners ──

    def test_max_listeners_enforced(self):
        emitter = EventEmitter(max_listeners=3)
        for _ in range(3):
            emitter.on("x", MagicMock())
        with pytest.raises(ValueError, match="Max listeners"):
            emitter.on("x", MagicMock())

    def test_max_listeners_per_event(self):
        """Max is per-event, not global."""
        emitter = EventEmitter(max_listeners=2)
        emitter.on("a", MagicMock())
        emitter.on("a", MagicMock())
        emitter.on("b", MagicMock())  # different event, should work
        with pytest.raises(ValueError):
            emitter.on("a", MagicMock())  # same event, exceeds

    # ── Clear ──

    def test_clear_all(self):
        self.emitter.on("a", MagicMock())
        self.emitter.on("b", MagicMock())
        self.emitter.clear()
        assert self.emitter.events == []

    def test_clear_specific_event(self):
        cb_a, cb_b = MagicMock(), MagicMock()
        self.emitter.on("a", cb_a)
        self.emitter.on("b", cb_b)
        self.emitter.clear("a")
        assert self.emitter.listener_count("a") == 0
        assert self.emitter.listener_count("b") == 1

    # ── Properties ──

    def test_events_property(self):
        self.emitter.on("x", MagicMock())
        self.emitter.on("y", MagicMock())
        assert sorted(self.emitter.events) == ["x", "y"]

    def test_listener_count(self):
        self.emitter.on("x", MagicMock())
        self.emitter.on("x", MagicMock())
        assert self.emitter.listener_count("x") == 2
        assert self.emitter.listener_count("y") == 0

    # ── Thread safety ──

    def test_concurrent_emit_and_register(self):
        """Concurrent on() and emit() should not crash."""
        results = []

        def listener(event, data):
            results.append(data.get("i"))

        def registerer():
            for i in range(20):
                self.emitter.on("concurrent", listener)

        def emitter_fn():
            for i in range(20):
                self.emitter.emit("concurrent", {"i": i})

        t1 = threading.Thread(target=registerer)
        t2 = threading.Thread(target=emitter_fn)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # No crash = pass. Results may vary due to race, but no exception.

    def test_concurrent_on_off(self):
        """Concurrent on() and off() should not crash."""
        cb = MagicMock()

        def adder():
            for _ in range(50):
                try:
                    self.emitter.on("race", cb)
                except ValueError:
                    pass

        def remover():
            for _ in range(50):
                self.emitter.off("race", cb)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=remover)
        t1.start()
        t2.start()
        t1.join()
        t2.join()


class TestGlobalEmitter:
    """Tests for module-level singleton."""

    def setup_method(self):
        reset_emitter()

    def teardown_method(self):
        reset_emitter()

    def test_get_emitter_returns_same_instance(self):
        e1 = get_emitter()
        e2 = get_emitter()
        assert e1 is e2

    def test_reset_emitter_creates_new_instance(self):
        e1 = get_emitter()
        reset_emitter()
        e2 = get_emitter()
        assert e1 is not e2

    def test_global_emitter_works(self):
        emitter = get_emitter()
        cb = MagicMock()
        emitter.on("global_test", cb)
        emitter.emit("global_test", {"ok": True})
        cb.assert_called_once_with("global_test", {"ok": True})
