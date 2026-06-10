"""Non-interactive pipeline self-test.

Drives the real pipeline end-to-end without the mic/hotkey/paste layer:

    WAV file -> faster-whisper (GPU) -> profile+vocabulary prompt -> gemma4 -> output

Usage:
    python scripts/selftest.py <wav> [profile_key] [--expect term1,term2,...]

Reports the resolved Whisper device, the raw transcript, the rewritten output,
cold/warm transcription latency, rewrite latency, and whether any --expect terms
were preserved verbatim.
"""

from __future__ import annotations

import os
import sys
import time
import wave

# Make the project root importable when run as `python scripts/selftest.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from hermes.config import AppConfig
from hermes.core.interfaces import ModelParams
from hermes.llm.openai_provider import OpenAIProvider
from hermes.prompt.profiles import build_messages, get_profile
from hermes.prompt.vocabulary import enforce_vocabulary
from hermes.stt.faster_whisper_engine import FasterWhisperEngine


def read_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        nframes = w.getnframes()
        channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        raw = w.readframes(nframes)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[sampwidth]
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if sampwidth == 2:
        data /= 32768.0
    elif sampwidth == 4:
        data /= 2147483648.0
    else:  # 8-bit unsigned
        data = (data - 128.0) / 128.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data.astype(np.float32), sr


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/selftest.py <wav> [profile] [--expect a,b]")
        return 2

    wav_path = sys.argv[1]
    profile_key = "general"
    expect: list[str] = []
    args = sys.argv[2:]
    if "--expect" in args:
        i = args.index("--expect")
        expect = [t.strip() for t in args[i + 1].split(",") if t.strip()]
        args = args[:i] + args[i + 2 :]
    if args:
        profile_key = args[0]

    cfg = AppConfig()
    audio, sr = read_wav(wav_path)
    print(f"[audio] {len(audio) / sr:.1f}s @ {sr} Hz  ({wav_path})")

    engine = FasterWhisperEngine(
        model=cfg.stt.model,
        device=cfg.stt.device,
        compute_type=cfg.stt.compute_type,
        beam_size=cfg.stt.beam_size,
        vad_filter=cfg.stt.vad_filter,
    )

    t0 = time.perf_counter()
    engine.transcribe(audio, sr)  # cold: also loads the model
    cold = time.perf_counter() - t0

    t0 = time.perf_counter()
    tr = engine.transcribe(audio, sr)  # warm
    warm = time.perf_counter() - t0

    print(f"[whisper] device={engine.resolved_device}  model={cfg.stt.model}")
    print(f"[whisper] cold(incl. load)={cold:.2f}s  warm={warm:.2f}s")
    print(f"[RAW] {tr.text!r}")

    if cfg.llm.provider == "ollama":
        from hermes.llm.ollama_provider import OllamaNativeProvider

        llm = OllamaNativeProvider(
            endpoint=cfg.llm.endpoint, timeout_s=cfg.llm.timeout_s, think=cfg.llm.think
        )
    else:
        llm = OpenAIProvider(
            endpoint=cfg.llm.endpoint,
            api_key=cfg.llm.api_key,
            timeout_s=cfg.llm.timeout_s,
        )
    profile = get_profile(profile_key, cfg.custom_profiles)
    messages = build_messages(tr.text, profile, cfg.vocabulary)
    params = ModelParams(
        model=cfg.llm.model,
        temperature=cfg.llm.temperature,
        top_p=cfg.llm.top_p,
        max_tokens=cfg.llm.max_tokens,
    )

    t0 = time.perf_counter()
    rewritten = llm.rewrite(messages, params)
    rewrite = time.perf_counter() - t0
    final = enforce_vocabulary(rewritten, cfg.vocabulary)

    print(f"[profile] {profile.name}")
    print(f"[REWRITTEN] {rewritten!r}")
    if final != rewritten:
        print(f"[FINAL(vocab)] {final!r}")
    else:
        print(f"[FINAL] {final!r}")
    print(f"[latency] warm transcribe={warm:.2f}s + rewrite={rewrite:.2f}s = {warm + rewrite:.2f}s")

    ok = True
    for term in expect:
        present = term in final
        ok = ok and present
        print(f"[vocab] preserve {term!r}: {'OK' if present else 'MISSING'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
