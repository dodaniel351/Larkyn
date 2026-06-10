"""Writing profiles.

Profiles change *prompting only* — every profile uses the same model
(gemma4:e2b-it-qat). Each profile appends guidance to the base system prompt.
Custom profiles (key -> guidance text) are merged in from config.
"""

from __future__ import annotations

from dataclasses import dataclass

from hermes.core.interfaces import Msg
from hermes.prompt.smart_commands import SMART_COMMANDS_GUIDANCE
from hermes.prompt.system_prompt import BASE_SYSTEM_PROMPT
from hermes.prompt.vocabulary import vocabulary_clause


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    guidance: str  # appended to the base system prompt ("" for General)


BUILTIN_PROFILES: dict[str, Profile] = {
    "general": Profile(
        "general", "General Writing",
        "",
    ),
    "email": Profile(
        "email", "Email",
        "Format the result as a professional email. Keep any greeting and "
        "sign-off the speaker used; if they addressed someone, keep that. Use "
        "short paragraphs. Do not invent a subject line, recipient, or closing "
        "that the speaker did not say.",
    ),
    "technical": Profile(
        "technical", "Technical Documentation",
        "Produce concise technical documentation. Use precise, unambiguous "
        "language and consistent terminology. Prefer short declarative "
        "sentences. Preserve commands, code, file paths, and identifiers "
        "exactly as spoken.",
    ),
    "meeting_notes": Profile(
        "meeting_notes", "Meeting Notes",
        "Convert the speech into structured meeting notes. Use short bullet "
        "points grouped under clear headings (e.g. Discussion, Decisions, "
        "Action Items) when the content supports them. Capture every action "
        "item and owner mentioned. Do not invent items that were not said.",
    ),
    "exec_summary": Profile(
        "exec_summary", "Executive Summary",
        "Write in clear, business-oriented language suitable for executives. "
        "Lead with the key point. Keep it crisp and outcome-focused while "
        "preserving every substantive point the speaker made.",
    ),
    "clinical": Profile(
        "clinical", "Clinical Documentation",
        "Write as professional clinical documentation. Preserve all medical "
        "terminology, drug names, dosages, measurements, anatomy, and "
        "abbreviations exactly as spoken. Do not add, infer, or alter any "
        "clinical detail. Never invent findings.",
    ),
    "it_ops": Profile(
        "it_ops", "IT Operations",
        "Write as clear IT operations communication. Preserve hostnames, IP "
        "addresses, server names, ports, file paths, commands, and technical "
        "terminology exactly as spoken — do not normalize, reformat, or "
        "correct them. Keep numbers and identifiers verbatim.",
    ),
}

PROFILE_ORDER = list(BUILTIN_PROFILES.keys())


def all_profiles(custom_profiles: dict[str, str] | None = None) -> dict[str, Profile]:
    profiles = dict(BUILTIN_PROFILES)
    for key, guidance in (custom_profiles or {}).items():
        if key in profiles:
            continue  # built-ins win over a clashing custom key
        profiles[key] = Profile(key, key.replace("_", " ").title(), guidance or "")
    return profiles


def get_profile(key: str, custom_profiles: dict[str, str] | None = None) -> Profile:
    return all_profiles(custom_profiles).get(key, BUILTIN_PROFILES["general"])


def build_system_prompt(profile: Profile, vocabulary: list[str]) -> str:
    parts = [BASE_SYSTEM_PROMPT, SMART_COMMANDS_GUIDANCE]
    if profile.guidance:
        parts.append(f"Writing profile — {profile.name}:\n{profile.guidance}")
    clause = vocabulary_clause(vocabulary)
    if clause:
        parts.append(clause)
    return "\n\n".join(parts)


def build_messages(transcript: str, profile: Profile, vocabulary: list[str]) -> list[Msg]:
    """Assemble the chat messages for a rewrite request."""
    system = build_system_prompt(profile, vocabulary)
    return [Msg("system", system), Msg("user", transcript.strip())]
