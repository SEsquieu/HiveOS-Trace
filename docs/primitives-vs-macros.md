# Primitives vs Macros

HiveOS Trace exposes two analysis layers plus ops controls.

## Primitives

Low-level commands for direct inspection and control:

- `hive trace run`
- `hive trace ls`
- `hive trace show`
- `hive trace summary`
- `hive trace diff`
- `hive trace diagnose`
- `hive trace replay`
- `hive trace anchors`
- `hive trace replay-plan`
- `hive trace flow ...`
- `hive trace tei validate`
- `hive trace tei ingest`

Use primitives when you want exact raw behavior and debugging control.

## Insight Macros

Composed, answer-first commands:

- `hive trace insight explain`
- `hive trace insight drift`
- `hive trace insight health`

Macros combine primitives and reasoning.

They include:

- provenance (`derived_from`)
- supporting evidence
- recommended next steps

## Ops

Lifecycle/admin controls:

- `hive trace ops archive`
- `hive trace ops unarchive`
- `hive trace ops prune`
- `hive trace ops reconcile`

Ops commands manage run lifecycle and trace storage.
