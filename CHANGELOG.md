# Changelog

## v0.3.2

- Improved replay reliability for shimmed live runs by preferring structured argv metadata during replay command recovery.
- Updated the OpenClaw live shim guidance to preserve quoted multi-word arguments safely.
- Clarified the current replay limitation:
  - replayed runs execute correctly
  - replayed runs do not yet automatically re-enter shim instrumentation for second-order anchors
- Refreshed public docs around replay milestones, builder shim expectations, and roadmap ordering.

## v0.2.0

- Promoted `hiveos_trace` as canonical runtime owner with compatibility shim for legacy imports.
- Added TEI CLI utilities:
  - `hive trace tei validate`
  - `hive trace tei ingest`
- Added framework integration guidance:
  - OpenClaw adoption path
  - OpenAI-compatible proxy path
- Added OpenClaw TEI smoke demo and example payload docs.
- Improved operator output:
  - clearer `trace flow show/steps` human formatting
  - richer `trace insight health` output with top failing commands

## v0.1.11

- Added `trace insight` macro layer (`explain`, `drift`, `health`)
- Canonicalized `trace ops` lifecycle namespace
- Improved flow readability and run liveness visibility
