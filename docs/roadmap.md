# Roadmap

## Now

- Stable primitive trace commands
- Insight macros: explain, drift, health
- Ops namespace for lifecycle/admin workflows
- TEI utilities: validate + ingest
- Framework integration docs for OpenClaw and OpenAI-compatible runtimes
- Canonical trace runtime decoupled from platform core (compat shim preserved)
- Replay from ranked anchors is validated on shimmed live runs
- Replay command recovery prefers structured argv metadata when shims provide it

## Next

- Replay-through-shim continuity for replayed runs
- Checkpoint preference and deterministic replay utility hardening
- Boundary-quality improvements from native shim/runtime emitters
- More runtime adapters and emitter shims for structured lineage events
- Stronger operator UX for flow-heavy agent traces

## Longer Term

- Agent self-diagnosis and bounded repair loops
- Policy-constrained automated replay and remediation
- Richer run scoring and before/after evaluation workflows
