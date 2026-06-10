"""Microphone capture via sounddevice (PortAudio).

Records mono float32 at 16 kHz — the rate Whisper expects — into an in-memory
buffer between ``start()`` and ``stop()``. No audio ever touches disk.
"""

from __future__ import annotations

import threading

import numpy as np

from hermes.core.interfaces import AudioCapture


class SoundDeviceCapture(AudioCapture):
    def __init__(self, sample_rate: int = 16000) -> None:
        self._sr = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._lock = threading.Lock()

    @property
    def sample_rate(self) -> int:
        return self._sr

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        # Called on PortAudio's thread; copy because the buffer is reused.
        with self._lock:
            self._frames.append(indata.copy())

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            self._frames = []
        self._stream = sd.InputStream(
            samplerate=self._sr,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        with self._lock:
            frames = self._frames
            self._frames = []
        if not frames:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(frames, axis=0).reshape(-1).astype(np.float32)
