from token_saver.core.tokenizer import (
    PRICING,
    TokenCount,
    CostEstimate,
    MonthlyProjection,
    count_tokens,
    estimate_cost,
    monthly_projection,
)
from tests.conftest import FakeTokenCount


class TestTokenCount:
    def test_input_cost_known_model(self):
        tc = TokenCount(input_tokens=1_000_000, model="claude-sonnet-4-6")
        assert tc.input_cost == 3.00

    def test_input_cost_opus(self):
        tc = TokenCount(input_tokens=1_000_000, model="claude-opus-4-8")
        assert tc.input_cost == 5.00

    def test_input_cost_haiku(self):
        tc = TokenCount(input_tokens=1_000_000, model="claude-haiku-4-5")
        assert tc.input_cost == 1.00

    def test_input_cost_unknown_model_uses_default(self):
        tc = TokenCount(input_tokens=1_000_000, model="unknown-model")
        assert tc.input_cost == 3.00

    def test_format_output(self):
        tc = TokenCount(input_tokens=1500, model="claude-sonnet-4-6")
        text = tc.format()
        assert "1,500 input tokens" in text
        assert "$" in text


class TestCostEstimate:
    def test_total_cost(self):
        ce = CostEstimate(
            input_tokens=1_000_000,
            estimated_output_tokens=1_000_000,
            model="claude-sonnet-4-6",
        )
        assert ce.input_cost == 3.00
        assert ce.output_cost == 15.00
        assert ce.total_cost == 18.00

    def test_format_contains_all_lines(self):
        ce = CostEstimate(input_tokens=500, estimated_output_tokens=200, model="claude-haiku-4-5")
        text = ce.format()
        assert "Input:" in text
        assert "Output:" in text
        assert "Total:" in text


class TestMonthlyProjection:
    def test_daily_cost(self):
        mp = MonthlyProjection(cost_per_request=0.01, requests_per_day=100)
        assert mp.daily_cost == 1.00

    def test_monthly_cost_default_30_days(self):
        mp = MonthlyProjection(cost_per_request=0.01, requests_per_day=100)
        assert mp.monthly_cost == 30.00

    def test_custom_days(self):
        mp = MonthlyProjection(cost_per_request=0.01, requests_per_day=100, days=7)
        assert mp.monthly_cost == 7.00

    def test_format(self):
        mp = MonthlyProjection(cost_per_request=0.05, requests_per_day=50)
        text = mp.format()
        assert "Per request" in text
        assert "Daily" in text
        assert "Monthly" in text


class TestCountTokens:
    def test_calls_api_and_returns_token_count(self, mock_client):
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=42)
        result = count_tokens(
            mock_client,
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result.input_tokens == 42
        assert result.model == "claude-sonnet-4-6"
        mock_client.messages.count_tokens.assert_called_once()

    def test_passes_system_when_provided(self, mock_client):
        count_tokens(
            mock_client,
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
            system="You are helpful.",
        )
        call_kwargs = mock_client.messages.count_tokens.call_args[1]
        assert call_kwargs["system"] == "You are helpful."

    def test_omits_system_when_none(self, mock_client):
        count_tokens(
            mock_client,
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
        )
        call_kwargs = mock_client.messages.count_tokens.call_args[1]
        assert "system" not in call_kwargs

    def test_passes_tools_when_provided(self, mock_client):
        tools = [{"name": "test", "description": "d", "input_schema": {"type": "object"}}]
        count_tokens(
            mock_client,
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
        )
        call_kwargs = mock_client.messages.count_tokens.call_args[1]
        assert call_kwargs["tools"] == tools


class TestEstimateCost:
    def test_returns_cost_estimate(self, mock_client):
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=500)
        result = estimate_cost(
            mock_client,
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hi"}],
            estimated_output_tokens=200,
        )
        assert result.input_tokens == 500
        assert result.estimated_output_tokens == 200
        assert result.model == "claude-sonnet-4-6"


class TestMonthlyProjectionFunc:
    def test_returns_projection(self):
        result = monthly_projection(0.05, 100, 30)
        assert result.cost_per_request == 0.05
        assert result.requests_per_day == 100
        assert result.days == 30


class TestPricing:
    def test_all_models_have_two_rates(self):
        for model, rates in PRICING.items():
            assert len(rates) == 2
            assert rates[0] > 0
            assert rates[1] > 0

    def test_output_rate_higher_than_input(self):
        for model, (inp, out) in PRICING.items():
            assert out > inp, f"{model}: output rate should exceed input rate"
