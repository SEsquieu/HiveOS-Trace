# HiveOS Trace

Replayable execution debugging for non-deterministic and agentic workflows.

Wrap an existing command, capture execution traces, and turn them into actionable insight.

Current public release line: `v0.3.2`.

AI workflows are inherently non-deterministic.

When something breaks, logs rarely explain:

- why the system chose a different path
- why behavior changed between runs
- how to reproduce the failure

HiveOS Trace captures execution and turns it into a **replayable execution model**.

Instead of just logs, it derives **execution anchors** — boundaries where a workflow safely closed — allowing developers to inspect runs, compare behavior, and replay execution from meaningful points.

---

# Install

```
pipx install hiveos-trace
```

Fallback:

```
python -m pip install hiveos-trace
```

---

# Quickstart Command

```
hive quickstart
```

No-browser variant:

```
hive quickstart --no-open
```

---

# 60-Second Quickstart

```
hive trace run --no-open -- python -c "print('hello trace')"
hive trace ls --limit 5
hive trace insight explain <run_id>
```

Inspect replay anchors:

```
hive trace anchors <run_id>
```

Generate a replay plan:

```
hive trace replay-plan <run_id> --recommended --explain
```

Execute a replay from the selected anchor:

```powershell
hive trace replay <run_id> --from-step-id <step_id> --no-open
```

---

# Framework Builder Quickstart (TEI)

```powershell
# validate event payloads before ingest
hive trace tei validate --file docs/examples/tei_batch.json --json

# ingest structured step/tool lineage events
hive trace tei ingest --file docs/examples/tei_batch.json --json
```

Notes:

- `hive trace tei ingest` requires `HIVE_TRACE_TEI_INGEST_ENABLED=true`.
- This is optional. Wrapper mode works without emitter integration.
- For builder shims that wrap executable commands, emit structured argv metadata when available so replay preserves quoted multi-word arguments.

---

# Command Model

- Primitives: `hive trace ...`
- Insight macros: `hive trace insight ...`
- Ops lifecycle: `hive trace ops ...`
- TEI utilities: `hive trace tei ...`

---

# What You Get (By Integration Level)

| Integration level | What works |
|---|---|
| Zero instrumentation (wrapper only) | `trace run`, `trace ls`, `trace show`, `trace summary`, `trace diff`, `trace diagnose`, `trace insight explain/drift/health` |
| OpenAI-compatible provider path | `trace run --proxy ...` request/response envelope capture plus normal run primitives |
| Instrumented workflow (step/checkpoint emitters) | TEI validation/ingest (`trace tei validate/ingest`), anchor discovery (`trace anchors`), anchored replay (`--from-step-id`, `--from-checkpoint-id`), replay planning (`trace replay-plan`), richer flow lineage (`trace flow ...`) |

For shimmed live runs in `v0.3.2`:
- replay from the original shimmed source run is reliable enough for live demos
- replayed runs do not yet automatically re-enter shim instrumentation, so replay-of-replay anchor discovery is not yet guaranteed

---

# Why HiveOS Trace

- Local-first: no required cloud account
- Works immediately as a wrapper
- Deeper value when instrumented (lineage + anchors)
- Replay, comparison, and diff for debugging non-deterministic behavior
- Macro insights (`explain`, `drift`, `health`) with provenance

---

# Screenshots

![Quickstart](screenshots/quickstart.png)  
![Trace run and list](screenshots/trace-run-and-ls.png)  
![Insight explain](screenshots/insight-explain.png)  
![Insight health](screenshots/insight-health.png)

---

# Docs

- [Quickstart](docs/quickstart.md)
- [TEI Contract](docs/tei-contract.md)
- [Primitives vs Macros](docs/primitives-vs-macros.md)
- [Why Hive Trace](docs/why-hive-trace.md)
- [Integrations](docs/integrations.md)
- [Roadmap](docs/roadmap.md)

---

# Demo Script (Copy/Paste)

```
hive trace run --no-open -- python -c "print('demo-success')"

hive trace run --no-open -- python -c "import sys; sys.stderr.write('demo-fail\n'); raise SystemExit(2)"

hive trace ls --limit 5

# pick run IDs from ls output
hive trace insight explain <run_id>
hive trace insight health --window 24h
hive trace insight drift <run_id_a> <run_id_b>
```

---

# Known Limits (Current Alpha)

- Anchors require emitted `step_id` / `checkpoint_id` events.
- Replay reliability is strongest when shims emit structured launcher metadata such as `payload.command_argv`.
- `insight health` is heuristic, not a policy-enforced SRE gate.
- Autonomous self-repair loops are a roadmap direction, not current default behavior.

---

# Links

PyPI: https://pypi.org/project/hiveos-trace/
