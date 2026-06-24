from tsave.core.analyzer import (
    AnalysisReport,
    Suggestion,
    _check_message_length,
    _check_system_prompt,
    _check_redundant_turns,
    _check_caching,
    _find_cheaper_models,
    analyze,
)
from tests.conftest import FakeTokenCount


class TestCheckMessageLength:
    def test_no_suggestion_for_short_messages(self):
        msgs = [{"role": "user", "content": "short message"}]
        assert _check_message_length(msgs) == []

    def test_flags_large_message(self):
        msgs = [{"role": "user", "content": "x" * 60_000}]
        result = _check_message_length(msgs)
        assert len(result) == 1
        assert result[0].category == "large-message"

    def test_skips_non_string_content(self):
        msgs = [{"role": "user", "content": [{"type": "text", "text": "x" * 60_000}]}]
        assert _check_message_length(msgs) == []


class TestCheckSystemPrompt:
    def test_no_suggestion_for_none(self):
        assert _check_system_prompt(None) == []

    def test_no_suggestion_for_short_prompt(self):
        assert _check_system_prompt("Be helpful.") == []

    def test_flags_large_string_prompt(self):
        result = _check_system_prompt("x" * 15_000)
        assert len(result) == 1
        assert result[0].category == "large-system-prompt"

    def test_flags_large_block_prompt(self):
        result = _check_system_prompt([{"type": "text", "text": "x" * 15_000}])
        assert len(result) == 1
        assert result[0].category == "large-system-prompt"


class TestCheckRedundantTurns:
    def test_no_suggestion_for_short_conversation(self):
        msgs = [{"role": "user", "content": "hi"}] * 10
        assert _check_redundant_turns(msgs) == []

    def test_flags_long_conversation(self):
        msgs = [{"role": "user", "content": "hi"}] * 25
        result = _check_redundant_turns(msgs)
        assert len(result) == 1
        assert result[0].category == "long-conversation"


class TestCheckCaching:
    def test_no_suggestion_when_cache_control_present(self):
        system = [{"type": "text", "text": "x" * 5000, "cache_control": {"type": "ephemeral"}}]
        assert _check_caching(system, None) == []

    def test_flags_large_system_without_caching(self):
        system = "x" * 5000
        result = _check_caching(system, None)
        assert len(result) == 1
        assert result[0].category == "no-caching"

    def test_flags_many_tools_without_caching(self):
        tools = [{"name": f"t{i}"} for i in range(5)]
        result = _check_caching(None, tools)
        assert len(result) == 1
        assert result[0].category == "no-caching"

    def test_no_suggestion_small_prompt_few_tools(self):
        assert _check_caching("short", [{"name": "t1"}]) == []

    def test_cache_control_on_tool_suppresses(self):
        tools = [{"name": f"t{i}"} for i in range(5)]
        tools[0]["cache_control"] = {"type": "ephemeral"}
        assert _check_caching(None, tools) == []


class TestFindCheaperModels:
    def test_finds_alternatives_for_opus(self):
        alts = _find_cheaper_models("claude-opus-4-8", 1_000_000)
        model_names = [a["model"] for a in alts]
        assert "claude-haiku-4-5" in model_names
        assert "claude-sonnet-4-6" in model_names

    def test_no_alternatives_for_cheapest(self):
        alts = _find_cheaper_models("claude-haiku-4-5", 1_000_000)
        assert alts == []

    def test_savings_are_positive(self):
        alts = _find_cheaper_models("claude-opus-4-8", 1_000_000)
        for alt in alts:
            assert alt["saving"] > 0


class TestAnalysisReport:
    def test_potential_savings_empty(self):
        report = AnalysisReport(model="claude-sonnet-4-6", input_tokens=100)
        assert report.potential_savings_pct == 0.0

    def test_potential_savings_returns_max(self):
        report = AnalysisReport(
            model="claude-sonnet-4-6",
            input_tokens=100,
            suggestions=[
                Suggestion("a", "msg", 10.0),
                Suggestion("b", "msg", 30.0),
            ],
        )
        assert report.potential_savings_pct == 30.0

    def test_format_no_suggestions(self):
        report = AnalysisReport(model="claude-sonnet-4-6", input_tokens=100)
        text = report.format()
        assert "looks good!" in text

    def test_format_with_suggestions(self):
        report = AnalysisReport(
            model="claude-sonnet-4-6",
            input_tokens=100,
            suggestions=[Suggestion("test", "do something", 25.0)],
        )
        text = report.format()
        assert "[test]" in text
        assert "25%" in text


class TestAnalyze:
    def test_returns_report(self, mock_client):
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=50)
        report = analyze(
            mock_client,
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "hello"}],
        )
        assert isinstance(report, AnalysisReport)
        assert report.input_tokens == 50
        assert report.model == "claude-sonnet-4-6"

    def test_detects_large_message(self, mock_client):
        mock_client.messages.count_tokens.return_value = FakeTokenCount(input_tokens=50000)
        report = analyze(
            mock_client,
            model="claude-opus-4-8",
            messages=[{"role": "user", "content": "x" * 60_000}],
        )
        categories = [s.category for s in report.suggestions]
        assert "large-message" in categories
