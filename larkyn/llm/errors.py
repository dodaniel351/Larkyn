"""User-facing LLM error type.

The orchestrator surfaces ``str(exception)`` directly in a toast notification,
so provider failures must carry an actionable, plain-English message — not an
HTTP traceback. ``LLMError`` marks messages that are already user-ready.
"""


class LLMError(RuntimeError):
    """A rewrite failure with a message written for the end user."""
