# Integrations

HiveOS Trace supports two adoption lanes:

1. Wrapper lane (immediate, no framework changes)
2. Emitter lane (structured lineage via TEI)

## Wrapper Lane

Works with any executable command, including agent runtimes and custom launchers.

```
hive trace run --no-open -- <your-command...>
hive trace ls --limit 5
hive trace show <run_id> --limit 120
hive trace diagnose <run_id>
```

## OpenAI-Compatible Proxy Lane

Use when your runtime talks to an OpenAI-compatible endpoint.

```
hive trace run --proxy --no-open -- <your-command...>
```

## TEI Emitter Lane

For framework developers who want richer step/tool/checkpoint observability.

Contract reference:
- `docs/tei-contract.md`

```
hive trace tei validate --file docs/examples/tei_batch.json --json
hive trace tei ingest --file docs/examples/tei_batch.json --json
```

Notes:
- `hive trace tei ingest` requires `HIVE_TRACE_TEI_INGEST_ENABLED=true`.
- Keep strict TEI version mode enabled by default.

## OpenClaw Path

For OpenClaw users:

1. Start with wrapper mode on your real OpenClaw command.
2. Add proxy mode if provider path is OpenAI-compatible.
3. Add TEI emitter shim only when you need deeper step-level lineage.
