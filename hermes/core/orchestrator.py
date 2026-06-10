"""The dictation pipeline orchestrator.

Implements the spec pipeline:

    Audio -> Whisper -> Raw Transcript -> gemma4:e2b-it-qat -> Final Output

A single global hotkey toggles recording. The first press starts capture; the
second stops it and runs transcription + rewrite + delivery on a background
thread so the UI never blocks. State changes are emitted as Qt signals.

The raw transcript is never delivered unless Raw Mode is enabled (spec).
"""

from __future__ import annotations

import datetime
import logging
import threading
import time

from PySide6.QtCore import QObject, Signal

from hermes.config import AppConfig
from hermes.core.interfaces import (
    AudioCapture,
    HistoryStore,
    LLMProvider,
    ModelParams,
    OutputMode,
    PipelineState,
    Session,
    Transcriber,
)
from hermes.prompt.profiles import build_messages, get_profile
from hermes.prompt.vocabulary import enforce_vocabulary

log = logging.getLogger("hermes.pipeline")


class Orchestrator(QObject):
    # Emitted on every pipeline state transition (PipelineState value).
    stateChanged = Signal(str)
    # Emitted with the completed Session on success.
    finished = Signal(object)
    # Emitted with a human-readable message on failure / no-speech.
    failed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        capture: AudioCapture,
        transcriber: Transcriber,
        llm: LLMProvider,
        sink,  # OutputSink
        history: HistoryStore,
    ) -> None:
        super().__init__()
        self._config = config
        self._capture = capture
        self._transcriber = transcriber
        self._llm = llm
        self._sink = sink
        self._history = history

        self._state = PipelineState.IDLE
        self._profile_key = config.profile_default
        self._lock = threading.Lock()
        self._t0: float | None = None

    # --- live settings ------------------------------------------------------
    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def profile_key(self) -> str:
        return self._profile_key

    def set_profile(self, key: str) -> None:
        self._profile_key = key

    def set_output_mode(self, mode: str) -> None:
        self._config.output.mode = mode

    def set_raw_mode(self, enabled: bool) -> None:
        self._config.output.raw_mode = enabled

    def set_llm_provider(self, llm) -> None:
        """Swap the rewrite backend (e.g. after settings change)."""
        self._llm = llm

    def set_transcriber(self, transcriber: Transcriber) -> None:
        """Swap the STT backend (e.g. after Whisper settings change)."""
        self._transcriber = transcriber

    @property
    def history(self) -> HistoryStore:
        return self._history

    def _set_state(self, state: PipelineState) -> None:
        self._state = state
        self.stateChanged.emit(state.value)

    # --- control ------------------------------------------------------------
    def toggle(self) -> None:
        """Start recording, or stop+process if already recording."""
        with self._lock:
            log.info("Hotkey toggle received (state=%s)", self._state.value)
            if self._state == PipelineState.RECORDING:
                self._stop_and_process()
            elif self._state in (PipelineState.IDLE, PipelineState.ERROR):
                self._start()
            else:
                log.info("Busy (%s); ignoring toggle.", self._state.value)

    # Push-to-talk: hold the hotkey to record, release to process.
    _MIN_HOLD_S = 0.35  # shorter holds are treated as accidental taps

    def on_hotkey_down(self) -> None:
        if self._config.hotkey.mode != "hold":
            self.toggle()
            return
        with self._lock:
            if self._state in (PipelineState.IDLE, PipelineState.ERROR):
                log.info("Hotkey down — recording while held")
                self._start()

    def on_hotkey_up(self) -> None:
        if self._config.hotkey.mode != "hold":
            return
        with self._lock:
            if self._state != PipelineState.RECORDING:
                return
            held = time.perf_counter() - (self._t0 or 0)
            if held < self._MIN_HOLD_S:
                log.info("Hotkey up after %.2fs — too short, discarding", held)
                self._capture.stop()
                self._set_state(PipelineState.IDLE)
                return
            log.info("Hotkey up after %.2fs — processing", held)
            self._stop_and_process()

    def _start(self) -> None:
        self._capture.start()
        self._t0 = time.perf_counter()
        self._set_state(PipelineState.RECORDING)

    def _stop_and_process(self) -> None:
        audio = self._capture.stop()
        self._set_state(PipelineState.TRANSCRIBING)
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    # --- worker thread ------------------------------------------------------
    def _process(self, audio) -> None:
        try:
            samples = 0 if audio is None else len(audio)
            log.info("Processing %d samples (%.1fs)", samples, samples / max(1, self._capture.sample_rate))
            transcript = self._transcriber.transcribe(audio, self._capture.sample_rate)
            raw = (transcript.text or "").strip()
            log.info("Transcript: %r", raw)
            if not raw:
                self._set_state(PipelineState.IDLE)
                self.failed.emit("No speech detected.")
                return

            if self._config.output.raw_mode:
                from hermes.prompt.smart_commands import apply_smart_commands

                final = apply_smart_commands(raw)
            else:
                self._set_state(PipelineState.REWRITING)
                final = self._rewrite(raw)

            self._set_state(PipelineState.DELIVERING)
            mode = OutputMode(self._config.output.mode)
            self._sink.deliver(final, mode)

            session = self._record_session(raw, final, mode)
            log.info("Delivered (%s, %dms): %r", mode.value, session.duration_ms, final)
            self._set_state(PipelineState.IDLE)
            self.finished.emit(session)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            log.exception("Pipeline failed")
            self._set_state(PipelineState.ERROR)
            self.failed.emit(str(exc))

    def _rewrite(self, raw: str) -> str:
        profile = get_profile(self._profile_key, self._config.custom_profiles)
        messages = build_messages(raw, profile, self._config.vocabulary)
        params = ModelParams(
            model=self._config.llm.model,
            temperature=self._config.llm.temperature,
            top_p=self._config.llm.top_p,
            max_tokens=self._config.llm.max_tokens,
        )
        final = self._llm.rewrite(messages, params).strip()
        # If the model returns nothing, fall back to the raw transcript rather
        # than delivering an empty paste.
        final = final or raw
        # Guarantee custom vocabulary is preserved exactly, even if the model
        # (or Whisper) garbled it.
        return enforce_vocabulary(final, self._config.vocabulary)

    def _record_session(self, raw: str, final: str, mode: OutputMode) -> Session:
        elapsed_ms = int((time.perf_counter() - (self._t0 or time.perf_counter())) * 1000)
        session = Session(
            timestamp=datetime.datetime.now().isoformat(timespec="seconds"),
            profile=self._profile_key,
            raw_transcript=raw,
            rewritten=final,
            duration_ms=elapsed_ms,
            model=self._config.llm.model,
            output_mode=mode.value,
        )
        try:
            self._history.add(session)
        except Exception:
            pass  # history is best-effort; never block delivery
        return session
