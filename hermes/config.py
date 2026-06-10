"""Application configuration.

Config is validated with pydantic and persisted as JSON in
``%APPDATA%\\Larkyn\\config.json``. Defaults are 100% local and match
the spec: the rewrite model is ``gemma4:e2b-it-qat`` served over an
OpenAI-compatible endpoint (Ollama) at ``http://localhost:11434/v1``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

APP_DIR_NAME = "Larkyn"
_LEGACY_DIR_NAME = "HermesDictate"  # pre-rename data dir, migrated on first run

# --- Spec defaults (do not silently change the model) -----------------------
DEFAULT_MODEL = "gemma4:e2b-it-qat"
DEFAULT_ENDPOINT = "http://localhost:11434/v1"

DEFAULT_VOCABULARY = [
    "eClinicalWorks",
    "Phreesia",
    "Dermatology Solutions Group",
    "LibreNMS",
    "Graylog",
    "OpenWebUI",
]


def app_data_dir() -> Path:
    """Per-user data directory (created if missing).

    Migrates the legacy "HermesDictate" directory (config + history) to the
    new name the first time Larkyn runs.
    """
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_DIR_NAME
    if not path.exists():
        legacy = Path(base) / _LEGACY_DIR_NAME
        if legacy.is_dir():
            try:
                legacy.rename(path)
            except OSError:
                pass  # legacy dir in use (old app running) -> start fresh
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return app_data_dir() / "config.json"


def history_db_path() -> Path:
    return app_data_dir() / "history.db"


class LLMConfig(BaseModel):
    # "ollama" = native API (supports think:false — sub-second rewrites with
    # gemma4:e2b-it-qat). "openai" = any OpenAI-compatible endpoint.
    provider: str = "ollama"
    endpoint: str = DEFAULT_ENDPOINT
    model: str = DEFAULT_MODEL
    # Ollama ignores the key, but the OpenAI client requires a non-empty value.
    api_key: str = "ollama"
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 4096
    timeout_s: int = 120
    # Reasoning models only: enabling thinking adds seconds of latency per
    # rewrite for marginal quality gain on this task.
    think: bool = False


class STTConfig(BaseModel):
    engine: str = "faster-whisper"
    model: str = "large-v3-turbo"
    device: str = "auto"          # auto | cuda | cpu
    compute_type: str = "auto"    # auto | float16 | int8 | int8_float16
    language: str | None = None   # None = auto-detect
    beam_size: int = 1            # 1 = greedy (lowest latency)
    vad_filter: bool = True       # trim silence for speed/accuracy


class HotkeyConfig(BaseModel):
    # Key combo, e.g. "<ctrl>+<alt>+<space>" or modifier-only "<ctrl>+<cmd>".
    toggle: str = "<ctrl>+<alt>+<space>"
    # "hold" = push-to-talk: record while the combo is held, process on release.
    # "toggle" = press once to start, press again to stop.
    mode: str = "hold"


class OutputConfig(BaseModel):
    mode: str = "paste"           # paste | clipboard | draft
    raw_mode: bool = False        # True = paste raw transcript, skip rewrite
    paste_delay_ms: int = 120     # let the target window regain focus before Ctrl+V


class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    hotkey: HotkeyConfig = Field(default_factory=HotkeyConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    profile_default: str = "general"
    theme: str = "dark"           # dark | light | auto
    vocabulary: list[str] = Field(default_factory=lambda: list(DEFAULT_VOCABULARY))
    # key -> guidance text appended to the base system prompt
    custom_profiles: dict[str, str] = Field(default_factory=dict)

    # --- persistence --------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cfg = cls.model_validate(data)
                # Migration: older configs default to the OpenAI-compat path even
                # for a local Ollama, which can't disable thinking (slow). Switch
                # them to the native provider.
                if cfg.llm.provider == "openai" and "localhost:11434" in cfg.llm.endpoint:
                    cfg.llm.provider = "ollama"
                    cfg.save(path)
                return cfg
            except Exception:
                # Corrupt config -> fall back to defaults rather than crash.
                return cls()
        cfg = cls()
        cfg.save(path)  # write defaults on first launch
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
