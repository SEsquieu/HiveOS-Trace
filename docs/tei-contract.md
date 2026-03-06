# TEI Contract (Shim Builders)

This is the current contract for framework shims that emit events to HiveOS Trace.

Current contract version: `tei_version = "0.1"` (HiveOS Trace `v0.2.0` line).

## Required Fields

Each TEI event must include:

1. `tei_version` (string)
2. `event_id` (string)
3. `event_type` (string)
4. `occurred_at_ms` (integer epoch ms, `> 0`)
5. `run_id` (string)
6. `source` (object)
7. `payload` (object)

Required source field:

1. `source.framework` (string)

## Optional Lineage Fields

Include these when available:

1. `flow_id`
2. `step_id`
3. `parent_step_id`
4. `tool_call_id`
5. `checkpoint_id`
6. `attempt` (integer, `>= 1`)
7. `step_type`
8. `outcome` (`success|failed|denied|running|unknown`)

Optional metadata:

1. `metadata` (object)
2. `tags` (array of non-empty strings)

## Validation and Ingest

Validate before ingest:

```powershell
hive trace tei validate --file your_events.json --json
```

Ingest into trace store:

```powershell
hive trace tei ingest --file your_events.json --json
```

Notes:
- Ingest requires `HIVE_TRACE_TEI_INGEST_ENABLED=true`.
- Strict version checking is on by default.
- Use `--no-strict-version` only for compatibility testing/migration.

## Compatibility Guarantees (Current)

For the `0.2.x` line:

1. Required field names above are treated as contract-stable.
2. Optional fields are additive; missing optional fields are acceptable.
3. Unknown extra fields should be considered non-breaking (ignored unless adopted later).
4. CLI validation/ingest commands are the recommended shim entrypoint for conformance.

Potential pre-`1.0` changes:

1. Additional optional fields may be introduced.
2. Event-type conventions may expand.
3. Default strictness policy may be refined, but explicit flags will remain.

## Minimal Event Example

```json
{
  "tei_version": "0.1",
  "event_id": "evt-001",
  "event_type": "agent.tool_call",
  "occurred_at_ms": 1772800000000,
  "run_id": "observe-run:demo-001",
  "source": {
    "framework": "your-framework",
    "emitter": "hive-shim.v1"
  },
  "flow_id": "flow:demo",
  "step_id": "step:search",
  "parent_step_id": "step:plan",
  "tool_call_id": "tool:web.search:1",
  "attempt": 1,
  "step_type": "tool_call",
  "outcome": "success",
  "payload": {
    "query": "example",
    "result_count": 3
  }
}
```
