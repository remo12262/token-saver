"""TokenSaverClient — drop-in replacement for anthropic.Anthropic with built-in cost tracking."""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from .core.tokenizer import (
    PRICING,
    CostEstimate,
    TokenCount,
    count_tokens,
    estimate_cost,
    monthly_projection,
)
from .core.analyzer import AnalysisReport, analyze
from .core.compressor import CompressedResult, compress


@dataclass
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def input_cost(self) -> float:
        rate_in, _ = PRICING.get(self.model, (3.00, 15.00))
        return self.input_tokens * rate_in / 1_000_000

    @property
    def output_cost(self) -> float:
        _, rate_out = PRICING.get(self.model, (3.00, 15.00))
        return self.output_tokens * rate_out / 1_000_000

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


class TokenSaverClient:
    """Wraps anthropic.Anthropic with token counting, cost tracking, analysis, and compression."""

    def __init__(self, **kwargs):
        self._client = anthropic.Anthropic(**kwargs)
        self._history: list[UsageRecord] = []

    @property
    def raw(self) -> anthropic.Anthropic:
        return self._client

    @property
    def history(self) -> list[UsageRecord]:
        return list(self._history)

    @property
    def total_cost(self) -> float:
        return sum(r.total_cost for r in self._history)

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self._history)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self._history)

    def create(self, **kwargs) -> anthropic.types.Message:
        response = self._client.messages.create(**kwargs)
        usage = response.usage
        record = UsageRecord(
            model=kwargs.get("model", response.model),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )
        self._history.append(record)
        return response

    def count_tokens(
        self,
        *,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None = None,
        tools: list[dict] | None = None,
    ) -> TokenCount:
        return count_tokens(self._client, model=model, messages=messages, system=system, tools=tools)

    def estimate_cost(
        self,
        *,
        model: str,
        messages: list[dict],
        estimated_output_tokens: int = 1000,
        system: str | list[dict] | None = None,
        tools: list[dict] | None = None,
    ) -> CostEstimate:
        return estimate_cost(
            self._client,
            model=model,
            messages=messages,
            estimated_output_tokens=estimated_output_tokens,
            system=system,
            tools=tools,
        )

    def analyze(
        self,
        *,
        model: str,
        messages: list[dict],
        system: str | list[dict] | None = None,
        tools: list[dict] | None = None,
    ) -> AnalysisReport:
        return analyze(self._client, model=model, messages=messages, system=system, tools=tools)

    def compress(
        self,
        *,
        model: str,
        messages: list[dict],
        target_reduction: float = 0.5,
        query: str | None = None,
        keep_last_n: int = 4,
    ) -> CompressedResult:
        return compress(
            self._client,
            model=model,
            messages=messages,
            target_reduction=target_reduction,
            query=query,
            keep_last_n=keep_last_n,
        )

    def monthly_projection(self, requests_per_day: int, days: int = 30):
        if not self._history:
            return monthly_projection(0.0, requests_per_day, days)
        avg_cost = self.total_cost / len(self._history)
        return monthly_projection(avg_cost, requests_per_day, days)

    def usage_summary(self) -> str:
        n = len(self._history)
        if n == 0:
            return "No requests tracked yet."
        lines = [
            f"=== Usage Summary ({n} requests) ===",
            f"Total input tokens:  {self.total_input_tokens:,}",
            f"Total output tokens: {self.total_output_tokens:,}",
            f"Total cost:          ${self.total_cost:.4f}",
            f"Avg cost/request:    ${self.total_cost / n:.4f}",
        ]
        models_used = set(r.model for r in self._history)
        if len(models_used) > 1:
            lines.append(f"Models used: {', '.join(sorted(models_used))}")
        return "\n".join(lines)
