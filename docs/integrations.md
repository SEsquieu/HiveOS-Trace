# Integrations

HiveOS Trace supports two adoption lanes:

1. Wrapper lane (immediate, no framework changes)
2. Emitter lane (structured lineage via TEI)

---

# Wrapper Lane

Works with any executable command, including agent runtimes and custom launchers.

```
hive trace run --no-open -- <your-command...>
hive trace ls --limit 5
hive trace show <run_id> --limit 120
hive trace diagnose <run_id>
```

Wrapper mode provides:

- run capture
- trace inspection
- drift comparison
- insight macros
- anchor discovery
- replay planning

No code changes required.

---

# OpenAI-Compatible Proxy Lane

Use when your runtime communicates with an OpenAI-compatible endpoint.

```
hive trace run --proxy --no-open -- <your-command...>
```

This captures request and response envelopes alongside the execution trace.

This is useful when debugging:

- model routing issues
- response drift
- prompt/response anomalies
- tool-calling behavior

---

# TEI Emitter Lane

For framework developers who want deeper execution visibility.

This integration emits structured lineage events that HiveOS Trace can ingest.

Contract reference:

```
docs/tei-contract.md
```

Example validation:

```
hive trace tei validate --file docs/examples/tei_batch.json --json
```

Example ingestion:

```
hive trace tei ingest --file docs/examples/tei_batch.json --json
```

TEI events enable:

- step lineage tracking
- checkpoint anchors
- replay boundary detection
- richer flow-level debugging

---

# Choosing an Integration Path

Most users should start with **wrapper mode**.

It provides immediate value with zero setup.

Framework builders and platform developers can add **TEI emitters** later to unlock:

- richer anchor discovery
- deeper replay planning
- more deterministic debugging boundaries
