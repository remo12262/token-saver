"""Pre-send prescriptive analysis with optimization suggestions."""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from .tokenizer import PRICING, count_tokens


@dataclass
class Suggestion:
    category: str
    message: str
    estimated_saving_pct: float = 0.0


@dataclass
class AnalysisReport:
    model: str
    input_tokens: int
    suggestions: list[Suggestion] = field(default_factory=list)
    alternative_models: list[dict] = field(default_factory=list)

    @property
    def input_cost(self) -> float:
        rate_in, _ = PRICING.get(self.model, (3.00, 15.00))
        return self.input_tokens * rate_in / 1_000_000

    @property
    def potential_savings_pct(self) -> float:
        if not self.suggestions:
            return 0.0
        return max(s.estimated_saving_pct for s in self.suggestions)

    def format(self) -> str:
        lines = [
            f"=== Analysis Report ===",
            f"Model: {self.model}",
            f"Input tokens: {self.input_tokens:,}",
            f"Estimated input cost: ${self.input_cost:.4f}",
        ]
        if self.suggestions:
            lines.append(f"\nSuggestions ({len(self.suggestions)}):")
            for i, s in enumerate(self.suggestions, 1):
                saving = f" (~{s.estimated_saving_pct:.0f}% saving)" if s.estimated_saving_pct else ""
                lines.append(f"  {i}. [{s.category}] {s.message}{saving}")
        else:
            lines.append("\nNo optimization suggestions -- looks good!")

        if self.alternative_models:
            lines.append("\nAlternative models:")
            for alt in self.alternative_models:
                lines.append(f"  - {alt['model']}: ${alt['cost']:.4f} (save ${alt['saving']:.4f})")

        return "\n".join(lines)


def _check_message_length(messages: list[dict]) -> list[Suggestion]:
    suggestions = []
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > 50_000:
            suggestions.append(Suggestion(
                category="large-message",
                message=f"Message {i} has {len(content):,} chars — consider compressing or chunking",
                estimated_saving_pct=30.0,
            ))
    return suggestions


def _check_system_prompt(system: str | list[dict] | None) -> list[Suggestion]:
    suggestions = []
    if system is None:
        return suggestions
    text = system if isinstance(system, str) else " ".join(
        b.get("text", "") for b in system if isinstance(b, dict)
    )
    if len(text) > 10_000:
        suggestions.append(Suggestion(
            category="large-system-prompt",
            message=f"System prompt is {len(text):,} chars — consider trimming or using caching",
            estimated_saving_pct=20.0,
        ))
    return suggestions


def _check_redundant_turns(messages: list[dict]) -> list[Suggestion]:
    suggestions = []
    if len(messages) > 20:
        suggestions.append(Suggestion(
            category="long-conversation",
            message=f"Conversation has {len(messages)} turns — consider summarizing older turns",
            estimated_saving_pct=40.0,
        ))
    return suggestions


def _check_caching(system: str | list[dict] | None, tools: list[dict] | None) -> list[Suggestion]:
    suggestions = []
    has_cache_control = False
    if isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and "cache_control" in block:
                has_cache_control = True
                break
    if tools:
        for tool in tools:
            if isinstance(tool, dict) and "cache_control" in tool:
                has_cache_control = True
                break

    sys_text = ""
    if isinstance(system, str):
        sys_text = system
    elif isinstance(system, list):
        sys_text = " ".join(b.get("text", "") for b in system if isinstance(b, dict))

    if not has_cache_control and (len(sys_text) > 2048 or (tools and len(tools) > 3)):
        suggestions.append(Suggestion(
            category="no-caching",
            message="Large system prompt or many tools without cache_control — enable prompt caching for 90% input cost reduction on cache hits",
            estimated_saving_pct=50.0,
        ))
    return suggestions


def _find_cheaper_models(model: str, input_tokens: int) -> list[dict]:
    current_rate, _ = PRICING.get(model, (3.00, 15.00))
    current_cost = input_tokens * current_rate / 1_000_000
    alternatives = []
    for alt_model, (alt_rate, _) in sorted(PRICING.items(), key=lambda x: x[1][0]):
        if alt_rate < current_rate and alt_model != model:
            alt_cost = input_tokens * alt_rate / 1_000_000
            alternatives.append({
                "model": alt_model,
                "cost": alt_cost,
                "saving": current_cost - alt_cost,
            })
    return alternatives


def analyze(
    client: anthropic.Anthropic,
    *,
    model: str,
    messages: list[dict],
    system: str | list[dict] | None = None,
    tools: list[dict] | None = None,
) -> AnalysisReport:
    tc = count_tokens(client, model=model, messages=messages, system=system, tools=tools)

    suggestions: list[Suggestion] = []
    suggestions.extend(_check_message_length(messages))
    suggestions.extend(_check_system_prompt(system))
    suggestions.extend(_check_redundant_turns(messages))
    suggestions.extend(_check_caching(system, tools))

    alternatives = _find_cheaper_models(model, tc.input_tokens)

    return AnalysisReport(
        model=model,
        input_tokens=tc.input_tokens,
        suggestions=suggestions,
        alternative_models=alternatives,
    )
