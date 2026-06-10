"""faster-whisper transcription engine (CTranslate2 backend).

Auto-detects CUDA (float16 on the GPU) and falls back to CPU (int8) so the app
runs on any machine. On Windows the NVIDIA cuBLAS/cuDNN DLLs shipped by the
``nvidia-*-cu12`` pip wheels are not on PATH by default, so we add their
directories to the DLL search path before importing faster-whisper.
"""

from __future__ import annotations

import logging
import os
import sys

import numpy as np

from larkyn.core.interfaces import Transcriber, TranscriptResult

log = logging.getLogger("larkyn.stt")


def _enable_cuda_dlls() -> None:
    """Best-effort: make pip-installed CUDA DLLs discoverable on Windows.

    The ``nvidia-*-cu12`` wheels drop their DLLs under ``nvidia/<pkg>/bin``. We
    must do *both* of the following before CTranslate2 loads them:
      * prepend those dirs to PATH — CTranslate2 loads cuBLAS/cuDNN at runtime
        via a plain ``LoadLibrary``, which searches PATH (not add_dll_directory);
      * call ``os.add_dll_directory`` so dependent DLLs resolve too.
    """
    if sys.platform != "win32":
        return
    bin_dirs: list[str] = []
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: CUDA DLLs are shipped in the bundle's "cuda" dir
        # (under _internal for onedir builds — that's what _MEIPASS points to).
        for base in (getattr(sys, "_MEIPASS", None), os.path.dirname(sys.executable)):
            if base:
                bundled = os.path.join(base, "cuda")
                if os.path.isdir(bundled):
                    bin_dirs.append(bundled)
    else:
        try:
            import nvidia  # type: ignore
        except Exception:
            nvidia = None
        if nvidia is not None:
            for root in getattr(nvidia, "__path__", []):
                for dirpath, _dirnames, _files in os.walk(root):
                    if os.path.basename(dirpath).lower() == "bin":
                        bin_dirs.append(dirpath)
    if not bin_dirs:
        return
    os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        for dirpath in bin_dirs:
            try:
                os.add_dll_directory(dirpath)
            except Exception:
                pass


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Simple linear resample (capture is already 16 kHz; this is a safety net)."""
    if src_sr == dst_sr or audio.size == 0:
        return audio
    duration = audio.shape[0] / float(src_sr)
    dst_len = int(round(duration * dst_sr))
    if dst_len <= 0:
        return np.zeros(0, dtype=np.float32)
    src_idx = np.linspace(0.0, audio.shape[0] - 1, num=dst_len)
    return np.interp(src_idx, np.arange(audio.shape[0]), audio).astype(np.float32)


class FasterWhisperEngine(Transcriber):
    def __init__(
        self,
        model: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "auto",
        language: str | None = None,
        beam_size: int = 1,
        vad_filter: bool = True,
    ) -> None:
        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._beam_size = beam_size
        self._vad_filter = vad_filter
        self._model = None
        self._resolved: tuple[str, str] | None = None

    def _resolve_device(self) -> tuple[str, str]:
        device = self._device
        if device == "auto":
            device = "cpu"
            try:
                import ctranslate2  # type: ignore

                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
            except Exception:
                device = "cpu"
        compute = self._compute_type
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"
        return device, compute

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        _enable_cuda_dlls()
        from faster_whisper import WhisperModel

        device, compute = self._resolve_device()
        try:
            self._model = WhisperModel(self._model_name, device=device, compute_type=compute)
            self._resolved = (device, compute)
        except Exception:
            # GPU init failed (missing CUDA libs, OOM, etc.) -> CPU fallback.
            log.exception("Whisper init on %s failed; falling back to CPU int8", device)
            self._model = WhisperModel(self._model_name, device="cpu", compute_type="int8")
            self._resolved = ("cpu", "int8")
        log.info("Whisper model %s loaded on %s (%s)", self._model_name, *self._resolved)

    @property
    def resolved_device(self) -> tuple[str, str] | None:
        return self._resolved

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> TranscriptResult:
        if audio is None or len(audio) == 0:
            return TranscriptResult(text="", duration_s=0.0)
        self._ensure_model()
        if sample_rate != 16000:
            audio = _resample(audio, sample_rate, 16000)
        segments, info = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=self._beam_size,
            vad_filter=self._vad_filter,
        )
        text = "".join(seg.text for seg in segments).strip()
        return TranscriptResult(
            text=text,
            language=getattr(info, "language", None),
            duration_s=float(getattr(info, "duration", 0.0) or 0.0),
        )
