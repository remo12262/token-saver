"""CLI entry point: tsave scan <file.py>"""

import sys
from pathlib import Path

from .core.static_analyzer import scan_file


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "scan":
        print("Usage: tsave scan <file.py> [file2.py ...]")
        sys.exit(1)

    files = sys.argv[2:]
    total_findings = 0

    for f in files:
        p = Path(f)
        if not p.exists():
            print(f"tsave: {f} -- file not found", file=sys.stderr)
            continue
        report = scan_file(p)
        print(report.format())
        total_findings += len(report.findings)
        if len(files) > 1:
            print()

    sys.exit(1 if total_findings > 0 else 0)


if __name__ == "__main__":
    main()
