from unittest.mock import MagicMock, patch

from token_saver.client import TokenSaverClient, UsageRecord
from token_saver.core.tokenizer import PRICING
from tests.conftest import FakeMessage, FakeUsage, FakeTokenCount


class TestUsageRecord:
    def test_costs_sonnet(self):
        r = UsageRecord(model="claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
        assert r.input_cost == 3.00
        assert r.output_cost == 15.00
        assert r.total_cost == 18.00

    def test_costs_haiku(self):
        r = UsageRecord(model="claude-haiku-4-5", input_tokens=500_000, output_tokens=500_000)
        assert r.input_cost == 0.50
        assert r.output_cost == 2.50
        assert r.total_cost == 3.00

    def test_unknown_model_default_rates(self):
        r = UsageRecord(model="future-model", input_tokens=1_000_000, output_tokens=1_000_000)
        assert r.input_cost == 3.00
        assert r.output_cost == 15.00


class TestTokenSaverClient:
    def _make_client(self) -> tuple[TokenSaverClient, MagicMock]:
        with patch("token_saver.client.anthropic.Anthropic") as MockAnthropic:
            mock_inner = MagicMock()
            MockAnthropic.return_value = mock_inner
            client = TokenSaverClient(api_key="fake")
            return client, mock_inner

    def test_create_tracks_usage(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.create.return_value = FakeMessage(
            usage=FakeUsage(input_tokens=100, output_tokens=50),
        )
        response = client.create(model="claude-sonnet-4-6", max_tokens=100, messages=[])
        assert len(client.history) == 1
        assert client.history[0].input_tokens == 100
        assert client.history[0].output_tokens == 50

    def test_total_cost_accumulates(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.create.return_value = FakeMessage(
            usage=FakeUsage(input_tokens=1_000_000, output_tokens=0),
        )
        client.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])
        client.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])
        assert client.total_cost == 6.00
        assert client.total_input_tokens == 2_000_000

    def test_total_output_tokens(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.create.return_value = FakeMessage(
            usage=FakeUsage(input_tokens=0, output_tokens=300),
        )
        client.create(model="claude-sonnet-4-6", max_tokens=1000, messages=[])
        assert client.total_output_tokens == 300

    def test_history_returns_copy(self):
        client, _ = self._make_client()
        h = client.history
        h.append("garbage")
        assert len(client.history) == 0

    def test_usage_summary_empty(self):
        client, _ = self._make_client()
        assert "No requests tracked" in client.usage_summary()

    def test_usage_summary_with_requests(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.create.return_value = FakeMessage(
            usage=FakeUsage(input_tokens=100, output_tokens=50),
        )
        client.create(model="claude-sonnet-4-6", max_tokens=100, messages=[])
        summary = client.usage_summary()
        assert "1 requests" in summary
        assert "Total input tokens" in summary

    def test_usage_summary_multiple_models(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.create.return_value = FakeMessage(
            usage=FakeUsage(input_tokens=100, output_tokens=50),
        )
        client.create(model="claude-sonnet-4-6", max_tokens=100, messages=[])
        client.create(model="claude-haiku-4-5", max_tokens=100, messages=[])
        summary = client.usage_summary()
        assert "Models used:" in summary

    def test_count_tokens_delegates(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.count_tokens.return_value = FakeTokenCount(input_tokens=42)
        result = client.count_tokens(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result.input_tokens == 42

    def test_monthly_projection_no_history(self):
        client, _ = self._make_client()
        proj = client.monthly_projection(requests_per_day=100)
        assert proj.cost_per_request == 0.0
        assert proj.monthly_cost == 0.0

    def test_monthly_projection_with_history(self):
        client, mock_inner = self._make_client()
        mock_inner.messages.create.return_value = FakeMessage(
            usage=FakeUsage(input_tokens=1_000_000, output_tokens=0),
        )
        client.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])
        proj = client.monthly_projection(requests_per_day=10)
        assert proj.cost_per_request == 3.00
        assert proj.daily_cost == 30.00

    def test_raw_exposes_inner_client(self):
        client, mock_inner = self._make_client()
        assert client.raw is mock_inner
