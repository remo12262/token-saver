"""Token counting, cost estimation, and monthly projection using the Anthropic API."""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5":      (10.00, 50.00),
    "claude-mythos-5":     (10.00, 50.00),
    "claude-opus-4-8":     (5.00, 25.00),
    "claude-opus-4-7":     (5.00, 25.00),
    "claude-opus-4-6":     (5.00, 25.00),
    "claude-sonnet-4-6":   (3.00, 15.00),
    "claude-haiku-4-5":    (1.00, 5.00),
}

CACHE_READ_DISCOUNT = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


@dataclass
class TokenCount:
    input_tokens: int
    model: str

    @property
    def input_cost(self) -> float:
        rate_in, _ = PRICING.get(self.model, (3.00, 15.00))
        return self.input_tokens * rate_in / 1_000_000

    def format(self) -> str:
        return f"{self.input_tokens:,} input tokens | est. ${self.input_cost:.4f}"


@dataclass
class CostEstimate:
    input_tokens: int
    estimated_output_tokens: int
    model: str

    @property
    def input_cost(self) -> float:
        rate_in, _ = PRICING.get(self.model, (3.00, 15.00))
        return self.input_tokens * rate_in / 1_000_000

    @property
    def output_cost(self) -> float:
        _, rate_out = PRICING.get(self.model, (3.00, 15.00))
        return self.estimated_output_tokens * rate_out / 1_000_000

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost

    def format(self) -> str:
        return (
            f"Input:  {self.input_tokens:>10,} tokens  ${self.input_cost:.4f}\n"
            f"Output: {self.estimated_output_tokens:>10,} tokens  ${self.output_cost:.4f}  (est.)\n"
            f"Total:  {'':>10}          ${self.total_cost:.4f}"
        )


@dataclass
class MonthlyProjection:
    cost_per_request: float
    requests_per_day: int
    days: int = 30

    @property
    def daily_cost(self) -> float:
        return self.cost_per_request * self.requests_per_day

    @property
    def monthly_cost(self) -> float:
        return self.daily_cost * self.days

    def format(self) -> str:
        return (
            f"Per request: ${self.cost_per_request:.4f}\n"
            f"Daily ({self.requests_per_day} req/day): ${self.daily_cost:.2f}\n"
            f"Monthly ({self.days} days): ${self.monthly_cost:.2f}"
        )


def count_tokens(
    client: anthropic.Anthropic,
    *,
    model: str,
    messages: list[dict],
    system: str | list[dict] | None = None,
    tools: list[dict] | None = None,
) -> TokenCount:
    kwargs: dict = {"model": model, "messages": messages}
    if system is not None:
        kwargs["system"] = system
    if tools is not None:
        kwargs["tools"] = tools
    resp = client.messages.count_tokens(**kwargs)
    return TokenCount(input_tokens=resp.input_tokens, model=model)


def estimate_cost(
    client: anthropic.Anthropic,
    *,
    model: str,
    messages: list[dict],
    estimated_output_tokens: int = 1000,
    system: str | list[dict] | None = None,
    tools: list[dict] | None = None,
) -> CostEstimate:
    tc = count_tokens(client, model=model, messages=messages, system=system, tools=tools)
    return CostEstimate(
        input_tokens=tc.input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        model=model,
    )


def monthly_projection(
    cost_per_request: float,
    requests_per_day: int,
    days: int = 30,
) -> MonthlyProjection:
    return MonthlyProjection(
        cost_per_request=cost_per_request,
        requests_per_day=requests_per_day,
        days=days,
    )
