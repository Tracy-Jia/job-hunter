# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Modular package structure (`job_hunter/`) with separate modules for browser, config, scanner, applier, prefilter, sender, daily, scorer, and utils
- `shared.py` backward-compatibility re-export layer
- `CHANGELOG.md`

### Changed
- `boss_*.py` scripts are now thin CLI wrappers delegating to `job_hunter/` package
- Test file moved to `tests/` directory

## [0.1.0] — Initial Release

### Added
- Dual-mode job scanning (`fast` cards + `deep` JD reading)
- Rule-based prefiltering with 7-layer configurable filters
- AI-assisted greeting generation framework (5-segment, role-aware)
- Automated application sending via CDP (Chrome DevTools Protocol)
- Daily summary with reply detection and follow-up suggestions
- Multi-keyword batch scanning with de-duplication
- Salary font-encryption bypass
- Cross-run sent-link deduplication
- Experimental adapters for additional recruitment platforms
