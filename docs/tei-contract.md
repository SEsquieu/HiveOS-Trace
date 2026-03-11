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

## Replay-Safety Hints For Shim Builders

These fields are optional, but strongly recommended when shims want replay quality that survives real-world command lines and side effects.

Recommended payload hints:

1. `canonical_anchor_type`
2. `idempotency_hint` (`low|medium|high|unknown`)
3. `side_effect` (`true|false`)
4. `external_write` (`true|false`)

If the shim wraps a subprocess or launcher command, also include:

1. `payload.command` (human-readable flattened command string)
2. `payload.command_argv` (structured argv array in execution order)

Why `command_argv` matters:
- replay command recovery in `v0.3.2` prefers structured argv when available
- this preserves quoted multi-word arguments that are otherwise lossy when rebuilt from a flat string
- practical example:
  - `--message "demo replay anchor flow"`

Windows-specific note:
- if the target runtime is shell-shimmed, the documented invocation may need to include `cmd /c ...`
- treat that shell wrapper as part of the canonical argv that should be preserved

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

Current limitation:
- replayed runs do not yet automatically re-enter the original shim/instrumentation layer
- native anchors are therefore strongest on the original shimmed run until replay-through-shim continuity lands
