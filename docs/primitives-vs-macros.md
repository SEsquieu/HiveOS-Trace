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
- `hive trace flow ...`
- `hive trace tei validate`
- `hive trace tei ingest`

Use primitives when you want exact raw behavior.

## Insight Macros

Composed, answer-first commands:

- `hive trace insight explain`
- `hive trace insight drift`
- `hive trace insight health`

Macros include provenance (`derived_from`) and actionable next steps.

## Ops

Lifecycle/admin controls:

- `hive trace ops archive`
- `hive trace ops unarchive`
- `hive trace ops prune`
- `hive trace ops reconcile`
- `hive trace ops export`
- `hive trace ops import`

## Practical Guidance

1. Start with primitives for exact observability.
2. Use insight macros for faster decision support.
3. Use TEI utilities when integrating framework emitters.
