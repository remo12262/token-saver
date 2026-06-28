from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import anthropic

from tsave.core.overflow import (
    OverflowRecoveryResult,
    _is_overflow_error,
    create_with_overflow_recovery,
)
from tsave.core.compressor import CompressedResult
from tests.conftest import FakeMessage, FakeTokenCount


def _make_bad_request(msg: str) -> anthropic.BadRequestError:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    return anthropic.BadRequestError(message=msg, response=mock_resp, body={})


def _make_overflow_error() -> anthropic.BadRequestError:
    return _make_bad_request("prompt is too long and exceeds limit")


def _make_compressed(messages: list[dict]) -> CompressedResult:
    return CompressedResult(
        original_messages=messages,
        compressed_messages=messages[-2:] if len(messages) >= 2 else messages,
        original_tokens=500,
        compressed_tokens=100,
    )


class TestIsOverflowError:
    def test_prompt_too_long(self):
        assert _is_overflow_error(_make_bad_request("prompt is too long"))

    def test_context_length_exceeded(self):
        assert _is_overflow_error(_make_bad_request("context_length_exceeded"))

    def test_too_many_tokens(self):
        assert _is_overflow_error(_make_bad_request("too many tokens"))

    def test_maximum_context_length(self):
        assert _is_overflow_error(_make_bad_request("maximum context length"))

    def test_case_insensitive(self):
        assert _is_overflow_error(_make_bad_request("Prompt Is Too Long"))

    def test_unrelated_bad_request_returns_false(self):
        assert not _is_overflow_error(_make_bad_request("invalid parameter value"))

    def test_non_anthropic_exception_returns_false(self):
        assert not _is_overflow_error(ValueError("too many tokens"))

    def test_generic_exception_returns_false(self):
        assert not _is_overflow_error(RuntimeError("something went wrong"))


class TestOverflowRecoveryResultFormat:
    def test_no_recovery(self):
        result = OverflowRecoveryResult(
            response=MagicMock(),
            compressed_result=None,
            recovery_attempted=False,
            recovery_successful=False,
        )
        assert result.format() == "No overflow recovery needed."

    def test_recovery_failed(self):
        result = OverflowRecoveryResult(
            response=None,
            compressed_result=None,
            recovery_attempted=True,
            recovery_successful=False,
        )
        assert result.format() == "Overflow recovery attempted but failed."

    def test_recovery_successful_includes_compression_info(self):
        mock_cr = MagicMock(spec=CompressedResult)
        mock_cr.format.return_value = "500 → 100 tokens (80.0%)"
        result = OverflowRecoveryResult(
            response=MagicMock(),
            compressed_result=mock_cr,
            recovery_attempted=True,
            recovery_successful=True,
        )
        text = result.format()
        assert "successful" in text
        assert "500 → 100 tokens (80.0%)" in text


