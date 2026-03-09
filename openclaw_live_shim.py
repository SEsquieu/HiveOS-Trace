"""OpenClaw live shim runner for Hive Trace TEI ingestion.

Run:
  python openclaw_live_shim.py -- openclaw agent --session-id main --message "hello"

Windows shell-shim form:
  python openclaw_live_shim.py -- cmd /c openclaw agent --session-id main --message "hello"
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hiveos import config as hive_config
from hiveos.observe import ingest_tei_events
from hiveos.tei import TEI_VERSION


def _now_ms() -> int:
    return int(time.time() * 1000)


def _tei_event(
    *,
    event_type: str,
    run_id: str,
    source_framework: str,
    source_emitter: str,
    payload: dict,
    flow_id: str = "",
    step_id: str = "",
    parent_step_id: str = "",
    tool_call_id: str = "",
    step_type: str = "",
    attempt: int | None = None,
    outcome: str = "unknown",
) -> dict:
    item = {
        "tei_version": TEI_VERSION,
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "event_type": str(event_type or "").strip(),
        "occurred_at_ms": _now_ms(),
        "run_id": str(run_id or "").strip(),
        "source": {
            "framework": str(source_framework or "openclaw"),
            "emitter": str(source_emitter or "hive-openclaw-shim.v1"),
        },
        "payload": dict(payload or {}),
        "outcome": str(outcome or "unknown"),
    }
    if flow_id:
        item["flow_id"] = str(flow_id)
    if step_id:
        item["step_id"] = str(step_id)
    if parent_step_id:
        item["parent_step_id"] = str(parent_step_id)
    if tool_call_id:
        item["tool_call_id"] = str(tool_call_id)
    if step_type:
        item["step_type"] = str(step_type)
    if attempt is not None:
        item["attempt"] = int(attempt)
    return item


def _reader(stream, label, out_queue):
    try:
        for line in iter(stream.readline, ""):
            out_queue.put((label, line))
    finally:
        out_queue.put((label, None))


def _run_command(argv: list[str], *, cwd: str | None = None) -> tuple[int, list[tuple[str, str]]]:
    proc = subprocess.Popen(
        argv,
        cwd=cwd or None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        universal_newlines=True,
        bufsize=1,
        shell=False,
    )
    q = queue.Queue()
    t_out = threading.Thread(target=_reader, args=(proc.stdout, "stdout", q), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, "stderr", q), daemon=True)
    t_out.start()
    t_err.start()
    closed = set()
    chunks: list[tuple[str, str]] = []
    while len(closed) < 2:
        channel, data = q.get()
        if data is None:
            closed.add(channel)
            continue
        chunks.append((channel, data.rstrip("\n")))
        target = sys.stdout if channel == "stdout" else sys.stderr
        target.write(data)
        target.flush()
    proc.wait()
    return int(proc.returncode or 0), chunks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openclaw_live_shim.py",
        description="Wrap a live OpenClaw command and emit TEI events with replay boundary hints.",
    )
    parser.add_argument("--run-id", default="", help="Optional explicit run id.")
    parser.add_argument("--flow-id", default="", help="Optional explicit flow id.")
    parser.add_argument("--framework", default="openclaw", help="TEI source.framework value.")
    parser.add_argument("--emitter", default="hive-openclaw-shim.v1", help="TEI source.emitter value.")
    parser.add_argument("--cwd", default="", help="Optional command working directory.")
    parser.add_argument(
        "--write-file",
        default="",
        help="Optional JSON path to persist emitted TEI batch for inspection.",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command after '--'.")
    args = parser.parse_args(argv)

    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("error=no_command")
        print("hint=Use: python docs/examples/openclaw_live_shim.py -- openclaw agent ...")
        return 2

    run_id = str(args.run_id or "").strip() or f"observe-run:openclaw-live-{uuid.uuid4().hex[:10]}"
    flow_id = str(args.flow_id or "").strip() or f"flow:openclaw-live-{uuid.uuid4().hex[:8]}"
    source_framework = str(args.framework or "openclaw").strip() or "openclaw"
    source_emitter = str(args.emitter or "hive-openclaw-shim.v1").strip() or "hive-openclaw-shim.v1"
    cwd = str(args.cwd or "").strip() or None
    command_text = " ".join([str(part) for part in command])
    step_cmd = "step:openclaw.command"
    tool_call_id = "tool:openclaw.command:1"
    started_ms = _now_ms()

    events: list[dict] = []
    events.append(
        _tei_event(
            event_type="turn.start",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id="step:turn.start",
            step_type="agent_step",
            attempt=1,
            outcome="success",
            payload={
                "step_name": "turn.start",
                "command": command_text,
                "cwd": str(cwd or ""),
                "boundary_type": "step.generic",
                "idempotency_hint": "unknown",
                "side_effect": False,
                "external_write": False,
            },
        )
    )
    events.append(
        _tei_event(
            event_type="tool.request",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id=step_cmd,
            parent_step_id="step:turn.start",
            tool_call_id=tool_call_id,
            step_type="tool_call",
            attempt=1,
            outcome="success",
            payload={
                "step_name": "tool.request",
                "command": command_text,
                "canonical_anchor_type": "tool.request",
                "idempotency_hint": "high",
                "side_effect": True,
                "external_write": True,
            },
        )
    )

    try:
        exit_code, chunks = _run_command(command, cwd=cwd)
    except FileNotFoundError as exc:
        msg = str(exc)
        events.append(
            _tei_event(
                event_type="error",
                run_id=run_id,
                source_framework=source_framework,
                source_emitter=source_emitter,
                flow_id=flow_id,
                step_id=step_cmd,
                parent_step_id="step:turn.start",
                tool_call_id=tool_call_id,
                step_type="tool_call",
                attempt=1,
                outcome="failed",
                payload={
                    "step_name": "error",
                    "error": msg,
                    "canonical_anchor_type": "output.commit",
                    "idempotency_hint": "low",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )
        exit_code = 127
        chunks = []

    seq = 0
    for channel, text in chunks:
        seq += 1
        events.append(
            _tei_event(
                event_type="response.commit",
                run_id=run_id,
                source_framework=source_framework,
                source_emitter=source_emitter,
                flow_id=flow_id,
                step_id="step:openclaw.output",
                parent_step_id=step_cmd,
                step_type="output",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "response.commit",
                    "stream": channel,
                    "seq": seq,
                    "text": text,
                    "canonical_anchor_type": "output.commit",
                    "idempotency_hint": "low",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    elapsed_ms = max(0, _now_ms() - started_ms)
    run_outcome = "success" if int(exit_code) == 0 else "failed"
    events.append(
        _tei_event(
            event_type="tool.result",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id=step_cmd,
            parent_step_id="step:turn.start",
            tool_call_id=tool_call_id,
            step_type="tool_call",
            attempt=1,
            outcome=run_outcome,
            payload={
                "step_name": "tool.result",
                "exit_code": int(exit_code),
                "duration_ms": int(elapsed_ms),
                "canonical_anchor_type": "tool.result",
                "idempotency_hint": "medium",
                "side_effect": True,
                "external_write": True,
            },
        )
    )
    events.append(
        _tei_event(
            event_type="turn.finish",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id="step:turn.finish",
            parent_step_id=step_cmd,
            step_type="agent_step",
            attempt=1,
            outcome=run_outcome,
            payload={
                "step_name": "turn.finish",
                "exit_code": int(exit_code),
                "duration_ms": int(elapsed_ms),
                "idempotency_hint": "low",
                "side_effect": False,
                "external_write": False,
            },
        )
    )

    if str(args.write_file or "").strip():
        out_path = Path(str(args.write_file)).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
        print(f"tei_file={out_path}")

    print(f"tei_ingest_enabled={bool(getattr(hive_config, 'TRACE_TEI_INGEST_ENABLED', False))}")
    result = ingest_tei_events(events)
    print(
        f"run_id={run_id} flow_id={flow_id} command_exit={int(exit_code)} "
        f"ingest_ok={bool(result.get('ok'))} ingested={int(result.get('ingested') or 0)} "
        f"failed={int(result.get('failed') or 0)}"
    )
    if not bool(result.get("ok")):
        print(f"ingest_items={json.dumps(result.get('items') or [], separators=(',', ':'))}")
    print(f"next=hive trace anchors {run_id} --json")
    print(f"next=hive trace replay-plan {run_id} --recommended --explain")
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())