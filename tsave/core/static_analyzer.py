"""Static analyzer: scans Python source for token-wasting patterns before execution."""

from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    message: str
    estimated_waste_tokens: int
    fix: str

    def format(self) -> str:
        return (
            f"  {self.file}:{self.line}  [{self.rule}]\n"
            f"  {self.message}\n"
            f"  ~{self.estimated_waste_tokens:,} tokens wasted per call\n"
            f"  Fix:\n"
            + textwrap.indent(self.fix, "    ")
        )


@dataclass
class ScanReport:
    file: str
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None

    @property
    def total_estimated_waste(self) -> int:
        return sum(f.estimated_waste_tokens for f in self.findings)

    def format(self) -> str:
        if self.error is not None:
            return f"tsave: {self.file} -- could not analyze: {self.error}"
        if not self.findings:
            return f"tsave: {self.file} -- no issues found"
        lines = [f"tsave: {self.file} -- {len(self.findings)} issue(s)\n"]
        for f in self.findings:
            lines.append(f.format())
            lines.append("")
        lines.append(f"Total estimated waste: ~{self.total_estimated_waste:,} tokens/call")
        return "\n".join(lines)


_API_CALL_ATTRS = {
    "create", "stream", "count_tokens",
}

_EXPENSIVE_MODELS = {"claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6", "claude-fable-5"}


def _is_api_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute) and node.func.attr in _API_CALL_ATTRS:
        return True
    return False


