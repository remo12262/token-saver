from unittest.mock import MagicMock

from token_saver.core.compressor import (
    CompressedResult,
    _score_message_relevance,
    compress,
)
from tests.conftest import FakeTokenCount, FakeMessage, FakeTextBlock


class TestCompressedResult:
    def test_reduction_pct_positive(self):
        cr = CompressedResult(
            original_messages=[],
            compressed_messages=[],
            original_tokens=1000,
            compressed_tokens=400,
        )
        assert cr.reduction_pct == 60.0

    def test_reduction_pct_zero_original(self):
        cr = CompressedResult(
            original_messages=[],
            compressed_messages=[],
            original_tokens=0,
            compressed_tokens=0,
        )
        assert cr.reduction_pct == 0.0

    def test_format_output(self):
        cr = CompressedResult(
            original_messages=[{"role": "user", "content": "a"}] * 10,
            compressed_messages=[{"role": "user", "content": "b"}] * 3,
            original_tokens=500,
            compressed_tokens=200,
        )
        text = cr.format()
        assert "10 messages" in text
        assert "3 messages" in text
        assert "60.0%" in text


class TestScoreMessageRelevance:
    def test_system_message_gets_max_score(self):
        msg = {"role": "system", "content": "Be helpful."}
        assert _score_message_relevance(msg, None) == 1.0

    def test_user_message_base_score(self):
        msg = {"role": "user", "content": "hello world"}
        score = _score_message_relevance(msg, None)
        assert 0.4 <= score <= 0.6

    def test_assistant_message_slightly_higher(self):
        user_score = _score_message_relevance({"role": "user", "content": "x"}, None)
        asst_score = _score_message_relevance({"role": "assistant", "content": "x"}, None)
        assert asst_score > user_score

    def test_query_overlap_boosts_score(self):
        msg = {"role": "user", "content": "python decorators pattern"}
        score_no_query = _score_message_relevance(msg, None)
        score_with_query = _score_message_relevance(msg, "python decorators")
        assert score_with_query > score_no_query

    def test_tool_use_boosts_score(self):
        msg_plain = {"role": "user", "content": "hello"}
        msg_tool = {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "x", "content": "result"},
        ]}
        score_plain = _score_message_relevance(msg_plain, None)
        score_tool = _score_message_relevance(msg_tool, None)
        assert score_tool > score_plain

    def test_non_string_content_gets_default(self):
        msg = {"role": "user", "content": 12345}
        assert _score_message_relevance(msg, None) == 1.0


class TestCompress:
    def _make_conversation(self, n_turns: int) -> list[dict]:
        msgs = []
        for i in range(n_turns):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append({"role": role, "content": f"Message number {i} with some content."})
        return msgs

    def test_short_conversation_unchanged(self, mock_client):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=20)
        result = compress(mock_client, model="claude-sonnet-4-6", messages=msgs, keep_last_n=4)
        assert result.compressed_messages == msgs
        assert result.reduction_pct == 0.0

    def test_long_conversation_produces_fewer_messages(self, mock_client):
        msgs = self._make_conversation(20)

        call_count = [0]
        def fake_count_tokens(**kwargs):
            call_count[0] += 1
            n_msgs = len(kwargs.get("messages", []))
            return FakeTokenCount(input_tokens=n_msgs * 50)

        mock_client.messages.count_tokens.side_effect = fake_count_tokens
        mock_client.messages.create.return_value = FakeMessage(
            content=[FakeTextBlock(text="Summary of earlier conversation.")]
        )

        result = compress(
            mock_client,
            model="claude-sonnet-4-6",
            messages=msgs,
            keep_last_n=4,
        )
        assert len(result.compressed_messages) < len(msgs)

    def test_protected_messages_preserved(self, mock_client):
        msgs = self._make_conversation(12)
        last_4 = msgs[-4:]

        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=100)
        mock_client.messages.create.return_value = FakeMessage(
            content=[FakeTextBlock(text="Summary.")]
        )

        result = compress(
            mock_client,
            model="claude-sonnet-4-6",
            messages=msgs,
            keep_last_n=4,
        )
        for protected_msg in last_4:
            found = any(
                protected_msg["content"] in m.get("content", "")
                for m in result.compressed_messages
            )
            assert found, f"Protected message not found: {protected_msg['content']}"

    def test_first_message_is_user_role(self, mock_client):
        msgs = self._make_conversation(10)
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=100)
        mock_client.messages.create.return_value = FakeMessage(
            content=[FakeTextBlock(text="Summary.")]
        )

        result = compress(
            mock_client,
            model="claude-sonnet-4-6",
            messages=msgs,
            keep_last_n=4,
        )
        assert result.compressed_messages[0]["role"] == "user"

    def test_no_consecutive_same_role(self, mock_client):
        msgs = self._make_conversation(10)
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=100)
        mock_client.messages.create.return_value = FakeMessage(
            content=[FakeTextBlock(text="Summary.")]
        )

        result = compress(
            mock_client,
            model="claude-sonnet-4-6",
            messages=msgs,
            keep_last_n=4,
        )
        for i in range(1, len(result.compressed_messages)):
            prev = result.compressed_messages[i - 1]["role"]
            curr = result.compressed_messages[i]["role"]
            if prev in ("user", "assistant") and curr in ("user", "assistant"):
                assert prev != curr, f"Consecutive {prev} messages at index {i-1},{i}"
