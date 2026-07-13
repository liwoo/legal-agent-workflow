"""Shared test scaffolding.

One physical PDF and one metadata payload seed *every* case: the PDF at
``SHARED_PDF`` is always read by the ingest node, while the routing is steered
deterministically by overriding the metadata text (``summary`` / ``senders_ask``
/ counterparty flags / ``related_contracts``). That split is deliberate — the
document is exercised on-disk, but the branch a run takes is a pure function of
the intake metadata, so each node can be targeted in isolation.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from contract_triage import heuristics
from contract_triage.data import item_from_metadata
from contract_triage.executors import HumanDecision
from contract_triage.models import InboxItem
from contract_triage.state import TriageRequest, TriageState
from contract_triage.workflow import build_workflow

# The single shared fixture (see data/test/README.md).
_TEST_DIR = Path(__file__).resolve().parents[3] / "data" / "test" / "CR-2026-050"
SHARED_PDF = str(_TEST_DIR / "cr-2026-050-intake.pdf")
BASE_META: dict[str, Any] = json.loads((_TEST_DIR / "metadata.json").read_text())


def make_metadata(**overrides: Any) -> dict[str, Any]:
    """A copy of the shared metadata with fields overridden to steer routing."""
    meta = dict(BASE_META)
    meta.update(overrides)
    return meta


def make_item(**overrides: Any) -> InboxItem:
    """Build the entry ``InboxItem`` from metadata + the shared PDF path."""
    return item_from_metadata(make_metadata(**overrides), SHARED_PDF)


# Optional intake fields the flat TriageRequest form exposes (steerable in tests).
_OPTIONAL_FIELDS = ("name", "counterparty", "summary", "senders_ask", "received_from")


def make_request(pdf_path: str | None = SHARED_PDF, **overrides: Any) -> TriageRequest:
    """Build a flat :class:`TriageRequest` from the shared intake facts.

    ``id``/``date_received``/``pdf_path`` are always supplied (they are required).
    ``related_contracts`` accepts a list (joined to the comma-separated form
    string); other overrides steer classification via the text. Pass
    ``pdf_path=""`` to exercise the no-document path.
    """
    fields: dict[str, Any] = {
        "id": overrides.get("id", BASE_META["id"]),
        "date_received": overrides.get("date_received", BASE_META["date_received"]),
        "pdf_path": SHARED_PDF if pdf_path is None else pdf_path,
    }
    for k in _OPTIONAL_FIELDS:
        if k in overrides:
            fields[k] = overrides[k]
        elif k in BASE_META:
            fields[k] = BASE_META[k]
    related = overrides.get("related_contracts", BASE_META.get("related_contracts", []))
    fields["related_contracts"] = ",".join(related) if isinstance(related, list) else str(related)
    return TriageRequest(**fields)


def classified(**overrides: Any) -> TriageState:
    """Entry state as it exists right after the ``classify`` node.

    Suitable input for the intake/triage routers, which read
    ``state.classification`` and ``state.flags``.
    """
    item = make_item(**overrides)
    state = TriageState(item=item)
    cls, flags = heuristics.classify(item)
    state.classification = cls
    state.flags = flags
    return state


class FakeCtx:
    """Minimal stand-in for ``WorkflowContext`` — records what a node emits."""

    def __init__(self) -> None:
        self.messages: list[Any] = []
        self.outputs: list[Any] = []
        self.requests: list[Any] = []

    async def send_message(self, message: Any, **_: Any) -> None:
        self.messages.append(message)

    async def yield_output(self, message: Any, **_: Any) -> None:
        self.outputs.append(message)

    async def request_info(self, request_data: Any = None, response_type: Any = None, **_: Any) -> None:
        self.requests.append(request_data)


def run_node(node: Any, message: Any) -> FakeCtx:
    """Invoke a single executor's handler on ``message`` and return the context."""
    ctx = FakeCtx()
    asyncio.run(node.run(message, ctx))
    return ctx


def emitted(ctx: FakeCtx) -> TriageState:
    """The (single) state a node forwarded."""
    assert ctx.messages, "node emitted no message"
    return ctx.messages[-1]


# ── end-to-end drivers ───────────────────────────────────────────────────────


def triage(request: TriageRequest) -> TriageState:
    """Run the workflow to completion (or to its first human-gate pause)."""

    async def _go() -> TriageState:
        wf = build_workflow()
        result = await wf.run(request)
        reqs = result.get_request_info_events()
        if reqs:
            return reqs[0].data
        return result.get_outputs()[0]

    return asyncio.run(_go())


def triage_meta(**overrides: Any) -> TriageState:
    """Run the workflow from flat intake-field overrides + the shared PDF."""
    return triage(make_request(**overrides))


def triage_and_resume(decision: str, note: str | None = None, **overrides: Any) -> TriageState:
    """Run to the human gate, then resume with a reviewer ``decision``."""

    async def _go() -> TriageState:
        wf = build_workflow()
        result = await wf.run(make_request(**overrides))
        reqs = result.get_request_info_events()
        assert reqs, "expected a human-gate interrupt to resume"
        resumed = await wf.run(
            responses={reqs[0].request_id: HumanDecision(decision=decision, note=note)}
        )
        outputs = resumed.get_outputs()
        assert outputs, "resume produced no terminal output"
        return outputs[0]

    return asyncio.run(_go())
