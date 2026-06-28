"""Token overflow recovery for Anthropic API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anthropic

from tsave.core.compressor import CompressedResult, compress


@dataclass
class OverflowRecoveryResult:
    """Result of an overflow recovery attempt."""
    response: Any
    compressed_result: CompressedResult | None
    recovery_attempted: bool
    recovery_successful: bool

    def format(self) -> str:
        if not self.recovery_attempted:
            return "No overflow recovery needed."
        if not self.recovery_successful:
            return "Overflow recovery attempted but failed."
        cr = self.compressed_result
        return (
            f"Overflow recovery successful.\n"
            f"{cr.format()}"
        )


def _is_overflow_error(exc: Exception) -> bool:
    """Detect context length exceeded errors from Anthropic API."""
    if isinstance(exc, anthropic.BadRequestError):
        msg = str(exc).lower()
        return any(phrase in msg for phrase in [
            "prompt is too long",
            "context_length_exceeded",
            "too many tokens",
            "maximum context length",
        ])
    return False


def create_with_overflow_recovery(
    client: anthropic.Anthropic,
    *,
    model: str,
    messages: list[dict],
    keep_last_n: int = 4,
    max_retries: int = 3,
    query: str | None = None,
    **kwargs: Any,
) -> OverflowRecoveryResult:
    """
    Call the Anthropic API with automatic overflow recovery.

    If the API returns a context_length_exceeded error, automatically
    compresses the conversation history and retries.

    Args:
        client: Anthropic client instance.
        model: Model string e.g. 'claude-sonnet-4-6'.
        messages: Conversation history.
        keep_last_n: Number of recent messages to always preserve.
        max_retries: Maximum compression/retry attempts.
        query: Optional query string to guide relevance scoring.
        **kwargs: Extra args passed to client.messages.create()
                  (e.g. max_tokens, system, tools).

    Returns:
        OverflowRecoveryResult with the API response and compression info.

    Example:
        result = create_with_overflow_recovery(
            client,
            model="claude-sonnet-4-6",
            messages=history,
            max_tokens=1024,
        )
        reply = result.response.content[0].text
    """
    current_messages = list(messages)
    last_compressed: CompressedResult | None = None

    # First attempt — no compression
    try:
        response = client.messages.create(
            model=model,
            messages=current_messages,
            **kwargs,
        )
        return OverflowRecoveryResult(
            response=response,
            compressed_result=None,
            recovery_attempted=False,
            recovery_successful=False,
        )
    except Exception as exc:
        if not _is_overflow_error(exc):
            raise

    # Overflow detected — compress and retry
    for attempt in range(max_retries):
        # Increase aggressiveness each retry
        keep_n = max(2, keep_last_n - attempt)

        try:
            compressed = compress(
                client,
                model=model,
                messages=current_messages,
                keep_last_n=keep_n,
                query=query,
            )
            last_compressed = compressed
            current_messages = compressed.compressed_messages

            response = client.messages.create(
                model=model,
                messages=current_messages,
                **kwargs,
            )
            return OverflowRecoveryResult(
                response=response,
                compressed_result=last_compressed,
                recovery_attempted=True,
                recovery_successful=True,
            )

        except Exception as exc:
            if not _is_overflow_error(exc):
                raise
            continue

    raise RuntimeError(
        f"Token overflow could not be resolved after {max_retries} "
        f"compression attempts. Consider reducing your conversation "
        f"history manually or increasing keep_last_n."
    )
