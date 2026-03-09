"""OpenAI / OpenAI-compatible live shim for Hive Trace TEI ingestion.

This mirrors the behavior/style of the OpenClaw live shim but wraps direct API
calls instead of a subprocess. It supports both the Responses API and the
Chat Completions API.

Usage (responses API):
  python openai_live_shim.py \
    --api responses \
    --model gpt-4o-mini \
    --message "Summarize why replayable traces matter" \
    --write-file /tmp/openai_tei.json

Usage (chat completions API):
  python openai_live_shim.py \
    --api chat \
    --model gpt-4o-mini \
    --message "Summarize why replayable traces matter"

Environment:
  OPENAI_API_KEY must be set.
  OPENAI_BASE_URL may be set for OpenAI-compatible providers.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_THIS_FILE = Path(__file__).resolve()
_repo_candidates = [_THIS_FILE.parents[i] for i in range(min(4, len(_THIS_FILE.parents)))]
for candidate in _repo_candidates:
    if (candidate / "hiveos").exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
        break

from hiveos import config as hive_config  # type: ignore
from hiveos.observe import ingest_tei_events  # type: ignore
from hiveos.tei import TEI_VERSION  # type: ignore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_jsonable(value: Any) -> Any:
    if value is None:
        return None
    try:
        json.dumps(value)
        return value
    except Exception:
        if isinstance(value, (list, tuple)):
            return [_safe_jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _safe_jsonable(v) for k, v in value.items()}
        dumped = getattr(value, "model_dump", None)
        if callable(dumped):
            try:
                return dumped()
            except Exception:
                pass
        return repr(value)


def _text_from_responses_api(obj: Any) -> str:
    if obj is None:
        return ""
    output_text = getattr(obj, "output_text", None)
    if output_text:
        return str(output_text)
    payload = _safe_jsonable(obj)
    try:
        outputs = payload.get("output") or []
        parts: list[str] = []
        for item in outputs:
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    parts.append(str(content.get("text")))
        return "\n".join(parts)
    except Exception:
        return repr(obj)


def _text_from_chat_api(obj: Any) -> str:
    if obj is None:
        return ""
    payload = _safe_jsonable(obj)
    try:
        choices = payload.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "\n".join([str(x.get("text") or x) for x in content])
    except Exception:
        return repr(obj)
    return repr(obj)


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
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> dict:
    item = {
        "tei_version": TEI_VERSION,
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "event_type": str(event_type or "").strip(),
        "occurred_at_ms": _now_ms(),
        "run_id": str(run_id or "").strip(),
        "source": {
            "framework": str(source_framework or "openai"),
            "emitter": str(source_emitter or "hive-openai-shim.v1"),
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
    if metadata:
        item["metadata"] = metadata
    if tags:
        item["tags"] = tags
    return item


def _build_openai_client(base_url: str | None = None):
    from openai import OpenAI
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openai_live_shim.py",
        description="Run an OpenAI/OpenAI-compatible request and emit TEI events with replay boundary hints.",
    )
    parser.add_argument("--run-id", default="", help="Optional explicit run id.")
    parser.add_argument("--flow-id", default="", help="Optional explicit flow id.")
    parser.add_argument("--framework", default="openai", help="TEI source.framework value.")
    parser.add_argument("--emitter", default="hive-openai-shim.v1", help="TEI source.emitter value.")
    parser.add_argument("--api", choices=["responses", "chat"], default="responses", help="Which OpenAI API surface to call.")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model name.")
    parser.add_argument("--message", default="Why are replayable traces useful for agents?", help="User message.")
    parser.add_argument("--system", default="You are a concise assistant. Explain your answer briefly.", help="System instruction.")
    parser.add_argument("--base-url", default="", help="Optional OpenAI-compatible base URL.")
    parser.add_argument("--write-file", default="", help="Optional JSON path to persist emitted TEI batch for inspection.")
    args = parser.parse_args(argv)

    run_id = str(args.run_id or "").strip() or f"observe-run:openai-live-{uuid.uuid4().hex[:10]}"
    flow_id = str(args.flow_id or "").strip() or f"flow:openai-live-{uuid.uuid4().hex[:8]}"
    source_framework = str(args.framework or "openai").strip() or "openai"
    source_emitter = str(args.emitter or "hive-openai-shim.v1").strip() or "hive-openai-shim.v1"
    started_ms = _now_ms()

    step_turn = "step:turn.start"
    step_model = "step:model.request"
    step_decision = "step:decision.model"
    step_output = "step:openai.output"
    events: list[dict] = []

    input_payload: dict[str, Any]
    if args.api == "responses":
        input_payload = {
            "model": args.model,
            "instructions": args.system,
            "input": args.message,
        }
    else:
        input_payload = {
            "model": args.model,
            "messages": [
                {"role": "system", "content": args.system},
                {"role": "user", "content": args.message},
            ],
        }

    events.append(
        _tei_event(
            event_type="turn.start",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id=step_turn,
            step_type="agent_step",
            attempt=1,
            outcome="success",
            payload={
                "step_name": "turn.start",
                "api": args.api,
                "model": args.model,
                "boundary_type": "step.generic",
                "idempotency_hint": "unknown",
                "side_effect": False,
                "external_write": False,
            },
        )
    )
    events.append(
        _tei_event(
            event_type="model.request",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id=step_model,
            parent_step_id=step_turn,
            step_type="model_call",
            attempt=1,
            outcome="running",
            payload={
                "step_name": "model.request",
                "request": _safe_jsonable(input_payload),
                "canonical_anchor_type": "model.request",
                "idempotency_hint": "medium",
                "side_effect": False,
                "external_write": False,
            },
        )
    )

    exit_code = 0
    raw_response = None
    text = ""
    try:
        client = _build_openai_client(base_url=str(args.base_url or "").strip() or None)
        if args.api == "responses":
            raw_response = client.responses.create(**input_payload)
            text = _text_from_responses_api(raw_response)
        else:
            raw_response = client.chat.completions.create(**input_payload)
            text = _text_from_chat_api(raw_response)
        if text:
            print(text)
    except Exception as exc:
        exit_code = 1
        events.append(
            _tei_event(
                event_type="error",
                run_id=run_id,
                source_framework=source_framework,
                source_emitter=source_emitter,
                flow_id=flow_id,
                step_id="step:openai.error",
                parent_step_id=step_model,
                step_type="model_call",
                attempt=1,
                outcome="failed",
                payload={
                    "step_name": "error",
                    "error": repr(exc),
                    "canonical_anchor_type": "output.commit",
                    "idempotency_hint": "low",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )
        print(repr(exc), file=sys.stderr)

    if raw_response is not None:
        events.append(
            _tei_event(
                event_type="model.response",
                run_id=run_id,
                source_framework=source_framework,
                source_emitter=source_emitter,
                flow_id=flow_id,
                step_id=step_model,
                parent_step_id=step_turn,
                step_type="model_call",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "model.response",
                    "text": text,
                    "raw_response": _safe_jsonable(raw_response),
                    "canonical_anchor_type": "model.response",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )
        if text:
            events.append(
                _tei_event(
                    event_type="decision",
                    run_id=run_id,
                    source_framework=source_framework,
                    source_emitter=source_emitter,
                    flow_id=flow_id,
                    step_id=step_decision,
                    parent_step_id=step_model,
                    step_type="agent_step",
                    attempt=1,
                    outcome="success",
                    payload={
                        "step_name": "decision",
                        "decision_kind": "model_output",
                        "decision_text": text[:400],
                        "canonical_anchor_type": "decision",
                        "idempotency_hint": "medium",
                        "side_effect": False,
                        "external_write": False,
                    },
                )
            )
            events.append(
                _tei_event(
                    event_type="response.commit",
                    run_id=run_id,
                    source_framework=source_framework,
                    source_emitter=source_emitter,
                    flow_id=flow_id,
                    step_id=step_output,
                    parent_step_id=step_model,
                    step_type="output",
                    attempt=1,
                    outcome="success",
                    payload={
                        "step_name": "response.commit",
                        "stream": "final",
                        "seq": 1,
                        "text": text,
                        "canonical_anchor_type": "output.commit",
                        "idempotency_hint": "low",
                        "side_effect": False,
                        "external_write": False,
                    },
                )
            )

    elapsed_ms = max(0, _now_ms() - started_ms)
    outcome = "success" if exit_code == 0 else "failed"
    events.append(
        _tei_event(
            event_type="turn.finish",
            run_id=run_id,
            source_framework=source_framework,
            source_emitter=source_emitter,
            flow_id=flow_id,
            step_id="step:turn.finish",
            parent_step_id=step_model,
            step_type="agent_step",
            attempt=1,
            outcome=outcome,
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
        f"run_id={run_id} flow_id={flow_id} openai_exit={int(exit_code)} "
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
