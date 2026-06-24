import textwrap

from tsave.core.static_analyzer import scan_source, Finding, ScanReport


def _scan(code: str) -> ScanReport:
    return scan_source(textwrap.dedent(code), "test.py")


def _rules(report: ScanReport) -> list[str]:
    return [f.rule for f in report.findings]


class TestApiInLoop:
    def test_detects_create_in_for(self):
        report = _scan("""\
            for item in items:
                client.messages.create(model="claude-sonnet-4-6", messages=[])
        """)
        assert "api-in-loop" in _rules(report)

    def test_detects_create_in_while(self):
        report = _scan("""\
            while True:
                client.messages.create(model="claude-sonnet-4-6", messages=[])
        """)
        assert "api-in-loop" in _rules(report)

    def test_no_false_positive_outside_loop(self):
        report = _scan("""\
            client.messages.create(model="claude-sonnet-4-6", messages=[])
        """)
        assert "api-in-loop" not in _rules(report)


class TestFullFilePerCall:
    def test_detects_open_read_in_kwarg(self):
        report = _scan("""\
            client.messages.create(
                model="claude-sonnet-4-6",
                messages=[{"role": "user", "content": open("f.txt").read()}],
            )
        """)
        assert "full-file-per-call" in _rules(report)

    def test_no_false_positive_without_read(self):
        report = _scan("""\
            client.messages.create(model="claude-sonnet-4-6", messages=[{"role": "user", "content": "hi"}])
        """)
        assert "full-file-per-call" not in _rules(report)


class TestNoModelRouting:
    def test_detects_opus_for_simple_call(self):
        report = _scan("""\
            client.messages.create(model="claude-opus-4-8", messages=[{"role": "user", "content": "hi"}])
        """)
        assert "no-model-routing" in _rules(report)

    def test_no_flag_for_haiku(self):
        report = _scan("""\
            client.messages.create(model="claude-haiku-4-5", messages=[{"role": "user", "content": "hi"}])
        """)
        assert "no-model-routing" not in _rules(report)


class TestSystemPromptRedefined:
    def test_detects_multiple_assignments(self):
        report = _scan("""\
            system_prompt = "v1"
            system_prompt = "v2"
            system_prompt = "v3"
        """)
        assert "system-prompt-redefined" in _rules(report)

    def test_no_flag_single_assignment(self):
        report = _scan("""\
            system_prompt = "only once"
        """)
        assert "system-prompt-redefined" not in _rules(report)


class TestUncachedSystemPrompt:
    def test_detects_system_in_loop_no_cache(self):
        report = _scan("""\
            for item in items:
                client.messages.create(
                    model="claude-sonnet-4-6",
                    system="You are helpful.",
                    messages=[],
                )
        """)
        assert "uncached-system-prompt" in _rules(report)


class TestUncompressedHistory:
    def test_detects_append_in_loop(self):
        report = _scan("""\
            for turn in range(10):
                messages.append({"role": "user", "content": turn})
                response = client.messages.create(model="claude-sonnet-4-6", messages=messages)
        """)
        assert "uncompressed-history" in _rules(report)

    def test_no_flag_with_compression(self):
        report = _scan("""\
            for turn in range(10):
                messages.append({"role": "user", "content": turn})
                if len(messages) > 20:
                    compressed = compress(messages)
        """)
        assert "uncompressed-history" not in _rules(report)


class TestScanReport:
    def test_format_clean(self):
        report = ScanReport(file="clean.py")
        assert "no issues" in report.format()

    def test_format_with_findings(self):
        report = ScanReport(file="bad.py", findings=[
            Finding("bad.py", 10, "api-in-loop", "msg", 5000, "fix code"),
        ])
        text = report.format()
        assert "1 issue" in text
        assert "5,000" in text

    def test_total_waste(self):
        report = ScanReport(file="x.py", findings=[
            Finding("x.py", 1, "a", "m", 1000, "f"),
            Finding("x.py", 2, "b", "m", 2000, "f"),
        ])
        assert report.total_estimated_waste == 3000
