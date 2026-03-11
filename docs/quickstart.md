# Quickstart

## 1) Install

```
pipx install hiveos-trace
```

## 2) Run and trace any command (zero instrumentation)

```
hive trace run --no-open -- python -c "print('quickstart')"
```

## 3) Inspect recent runs

```
hive trace ls --limit 5
```

## 4) Explain a run

```
hive trace insight explain <run_id>
```

## 5) Compare two runs

```
hive trace insight drift <run_id_a> <run_id_b>
```

## 6) View windowed health

```
hive trace insight health --window 24h
```

## 7) Optional: OpenAI-compatible proxy capture

```
hive trace run --proxy --no-open -- python app.py
```

## 8) Optional: Structured TEI payload path (builder mode)

```
hive trace tei validate --file docs/examples/tei_batch.json --json
hive trace tei ingest --file docs/examples/tei_batch.json --json
```

Notes:
- `hive trace tei ingest` requires `HIVE_TRACE_TEI_INGEST_ENABLED=true`.
- Use this lane when you want richer step/tool/checkpoint lineage from framework emitters.
- For live command shims, include structured argv metadata (`payload.command_argv`) if the runtime launches a subprocess.

## 9) OpenClaw live replay demo

```powershell
$env:HIVE_TRACE_TEI_INGEST_ENABLED="true"
python openclaw_live_shim.py -- cmd /c openclaw agent --session-id main --message "demo replay anchor flow"
hive trace anchors <run_id>
hive trace replay-plan <run_id> --recommended --explain
hive trace replay <run_id> --from-step-id step:openclaw.output --no-open
```

Current status in `v0.3.2`:
- the original shimmed run is anchorable and replayable
- replay preserves quoted multi-word arguments correctly
- replayed runs do not yet automatically re-enter shim instrumentation
