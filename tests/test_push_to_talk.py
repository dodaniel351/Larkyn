"""Orchestrator push-to-talk behavior, exercised with fake pipeline components."""

import time

import numpy as np
import pytest

from hermes.config import AppConfig
from hermes.core.interfaces import (
    AudioCapture,
    HistoryStore,
    LLMProvider,
    OutputMode,
    OutputSink,
    PipelineState,
    Transcriber,
    TranscriptResult,
)


class FakeCapture(AudioCapture):
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1
        return np.zeros(16000, dtype=np.float32)

    @property
    def sample_rate(self):
        return 16000


class FakeTranscriber(Transcriber):
    def transcribe(self, audio, sample_rate):
        return TranscriptResult(text="hello world")


class FakeLLM(LLMProvider):
    def rewrite(self, messages, params):
        return "Hello world."


class FakeSink(OutputSink):
    def __init__(self):
        self.delivered = []

    def deliver(self, text, mode: OutputMode):
        self.delivered.append((text, mode))


class FakeHistory(HistoryStore):
    def __init__(self):
        self.rows = []

    def add(self, session):
        self.rows.append(session)
        return len(self.rows)

    def search(self, query, limit=50):
        return []

    def recent(self, limit=50):
        return list(self.rows)

    def count(self):
        return len(self.rows)

    def delete(self, session_id):
        pass


@pytest.fixture
def orch(qt_app):
    from hermes.core.orchestrator import Orchestrator

    cfg = AppConfig()
    cfg.hotkey.mode = "hold"
    capture = FakeCapture()
    sink = FakeSink()
    o = Orchestrator(cfg, capture, FakeTranscriber(), FakeLLM(), sink, FakeHistory())
    return o, cfg, capture, sink


@pytest.fixture(scope="session")
def qt_app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _wait_idle(o, timeout=5.0):
    t0 = time.time()
    while o.state != PipelineState.IDLE and time.time() - t0 < timeout:
        time.sleep(0.02)


def test_hold_records_while_held_and_processes_on_release(orch):
    o, cfg, capture, sink = orch
    o.on_hotkey_down()
    assert o.state == PipelineState.RECORDING
    assert capture.started == 1
    time.sleep(0.4)  # exceed the short-tap guard
    o.on_hotkey_up()
    _wait_idle(o)
    assert capture.stopped == 1
    assert sink.delivered and sink.delivered[0][0] == "Hello world."


def test_short_tap_is_discarded(orch):
    o, cfg, capture, sink = orch
    o.on_hotkey_down()
    o.on_hotkey_up()  # released almost immediately
    assert o.state == PipelineState.IDLE
    assert capture.stopped == 1
    assert sink.delivered == []


def test_toggle_mode_ignores_release(orch):
    o, cfg, capture, sink = orch
    cfg.hotkey.mode = "toggle"
    o.on_hotkey_down()       # acts as toggle -> start
    assert o.state == PipelineState.RECORDING
    o.on_hotkey_up()         # ignored in toggle mode
    assert o.state == PipelineState.RECORDING
    time.sleep(0.05)
    o.on_hotkey_down()       # second press -> stop & process
    _wait_idle(o)
    assert sink.delivered and sink.delivered[0][0] == "Hello world."