def _get_string_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_keyword(call: ast.Call, name: str) -> ast.keyword | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, filename: str, source_lines: list[str]):
        self.filename = filename
        self.source_lines = source_lines
        self.findings: list[Finding] = []
        self._loop_stack: list[ast.AST] = []
        self._system_assignments: list[int] = []
        self._seen_models: list[tuple[int, str]] = []

    def _in_loop(self) -> bool:
        return len(self._loop_stack) > 0

    def visit_For(self, node: ast.For):
        self._loop_stack.append(node)
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_While(self, node: ast.While):
        self._loop_stack.append(node)
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_Call(self, node: ast.Call):
        if _is_api_call(node):
            self._check_api_in_loop(node)
            self._check_file_read_in_call(node)
            self._check_model_routing(node)
            self._check_no_caching(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and "system" in target.id.lower():
                self._system_assignments.append(node.lineno)
        self.generic_visit(node)

    def _check_api_in_loop(self, node: ast.Call):
        if not self._in_loop():
            return
        self.findings.append(Finding(
            file=self.filename,
            line=node.lineno,
            rule="api-in-loop",
            message="API call inside a loop — each iteration sends a full request",
            estimated_waste_tokens=5000,
            fix=textwrap.dedent("""\
                # Batch messages or collect results, then make one call
                results = []
                for item in items:
                    results.append(item)
                response = client.messages.create(
                    model="claude-haiku-4-5",
                    messages=[{"role": "user", "content": "\\n".join(results)}],
                )"""),
        ))

    def _check_file_read_in_call(self, node: ast.Call):
        subtree = ast.dump(node)
        if "read" not in subtree.lower() and "open" not in subtree.lower():
            return
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if child is node:
                continue
            if isinstance(child.func, ast.Attribute) and child.func.attr in ("read", "read_text"):
                self.findings.append(Finding(
                    file=self.filename,
                    line=node.lineno,
                    rule="full-file-per-call",
                    message="Entire file read and passed in every API call -- chunk or summarize first",
                    estimated_waste_tokens=10000,
                    fix=textwrap.dedent("""\
                        # Read once, chunk, send only relevant parts
                        content = Path("doc.txt").read_text()
                        chunks = [content[i:i+4000] for i in range(0, len(content), 4000)]
                        response = client.messages.create(
                            messages=[{"role": "user", "content": chunks[0]}],
                        )"""),
                ))
                return

    def _check_model_routing(self, node: ast.Call):
        model_kw = _get_keyword(node, "model")
        if model_kw is None:
            return
        model_val = _get_string_value(model_kw.value)
        if model_val is None:
            return
        self._seen_models.append((node.lineno, model_val))
        if model_val not in _EXPENSIVE_MODELS:
            return
        is_simple = True
        msg_kw = _get_keyword(node, "messages")
        if msg_kw and isinstance(msg_kw.value, ast.List) and len(msg_kw.value.elts) <= 2:
            tools_kw = _get_keyword(node, "tools")
            if tools_kw is None:
                is_simple = True
        if is_simple and model_val in _EXPENSIVE_MODELS:
            self.findings.append(Finding(
                file=self.filename,
                line=node.lineno,
                rule="no-model-routing",
                message=f"Using {model_val} for a simple call — Haiku may suffice",
                estimated_waste_tokens=0,
                fix=textwrap.dedent(f"""\
                    # Route by complexity
                    model = "claude-haiku-4-5"  # simple tasks
                    # model = "{model_val}"     # complex tasks only"""),
            ))

    def _check_no_caching(self, node: ast.Call):
        sys_kw = _get_keyword(node, "system")
        if sys_kw is None:
            return
        has_cache = False
        if isinstance(sys_kw.value, ast.List):
            for elt in sys_kw.value.elts:
                if isinstance(elt, ast.Dict):
                    for key in elt.keys:
                        if isinstance(key, ast.Constant) and key.value == "cache_control":
                            has_cache = True
        if isinstance(sys_kw.value, (ast.Constant, ast.JoinedStr)):
            pass

        if not has_cache and self._in_loop():
            self.findings.append(Finding(
                file=self.filename,
                line=node.lineno,
                rule="uncached-system-prompt",
                message="System prompt sent in loop without cache_control — reparsed every call",
                estimated_waste_tokens=2000,
                fix=textwrap.dedent("""\
                    system=[{
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }]"""),
            ))

    def finalize(self):
        if len(self._system_assignments) > 1:
            self.findings.append(Finding(
                file=self.filename,
                line=self._system_assignments[-1],
                rule="system-prompt-redefined",
                message=f"System prompt assigned {len(self._system_assignments)} times — define once and cache",
                estimated_waste_tokens=2000,
                fix=textwrap.dedent("""\
                    # Define once at module level with cache_control
                    SYSTEM = [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]"""),
            ))

        self._check_uncompressed_history()

    def _check_uncompressed_history(self):
        for i, line in enumerate(self.source_lines, 1):
            stripped = line.strip()
            if ".append(" in stripped and "messages" in stripped.lower():
                context_start = max(0, i - 5)
                context = "\n".join(self.source_lines[context_start:i + 5])
                if "compres" not in context.lower() and "summar" not in context.lower() and "compact" not in context.lower():
                    has_loop = any(
                        kw in context for kw in ("for ", "while ", "def chat", "def conversation")
                    )
                    if has_loop:
                        self.findings.append(Finding(
                            file=self.filename,
                            line=i,
                            rule="uncompressed-history",
                            message="Messages appended in a loop without compression — history grows unbounded",
                            estimated_waste_tokens=8000,
                            fix=textwrap.dedent("""\
                                # Compress history when it grows large
                                if len(messages) > 20:
                                    result = client.compress(model=model, messages=messages)
                                    messages = result.compressed_messages"""),
                        ))
                        return


def scan_source(source: str, filename: str = "<stdin>") -> ScanReport:
    # Strip a leading UTF-8 BOM so BOM-prefixed sources parse correctly.
    if source and ord(source[0]) == 0xFEFF:
        source = source[1:]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        # Surface the parse failure instead of silently reporting "no issues".
        where = f"line {e.lineno}: " if e.lineno else ""
        return ScanReport(file=filename, error=f"syntax error ({where}{e.msg})")

    lines = source.splitlines()
    visitor = _Visitor(filename, lines)
    visitor.visit(tree)
    visitor.finalize()
    return ScanReport(file=filename, findings=visitor.findings)


def scan_file(path: str | Path) -> ScanReport:
    p = Path(path)
    # utf-8-sig transparently strips a BOM if the file has one.
    source = p.read_text(encoding="utf-8-sig")
    return scan_source(source, str(p))