class TestCreateWithOverflowRecovery:
    def _make_messages(self, n: int) -> list[dict]:
        msgs = []
        for i in range(n):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append({"role": role, "content": f"Message {i}"})
        return msgs

    def test_success_on_first_attempt_no_recovery(self, mock_client):
        messages = self._make_messages(4)
        result = create_with_overflow_recovery(
            mock_client,
            model="claude-sonnet-4-6",
            messages=messages,
            max_tokens=100,
        )
        assert result.recovery_attempted is False
        assert result.recovery_successful is False
        assert result.compressed_result is None
        assert result.response is mock_client.messages.create.return_value

    def test_recovery_on_overflow(self, mock_client):
        messages = self._make_messages(10)
        mock_client.messages.create.side_effect = [_make_overflow_error(), FakeMessage()]

        with patch("tsave.core.overflow.compress") as mock_compress:
            mock_compress.return_value = _make_compressed(messages)
            result = create_with_overflow_recovery(
                mock_client,
                model="claude-sonnet-4-6",
                messages=messages,
                max_tokens=100,
            )

        assert result.recovery_attempted is True
        assert result.recovery_successful is True
        assert result.compressed_result is not None
        assert mock_compress.call_count == 1

    def test_non_overflow_error_is_reraised_immediately(self, mock_client):
        mock_client.messages.create.side_effect = ValueError("bad value")
        with pytest.raises(ValueError, match="bad value"):
            create_with_overflow_recovery(
                mock_client,
                model="claude-sonnet-4-6",
                messages=self._make_messages(4),
                max_tokens=100,
            )

    def test_non_overflow_error_during_retry_is_reraised(self, mock_client):
        messages = self._make_messages(10)
        mock_client.messages.create.side_effect = [
            _make_overflow_error(),
            RuntimeError("network error"),
        ]

        with patch("tsave.core.overflow.compress") as mock_compress:
            mock_compress.return_value = _make_compressed(messages)
            with pytest.raises(RuntimeError, match="network error"):
                create_with_overflow_recovery(
                    mock_client,
                    model="claude-sonnet-4-6",
                    messages=messages,
                    max_tokens=100,
                )

    def test_all_retries_exhausted_raises_runtime_error(self, mock_client):
        messages = self._make_messages(10)
        mock_client.messages.create.side_effect = _make_overflow_error()

        with patch("tsave.core.overflow.compress") as mock_compress:
            mock_compress.return_value = _make_compressed(messages)
            with pytest.raises(RuntimeError, match="could not be resolved after 3"):
                create_with_overflow_recovery(
                    mock_client,
                    model="claude-sonnet-4-6",
                    messages=messages,
                    max_retries=3,
                    max_tokens=100,
                )

    def test_compress_called_max_retries_times(self, mock_client):
        messages = self._make_messages(10)
        mock_client.messages.create.side_effect = _make_overflow_error()

        with patch("tsave.core.overflow.compress") as mock_compress:
            mock_compress.return_value = _make_compressed(messages)
            with pytest.raises(RuntimeError):
                create_with_overflow_recovery(
                    mock_client,
                    model="claude-sonnet-4-6",
                    messages=messages,
                    max_retries=3,
                    max_tokens=100,
                )
            assert mock_compress.call_count == 3

    def test_keep_last_n_decreases_on_each_retry(self, mock_client):
        messages = self._make_messages(10)
        mock_client.messages.create.side_effect = [
            _make_overflow_error(),
            _make_overflow_error(),
            FakeMessage(),
        ]
        keep_n_calls = []

        def fake_compress(client, *, model, messages, keep_last_n, query):
            keep_n_calls.append(keep_last_n)
            return CompressedResult(
                original_messages=messages,
                compressed_messages=messages[-keep_last_n:] if len(messages) >= keep_last_n else messages,
                original_tokens=500,
                compressed_tokens=100,
            )

        with patch("tsave.core.overflow.compress", side_effect=fake_compress):
            result = create_with_overflow_recovery(
                mock_client,
                model="claude-sonnet-4-6",
                messages=messages,
                keep_last_n=4,
                max_retries=3,
                max_tokens=100,
            )

        assert result.recovery_successful is True
        assert len(keep_n_calls) == 2
        assert keep_n_calls[0] > keep_n_calls[1]

    def test_kwargs_forwarded_to_create(self, mock_client):
        create_with_overflow_recovery(
            mock_client,
            model="claude-sonnet-4-6",
            messages=self._make_messages(2),
            max_tokens=256,
            system="You are helpful.",
        )
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["max_tokens"] == 256
        assert call_kwargs["system"] == "You are helpful."

    def test_original_messages_list_not_mutated(self, mock_client):
        messages = self._make_messages(4)
        original_copy = list(messages)
        create_with_overflow_recovery(
            mock_client,
            model="claude-sonnet-4-6",
            messages=messages,
            max_tokens=100,
        )
        assert messages == original_copy

    def test_query_forwarded_to_compress(self, mock_client):
        messages = self._make_messages(10)
        mock_client.messages.create.side_effect = [_make_overflow_error(), FakeMessage()]

        with patch("tsave.core.overflow.compress") as mock_compress:
            mock_compress.return_value = _make_compressed(messages)
            create_with_overflow_recovery(
                mock_client,
                model="claude-sonnet-4-6",
                messages=messages,
                query="python async",
                max_tokens=100,
            )

        call_kwargs = mock_compress.call_args[1]
        assert call_kwargs["query"] == "python async"
