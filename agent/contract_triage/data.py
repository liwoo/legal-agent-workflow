"""The raw inbox the triage workflow consumes.

Mirrors ``../../contract-inbox.md`` (10 items that landed 10–12 July 2026) and a
small index of inherited flags from prior contracts (e.g. the DPIA-required flag
on CR-2026-046 that CR-2026-052 inherits). Kept as code so the backend is
self-contained and runs with no filesystem coupling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Counterparty, InboxItem

# Inherited flags keyed by prior contract id — consulted when a new item names a
# prior_contract in its chain (the "prior_file? blocking flag?" intake router).
PRIOR_FLAGS: dict[str, list[str]] = {
    "CR-2026-046": ["dpia_required_before_order_form"],  # blocking precondition
    "CR-2026-015": ["etf_mechanics_month_12"],  # negotiated termination/ETF terms
    "CR-2025-008": ["framework_ip_clause"],
    "CR-2025-011": ["dpa_amended_cr_2025_022"],
}


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


INBOX: list[InboxItem] = [
    InboxItem(
        id="CR-2026-050",
        received_at=_dt("2026-07-10T09:14"),
        sender_role="AE (sales)",
        counterparty=Counterparty(name="Kestrel Dynamics Ltd", sector="drone inspection"),
        what_arrived="Counterparty's own NDA paper (4 pages, Word), unsigned.",
        sender_ask="Can we just sign their version? They said their legal won't look at ours.",
    ),
    InboxItem(
        id="CR-2026-051",
        received_at=_dt("2026-07-10T11:47"),
        sender_role="AE (sales)",
        counterparty=Counterparty(name="Wychwood Analytics Ltd"),
        what_arrived=(
            "Our own order form + MSA v4 returned with tracked changes from the "
            "prospect's solicitor. Redlines on liability, payment terms and indemnity. "
            "40 seats, Professional tier."
        ),
        sender_ask="They want to close this month — how bad are the changes?",
    ),
    InboxItem(
        id="CR-2026-052",
        received_at=_dt("2026-07-10T15:02"),
        sender_role="AE (sales)",
        counterparty=Counterparty(name="Ilex Biometrics Ltd", sector="biometrics"),
        what_arrived=(
            "Signed-NDA prospect requesting an order form — 25 seats, Professional tier. "
            "Would sync 'employee verification event data' into the platform."
        ),
        sender_ask="Standard order form please, they're ready to go.",
    ),
    InboxItem(
        id="CR-2026-053",
        received_at=_dt("2026-07-10T16:30"),
        sender_role="Head of Engineering",
        counterparty=Counterparty(name="Applause QA Collective Ltd"),
        what_arrived=(
            "Supplier's renewal notice for the QA services agreement proposing a 9% "
            "uplift and a new clause pack ('updated standard terms v2.3', unread). "
            "Current term expires 2026-08-31."
        ),
        sender_ask="Fine to renew? We're happy with them.",
    ),
    InboxItem(
        id="CR-2026-054",
        received_at=_dt("2026-07-11T08:55"),
        sender_role="CEO",
        counterparty=Counterparty(name="Thornbury Rail Consortium", sector="rail infrastructure"),
        what_arrived=(
            "Consortium's NDA paper (11 pages, PDF) covering multi-party disclosure among "
            "four consortium members plus Northgate."
        ),
        sender_ask="Need this signed before Tuesday's consortium call.",
    ),
    InboxItem(
        id="CR-2026-055",
        received_at=_dt("2026-07-11T10:20"),
        sender_role="Marketing Director",
        counterparty=Counterparty(name="Kite & Anchor Creative Ltd", sector="creative agency"),
        what_arrived=(
            "Agency's draft SOW under the existing framework: autumn campaign, £21k, "
            "includes a new line item for 'AI-generated imagery' not contemplated by the "
            "framework's IP clause."
        ),
        sender_ask="Same as the last two SOWs, should be quick.",
    ),
    InboxItem(
        id="CR-2026-056",
        received_at=_dt("2026-07-11T14:05"),
        sender_role="Head of RevOps",
        counterparty=Counterparty(name="Loquent AI Ltd", sector="AI meeting transcription"),
        what_arrived=(
            "Vendor's online terms of service (link) + order form (PDF) for an AI "
            "meeting-transcription tool. Terms reference training-data usage rights and "
            "US-hosted processing; no DPA attached."
        ),
        sender_ask="Team is already trialling the free tier — can we get the paid plan approved this week?",
    ),
    InboxItem(
        id="CR-2026-057",
        received_at=_dt("2026-07-11T17:12"),
        sender_role="CSM (customer success)",
        counterparty=Counterparty(name="Ashcombe Retail Group plc", sector="retail"),
        what_arrived=(
            "Renewal paperwork for the 50-seat subscription. Customer returned our renewal "
            "order form with one visible comment bubble on the uplift figure. "
            "Term expires 2026-08-15."
        ),
        sender_ask="Renewal at risk if we can't confirm pricing by end of next week.",
    ),
    InboxItem(
        id="CR-2026-058",
        received_at=_dt("2026-07-12T09:03"),
        sender_role="Bid Manager",
        counterparty=Counterparty(
            name="Oakhampton Council", sector="local government", is_public_body=True
        ),
        what_arrived=(
            "Council's invitation-to-tender pack: mandatory contract terms (38 pages), "
            "a no-negotiation notice, and a compliance questionnaire. Submission deadline 2026-07-31."
        ),
        sender_ask="Please confirm we can accept their terms as-is — tender doesn't allow redlines.",
    ),
    InboxItem(
        id="CR-2026-059",
        received_at=_dt("2026-07-12T10:41"),
        sender_role="CSM (customer success)",
        counterparty=Counterparty(name="Draycott Field Services Ltd"),
        what_arrived=(
            "Customer email (no draft attached) asking to reduce from 60 to 40 seats "
            "mid-term, citing restructuring. Their 24-month order form includes negotiated "
            "termination-for-convenience/ETF mechanics at month 12."
        ),
        sender_ask="What are our options? They're a reference customer.",
    ),
]

# Prior-contract chains referenced by the inbox (drives the "prior file?" router).
PRIOR_CHAINS: dict[str, list[str]] = {
    "CR-2026-052": ["CR-2026-046"],
    "CR-2026-053": ["CR-2026-025"],
    "CR-2026-055": ["CR-2025-008"],
    "CR-2026-057": ["CR-2025-011", "CR-2025-022"],
    "CR-2026-058": ["CR-2026-033"],
    "CR-2026-059": ["CR-2026-015"],
}

_INBOX_BY_ID = {i.id: i for i in INBOX}


def get_inbox() -> list[InboxItem]:
    return list(INBOX)


def get_item(item_id: str) -> InboxItem | None:
    return _INBOX_BY_ID.get(item_id)


def inherited_flags(item_id: str, prior_ids: list[str] | None = None) -> list[str]:
    """Flags a new item inherits from its prior-contract chain.

    ``prior_ids`` overrides the built-in ``PRIOR_CHAINS`` lookup — used when the
    chain comes from an ad-hoc intake (metadata ``related_contracts``) rather
    than the hard-coded inbox.
    """
    chain = prior_ids if prior_ids is not None else PRIOR_CHAINS.get(item_id, [])
    flags: list[str] = []
    for prior in chain:
        flags.extend(PRIOR_FLAGS.get(prior, []))
    return flags


def prior_contracts(item_id: str) -> list[str]:
    return list(PRIOR_CHAINS.get(item_id, []))


def item_from_metadata(metadata: dict[str, Any], pdf_path: str | None = None) -> InboxItem:
    """Build an :class:`InboxItem` from a ``metadata.json`` payload + a PDF path.

    Maps the on-disk intake schema (``test/CR-2026-05N/metadata.json``) onto the
    workflow's entry state: ``summary`` → ``what_arrived``, ``senders_ask`` →
    ``sender_ask``, ``received_from`` → ``sender_role``, and the ``related_-
    contracts`` chain that drives the prior-file blocker. ``pdf_path`` (absolute)
    is stored so the ingest node can read the document via the PDF tool.
    """
    cp = metadata.get("counterparty")
    counterparty = Counterparty(
        name=cp if isinstance(cp, str) else metadata.get("counterparty_name", "Unknown"),
        is_public_body=bool(metadata.get("is_public_body", False)),
        is_regulated=bool(metadata.get("is_regulated", False)),
        sector=metadata.get("sector"),
        jurisdiction=metadata.get("jurisdiction"),
    )
    received = metadata.get("received_at") or metadata.get("date_received")
    received_at = _dt(str(received)) if received else datetime(1970, 1, 1)
    return InboxItem(
        id=metadata.get("id", "AD-HOC"),
        received_at=received_at,
        sender_role=metadata.get("received_from") or metadata.get("sender_role", "unknown"),
        counterparty=counterparty,
        what_arrived=metadata.get("summary") or metadata.get("what_arrived", ""),
        sender_ask=metadata.get("senders_ask") or metadata.get("sender_ask", ""),
        related_contracts=list(metadata.get("related_contracts", []) or []),
        pdf_path=pdf_path,
    )
