# Quickstart

## 1) Install

```powershell
pipx install hiveos-trace
```

## 2) Run and trace any command (zero instrumentation)

```powershell
hive trace run --no-open -- python -c "print('quickstart')"
```

## 3) Inspect recent runs

```powershell
hive trace ls --limit 5
```

## 4) Explain a run

```powershell
hive trace insight explain <run_id>
```

## 5) Compare two runs

```powershell
hive trace insight drift <run_id_a> <run_id_b>
```

## 6) View windowed health

```powershell
hive trace insight health --window 24h
```

## 7) Optional: OpenAI-compatible proxy capture

```powershell
hive trace run --proxy --no-open -- python app.py
```

## 8) Optional: Structured TEI payload path (builder mode)

```powershell
hive trace tei validate --file docs/examples/tei_batch.json --json
hive trace tei ingest --file docs/examples/tei_batch.json --json
```

Notes:
- `hive trace tei ingest` requires `HIVE_TRACE_TEI_INGEST_ENABLED=true`.
- Use this lane when you want richer step/tool/checkpoint lineage from framework emitters.
