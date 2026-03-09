"""LangChain live shim for Hive Trace TEI ingestion.

This mirrors the behavior/style of the OpenClaw live shim, but plugs into
LangChain via the callback system and emits canonical TEI lifecycle events.

Usage (example):
  python langchain_live_shim.py \
    --provider openai \
    --model gpt-4o-mini \
    --message "Summarize why replayable traces matter" \
    --write-file /tmp/langchain_tei.json

Environment:
  OPENAI_API_KEY must be set when using provider=openai.

Notes:
- This shim emits debugger-meaningful boundaries, not every possible callback.
- Tool events are emitted when the wrapped LangChain runnable invokes tools.
- A synthetic decision event is emitted after model/tool boundaries when useful.
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
# Allow this file to live either in docs/examples or as a loose standalone file.
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
        return repr(value)


def _extract_text_from_llm_result(result: Any) -> str:
    if result is None:
        return ""
    # LangChain AIMessage
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            else:
                maybe_text = getattr(item, "text", None)
                if maybe_text:
                    parts.append(str(maybe_text))
        return "\n".join([p for p in parts if p])
    if isinstance(result, str):
        return result
    return repr(result)


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
            "framework": str(source_framework or "langchain"),
            "emitter": str(source_emitter or "hive-langchain-shim.v1"),
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


class _EventCollector:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.step_names: dict[str, str] = {}
        self.step_types: dict[str, str] = {}
        self.tool_call_ids: dict[str, str] = {}
        self.last_decision_by_parent: dict[str, str] = {}

    def append(self, event: dict) -> None:
        self.events.append(event)


try:
    from langchain_core.callbacks.base import BaseCallbackHandler
except Exception:  # pragma: no cover - only hit if langchain isn't installed
    BaseCallbackHandler = object  # type: ignore


class HiveLangChainLiveShim(BaseCallbackHandler):
    raise_error = False

    def __init__(
        self,
        *,
        collector: _EventCollector,
        run_id: str,
        flow_id: str,
        source_framework: str = "langchain",
        source_emitter: str = "hive-langchain-shim.v1",
        root_name: str = "langchain.invoke",
    ) -> None:
        self.collector = collector
        self.run_id = run_id
        self.flow_id = flow_id
        self.source_framework = source_framework
        self.source_emitter = source_emitter
        self.root_name = root_name
        self.root_step_id = "step:turn.start"
        self.started_ms = _now_ms()
        self.collector.append(
            _tei_event(
                event_type="turn.start",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=self.root_step_id,
                step_type="agent_step",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "turn.start",
                    "root_name": self.root_name,
                    "boundary_type": "step.generic",
                    "idempotency_hint": "unknown",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def _name_for(self, serialized: Any, fallback: str) -> str:
        if isinstance(serialized, dict):
            return str(serialized.get("name") or serialized.get("id") or fallback)
        return fallback

    def _step_id(self, run_id: Any, prefix: str) -> str:
        text = str(run_id or "").strip()
        return f"step:{prefix}:{text}" if text else f"step:{prefix}:{uuid.uuid4().hex[:8]}"

    def _parent(self, parent_run_id: Any) -> str:
        text = str(parent_run_id or "").strip()
        if not text:
            return self.root_step_id
        # We do not know the original prefix, so use any known id by scanning.
        known_prefixes = ["chain", "model", "tool", "retriever", "decision"]
        for prefix in known_prefixes:
            candidate = f"step:{prefix}:{text}"
            if candidate in self.collector.step_names:
                return candidate
        return self.root_step_id

    def _emit_decision(self, *, parent_step_id: str, decision_text: str, decision_kind: str = "agent_choice") -> None:
        if not decision_text:
            return
        previous = self.collector.last_decision_by_parent.get(parent_step_id)
        if previous == decision_text:
            return
        step_id = f"step:decision:{uuid.uuid4().hex[:10]}"
        self.collector.step_names[step_id] = "decision"
        self.collector.step_types[step_id] = "agent_step"
        self.collector.last_decision_by_parent[parent_step_id] = decision_text
        self.collector.append(
            _tei_event(
                event_type="decision",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="agent_step",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "decision",
                    "decision_kind": decision_kind,
                    "decision_text": decision_text,
                    "canonical_anchor_type": "decision",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        step_id = self._step_id(run_id, "chain")
        parent_step_id = self._parent(parent_run_id)
        name = self._name_for(serialized, "chain")
        self.collector.step_names[step_id] = name
        self.collector.step_types[step_id] = "agent_step"
        self.collector.append(
            _tei_event(
                event_type="turn.start" if parent_step_id == self.root_step_id and name == self.root_name else "checkpoint",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="agent_step",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": name,
                    "inputs": _safe_jsonable(inputs),
                    "canonical_anchor_type": "checkpoint.state",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
                metadata={"tags": tags or [], "meta": _safe_jsonable(metadata) or {}},
            )
        )

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "chain")
        parent_step_id = self._parent(parent_run_id)
        name = self.collector.step_names.get(step_id, "chain")
        self.collector.append(
            _tei_event(
                event_type="checkpoint",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="agent_step",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": name,
                    "outputs": _safe_jsonable(outputs),
                    "canonical_anchor_type": "checkpoint.state",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def on_chain_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "chain")
        parent_step_id = self._parent(parent_run_id)
        name = self.collector.step_names.get(step_id, "chain")
        self.collector.append(
            _tei_event(
                event_type="error",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="agent_step",
                attempt=1,
                outcome="failed",
                payload={
                    "step_name": name,
                    "error": repr(error),
                    "canonical_anchor_type": "output.commit",
                    "idempotency_hint": "low",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        step_id = self._step_id(run_id, "model")
        parent_step_id = self._parent(parent_run_id)
        name = self._name_for(serialized, "chat_model")
        self.collector.step_names[step_id] = name
        self.collector.step_types[step_id] = "model_call"
        self.collector.append(
            _tei_event(
                event_type="model.request",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="model_call",
                attempt=1,
                outcome="running",
                payload={
                    "step_name": "model.request",
                    "model_name": name,
                    "messages": _safe_jsonable(messages),
                    "canonical_anchor_type": "model.request",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
                metadata={"tags": tags or [], "meta": _safe_jsonable(metadata) or {}},
            )
        )

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        step_id = self._step_id(run_id, "model")
        parent_step_id = self._parent(parent_run_id)
        name = self._name_for(serialized, "llm")
        self.collector.step_names[step_id] = name
        self.collector.step_types[step_id] = "model_call"
        self.collector.append(
            _tei_event(
                event_type="model.request",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="model_call",
                attempt=1,
                outcome="running",
                payload={
                    "step_name": "model.request",
                    "model_name": name,
                    "prompts": _safe_jsonable(prompts),
                    "canonical_anchor_type": "model.request",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
                metadata={"tags": tags or [], "meta": _safe_jsonable(metadata) or {}},
            )
        )

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "model")
        parent_step_id = self._parent(parent_run_id)
        text = _extract_text_from_llm_result(response)
        self.collector.append(
            _tei_event(
                event_type="model.response",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="model_call",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "model.response",
                    "text": text,
                    "raw_response": _safe_jsonable(response),
                    "canonical_anchor_type": "model.response",
                    "idempotency_hint": "medium",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )
        if text:
            self._emit_decision(parent_step_id=parent_step_id, decision_text=text[:400], decision_kind="model_output")

    def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "model")
        parent_step_id = self._parent(parent_run_id)
        self.collector.append(
            _tei_event(
                event_type="error",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="model_call",
                attempt=1,
                outcome="failed",
                payload={
                    "step_name": "model.error",
                    "error": repr(error),
                    "canonical_anchor_type": "output.commit",
                    "idempotency_hint": "low",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, tags=None, metadata=None, inputs=None, **kwargs):
        step_id = self._step_id(run_id, "tool")
        parent_step_id = self._parent(parent_run_id)
        name = self._name_for(serialized, "tool")
        tool_call_id = f"tool:{name}:{str(run_id)[:12]}"
        self.collector.step_names[step_id] = name
        self.collector.step_types[step_id] = "tool_call"
        self.collector.tool_call_ids[step_id] = tool_call_id
        self.collector.append(
            _tei_event(
                event_type="tool.request",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                tool_call_id=tool_call_id,
                step_type="tool_call",
                attempt=1,
                outcome="running",
                payload={
                    "step_name": "tool.request",
                    "tool_name": name,
                    "tool_input": _safe_jsonable(inputs if inputs is not None else input_str),
                    "canonical_anchor_type": "tool.request",
                    "idempotency_hint": "high",
                    "side_effect": True,
                    "external_write": True,
                },
                metadata={"tags": tags or [], "meta": _safe_jsonable(metadata) or {}},
            )
        )
        self._emit_decision(parent_step_id=parent_step_id, decision_text=f"selected_tool={name}", decision_kind="tool_select")

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "tool")
        parent_step_id = self._parent(parent_run_id)
        name = self.collector.step_names.get(step_id, "tool")
        tool_call_id = self.collector.tool_call_ids.get(step_id, f"tool:{name}:{str(run_id)[:12]}")
        self.collector.append(
            _tei_event(
                event_type="tool.result",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                tool_call_id=tool_call_id,
                step_type="tool_call",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "tool.result",
                    "tool_name": name,
                    "tool_output": _safe_jsonable(output),
                    "canonical_anchor_type": "tool.result",
                    "idempotency_hint": "medium",
                    "side_effect": True,
                    "external_write": True,
                },
            )
        )

    def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "tool")
        parent_step_id = self._parent(parent_run_id)
        name = self.collector.step_names.get(step_id, "tool")
        tool_call_id = self.collector.tool_call_ids.get(step_id, f"tool:{name}:{str(run_id)[:12]}")
        self.collector.append(
            _tei_event(
                event_type="tool.result",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                tool_call_id=tool_call_id,
                step_type="tool_call",
                attempt=1,
                outcome="failed",
                payload={
                    "step_name": "tool.result",
                    "tool_name": name,
                    "error": repr(error),
                    "canonical_anchor_type": "tool.result",
                    "idempotency_hint": "medium",
                    "side_effect": True,
                    "external_write": True,
                },
            )
        )

    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, tags=None, metadata=None, **kwargs):
        step_id = self._step_id(run_id, "retriever")
        parent_step_id = self._parent(parent_run_id)
        name = self._name_for(serialized, "retriever")
        self.collector.step_names[step_id] = name
        self.collector.step_types[step_id] = "observe"
        self.collector.append(
            _tei_event(
                event_type="checkpoint",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="observe",
                attempt=1,
                outcome="running",
                payload={
                    "step_name": "observe.start",
                    "query": query,
                    "canonical_anchor_type": "checkpoint.state",
                    "idempotency_hint": "high",
                    "side_effect": False,
                    "external_write": False,
                },
                metadata={"tags": tags or [], "meta": _safe_jsonable(metadata) or {}},
            )
        )

    def on_retriever_end(self, documents, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "retriever")
        parent_step_id = self._parent(parent_run_id)
        self.collector.append(
            _tei_event(
                event_type="checkpoint",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="observe",
                attempt=1,
                outcome="success",
                payload={
                    "step_name": "observe.end",
                    "documents": _safe_jsonable(documents),
                    "canonical_anchor_type": "checkpoint.state",
                    "idempotency_hint": "high",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def on_retriever_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        step_id = self._step_id(run_id, "retriever")
        parent_step_id = self._parent(parent_run_id)
        self.collector.append(
            _tei_event(
                event_type="error",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id=step_id,
                parent_step_id=parent_step_id,
                step_type="observe",
                attempt=1,
                outcome="failed",
                payload={
                    "step_name": "observe.error",
                    "error": repr(error),
                    "canonical_anchor_type": "output.commit",
                    "idempotency_hint": "low",
                    "side_effect": False,
                    "external_write": False,
                },
            )
        )

    def finish(self, *, output: Any = None, exit_code: int = 0) -> list[dict]:
        outcome = "success" if int(exit_code) == 0 else "failed"
        elapsed_ms = max(0, _now_ms() - self.started_ms)
        if output is not None:
            text = _extract_text_from_llm_result(output)
            if text:
                self.collector.append(
                    _tei_event(
                        event_type="response.commit",
                        run_id=self.run_id,
                        source_framework=self.source_framework,
                        source_emitter=self.source_emitter,
                        flow_id=self.flow_id,
                        step_id="step:langchain.output",
                        parent_step_id=self.root_step_id,
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
        self.collector.append(
            _tei_event(
                event_type="turn.finish",
                run_id=self.run_id,
                source_framework=self.source_framework,
                source_emitter=self.source_emitter,
                flow_id=self.flow_id,
                step_id="step:turn.finish",
                parent_step_id=self.root_step_id,
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
        return self.collector.events


def _build_demo_chain(provider: str, model: str, message: str, callback_handler: HiveLangChainLiveShim):
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda

    provider_text = str(provider or "openai").strip().lower()
    if provider_text == "openai":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=model, temperature=0)
    else:
        raise SystemExit(f"Unsupported provider for demo chain: {provider}")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a concise assistant. Explain your answer briefly."),
            ("human", "{message}"),
        ]
    )

    def passthrough_parser(ai_message: Any) -> Any:
        return ai_message

    chain = prompt | llm | RunnableLambda(passthrough_parser)
    return chain.with_config({"callbacks": [callback_handler], "run_name": "langchain.invoke"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="langchain_live_shim.py",
        description="Run a LangChain invocation and emit TEI events with replay boundary hints.",
    )
    parser.add_argument("--run-id", default="", help="Optional explicit run id.")
    parser.add_argument("--flow-id", default="", help="Optional explicit flow id.")
    parser.add_argument("--framework", default="langchain", help="TEI source.framework value.")
    parser.add_argument("--emitter", default="hive-langchain-shim.v1", help="TEI source.emitter value.")
    parser.add_argument("--provider", default="openai", help="LangChain provider to use in the demo runner.")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model name for the demo runner.")
    parser.add_argument("--message", default="Why are replayable traces useful for agents?", help="User message for the demo runner.")
    parser.add_argument("--write-file", default="", help="Optional JSON path to persist emitted TEI batch for inspection.")
    args = parser.parse_args(argv)

    run_id = str(args.run_id or "").strip() or f"observe-run:langchain-live-{uuid.uuid4().hex[:10]}"
    flow_id = str(args.flow_id or "").strip() or f"flow:langchain-live-{uuid.uuid4().hex[:8]}"
    collector = _EventCollector()
    shim = HiveLangChainLiveShim(
        collector=collector,
        run_id=run_id,
        flow_id=flow_id,
        source_framework=str(args.framework or "langchain").strip() or "langchain",
        source_emitter=str(args.emitter or "hive-langchain-shim.v1").strip() or "hive-langchain-shim.v1",
        root_name="langchain.invoke",
    )

    exit_code = 0
    output = None
    try:
        chain = _build_demo_chain(args.provider, args.model, args.message, shim)
        output = chain.invoke({"message": args.message})
        text = _extract_text_from_llm_result(output)
        if text:
            print(text)
    except Exception as exc:
        exit_code = 1
        collector.append(
            _tei_event(
                event_type="error",
                run_id=run_id,
                source_framework=str(args.framework or "langchain").strip() or "langchain",
                source_emitter=str(args.emitter or "hive-langchain-shim.v1").strip() or "hive-langchain-shim.v1",
                flow_id=flow_id,
                step_id="step:langchain.error",
                parent_step_id="step:turn.start",
                step_type="agent_step",
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

    events = shim.finish(output=output, exit_code=exit_code)

    if str(args.write_file or "").strip():
        out_path = Path(str(args.write_file)).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
        print(f"tei_file={out_path}")

    print(f"tei_ingest_enabled={bool(getattr(hive_config, 'TRACE_TEI_INGEST_ENABLED', False))}")
    result = ingest_tei_events(events)
    print(
        f"run_id={run_id} flow_id={flow_id} langchain_exit={int(exit_code)} "
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
