# Changelog

All notable project changes are documented here. Version numbers below describe the combined BruteForcer upgrade path from the original public plugin to the current GitHub-ready release.

## [3.3.0] - Unreleased

### Added
- Mutator Lab page at `/mutator` with strategy, cap, candidate-family mix, seed counts, preview budget, and recent build history.
- Ordered mutator strategies: `smart`, `compatibility`, and `thorough`.
- Optional token-pair generation, numeric suffix handling, bounded year window, custom local seed words, custom prefixes, and custom suffixes.
- Candidate-length controls and per-build category accounting.
- Expanded dashboard mutator panel and persisted mutator-build analytics.

### Changed
- Updated release metadata to `3.3.0`.
- The recommended configuration keeps the normal Pi-oriented candidate cap at `800` and puts lower-noise SSID-specific forms first.
- Explicit `main.plugins.Bruteforcer.*` configuration values take precedence over stale or framework-supplied defaults.

## [3.2.3]

### Fixed
- Prevented raw terminal redraw values from overwriting a measured throughput source once a tested-key/time measurement exists.
- Added compatibility parsing for `bruteforce`, `bruteforcer`, and `Bruteforcer` configuration blocks, with the current `Bruteforcer` spelling winning last.
- Added a fallback TOML reader so explicit configuration continues to work when the optional Python `toml` module is unavailable.

## [3.2.2]

### Added
- Measured WPS/candidate-rate telemetry based on tested keys divided by elapsed time.
- Throughput source and confidence fields, including a clear distinction between measured rates and unverified Aircrack terminal text.
- Completed-wordlist WPS calculation and compact dashboard formatting.

### Changed
- Dashboard rate cards and sparklines now prefer measured data instead of trusting a terminal `k/s` string blindly.

## [3.2.1]

### Added
- Optional fan telemetry integration via `/var/tmp/pwnagotchi/fan_status.json`.
- CPU temperature in Fahrenheit, fan PWM percentage, fan RPM, stale-data detection, and system-health display in the Command Center.
- Optional companion `fan_control.py` telemetry writer.

## [3.2.0]

### Added
- Capture Intelligence page and Reports page.
- Capture quality grades, reasons, duplicate grouping, best-capture selection, and queue-priority explanations.
- Optional adaptive queue ordering and optional duplicate auto-hold behavior.
- Resource-history tracking for temperature, RAM, swap, load, and WPS.
- Crash-aware active-job journal and recovery visibility.
- Daily/weekly reporting, wordlist-lab summaries, event timeline, and optional compact e-paper status mode.

## [3.1.3]

### Changed
- Compact WPS formatting such as `249.3K` and `1.3M` for faster dashboard reading.

## [3.1.2]

### Added
- Aircrack status parsing for key-test counters and printed throughput units.
- Live WPS card, WPS sparkline feed, and improved words-processed tracking.

## [3.1.1]

### Fixed
- Replaced dashboard characters that could render incorrectly after terminal paste or encoding changes.
- Standardized dashboard temperature display in Fahrenheit.
- Improved runtime configuration discovery for the BruteForcer plugin block.

## [3.1.0]

### Added
- Offline-friendly SkyGotchi Command Center layout with embedded styling.
- Capture Library with search, filters, statuses, and requeue controls.
- Clear current-job panel, queue controls, system status, activity timeline, and improved responsive layout.

## [3.0.0]

### Added
- Resource governor framework for temperature, memory, swap, and load awareness.
- Capture preflight handling, queue actions, export endpoints, wordlist analytics, and persistent operational state.
- Per-SSID and per-wordlist history, retry tracking, job timeline, and enhanced dashboard metrics.

## Legacy baseline (pre-3.0)

The original public plugin provided the core workflow: a monitored capture directory, sequential Aircrack jobs, wordlist iteration, retry behavior, progress persistence, Pwnagotchi UI status, and a Flask dashboard on port `5000`.
