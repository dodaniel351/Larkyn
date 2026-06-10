"""Abstract interfaces + data types for the Larkyn pipeline.

Every stage of the pipeline is defined as an ABC so the concrete backend can be
swapped without touching the orchestrator (spec: "All components should be
replaceable"). Data passed between stages uses plain dataclasses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import numpy as np


class OutputMode(str, Enum):
    PASTE = "paste"          # copy to clipboard then auto-paste into active app
    CLIPBOARD = "clipboard"  # copy only
    DRAFT = "draft"          # store without pasting


class PipelineState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    REWRITING = "rewriting"
    DELIVERING = "delivering"
    ERROR = "error"


@dataclass
class Msg:
    """A single chat message (OpenAI-style)."""
    role: str   # "system" | "user" | "assistant"
    content: str


@dataclass
class ModelParams:
    model: str
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 4096


@dataclass
class TranscriptResult:
    text: str
    language: str | None = None
    duration_s: float = 0.0  # detected audio duration


@dataclass
class Session:
    """A completed dictation, persisted to history."""
    timestamp: str       # ISO 8601
    profile: str
    raw_transcript: str
    rewritten: str
    duration_ms: int     # end-to-end (record + process)
    model: str
    output_mode: str
    id: int | None = None


# --- Pipeline stage contracts ----------------------------------------------

class AudioCapture(ABC):
    @abstractmethod
    def start(self) -> None:
        """Begin recording from the default input device."""

    @abstractmethod
    def stop(self) -> np.ndarray:
        """Stop recording and return mono float32 samples."""

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        ...


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> TranscriptResult:
        ...


class LLMProvider(ABC):
    @abstractmethod
    def rewrite(self, messages: list[Msg], params: ModelParams) -> str:
        """Return the final rewritten text for the given chat messages."""


class OutputSink(ABC):
    @abstractmethod
    def deliver(self, text: str, mode: OutputMode) -> None:
        ...


class HistoryStore(ABC):
    @abstractmethod
    def add(self, session: Session) -> int:
        """Persist a session; return its new row id."""

    @abstractmethod
    def search(self, query: str, limit: int = 50) -> list[Session]:
        ...

    @abstractmethod
    def recent(self, limit: int = 50) -> list[Session]:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def delete(self, session_id: int) -> None:
        ...
