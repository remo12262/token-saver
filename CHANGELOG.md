# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
Release convention (Keep a Changelog):
Keep an "Unreleased" section at the top. Add entries under it as changes land,
grouped by Added / Changed / Fixed / Removed. When cutting release X.Y.Z:
  1. Rename "## [Unreleased]" to "## [X.Y.Z] - YYYY-MM-DD".
  2. Add a fresh, empty "## [Unreleased]" section above it.
  3. Update the comparison links at the bottom.
-->

## [Unreleased]

## [0.1.3] - 2026-06-24

### Fixed
- The scanner no longer silently returns a clean result for files it cannot
  parse. Syntax errors are now surfaced as `could not analyze: syntax error (...)`.
- `scan_file` reads sources with `utf-8-sig`, so files saved with a UTF-8 BOM
  (common on Windows) are analyzed correctly instead of failing silently and
  reporting "no issues found".
- `tsave scan` exits with a non-zero status on unparseable files.

### Added
- Tests covering BOM handling and syntax-error reporting.

## [0.1.2] - 2026-06-24

### Changed
- Renamed the Python import package from `token_saver` to `tsave`, so the import
  name matches the PyPI distribution and the CLI
  (`from tsave import TokenSaverClient`). Public API is otherwise unchanged.

## [0.1.1] - 2026-06-24

### Added
- First release published to PyPI as [`tsave`](https://pypi.org/project/tsave/),
  via GitHub Actions Trusted Publishing.

### Changed
- Renamed the PyPI distribution from `token-saver` to `tsave`
  (`pip install tsave`).

[Unreleased]: https://github.com/remo12262/token-saver/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/remo12262/token-saver/releases/tag/v0.1.3
[0.1.2]: https://github.com/remo12262/token-saver/releases/tag/v0.1.2
[0.1.1]: https://github.com/remo12262/token-saver/releases/tag/v0.1.1