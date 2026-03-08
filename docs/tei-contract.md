# TEI Contract (Shim Builders)

This is the current contract for framework shims that emit events to HiveOS Trace.

Current contract version:

`tei_version = "0.1"`

Compatible with HiveOS Trace `v0.3.x`.

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

## Optional Metadata

Optional metadata fields:

1. `metadata` (object)
2. `tags` (array of non-empty strings)

## Event Design Guidance

Emit events at stable execution boundaries such as:

- step start
- tool request
- tool result
- checkpoint creation
- response commit
- error/failure

Stable boundaries improve:

- anchor discovery
- replay planning
- trace explainability
