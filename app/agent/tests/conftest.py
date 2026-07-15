"""Test-suite bootstrap.

Two jobs:

1. Make the test-support modules importable regardless of pytest's rootdir.
2. Swap the LLM brain for a deterministic offline double. The shipped agent is
   fully LLM-first (``contract_triage.agents`` calls the model for every
   classification, gate and redline decision); to exercise the graph — routers,
   fan-out, human-gate, service — without live API calls, an autouse fixture
   monkeypatches those decision functions onto ``_fake_brain`` and disables the
   chat client so the reviewer explanation degrades to its template.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _fake_brain as fake_brain  # noqa: E402  (after sys.path shim)
from contract_triage import agents  # noqa: E402


@pytest.fixture(autouse=True)
def offline_brain(monkeypatch):
    """Route every agent decision through the deterministic test double."""

    # The app ships an empty inbox by default; the suite exercises the seeded
    # demo contracts, so opt seeding back on for tests that build a TriageService.
    monkeypatch.setenv("SEED_EXAMPLES", "1")

    # Deterministic confidence for the offline brain — real runs get the value
    # from the model's structured output; the test double just picks a plausible
    # mid-high number so ``finalize`` still averages a real score.
    _confidence = lambda stage: agents.ConfidenceScore(stage=stage, score=8)

    async def classify_llm(item, inherited, prior_ids):
        cls, flags = fake_brain.classify(item)
        return cls, flags, agents.IntakeReview(), _confidence("classify")

    async def gate_llm(state, gate):
        check = fake_brain.gate_for(state, gate)
        return check, (_confidence(f"gate_{gate.value}") if check else None)

    async def redlines_llm(state):
        return fake_brain.extract_redlines(state), _confidence("redlines")

    monkeypatch.setattr(agents, "classify_llm", classify_llm)
    monkeypatch.setattr(agents, "gate_llm", gate_llm)
    monkeypatch.setattr(agents, "redlines_llm", redlines_llm)
    # No chat client → agents.explain() returns its deterministic template, and a
    # real key in the environment can't leak a live call into the tests.
    # (monkeypatch restores the original lru_cached function at teardown.)
    agents.get_chat_client.cache_clear()
    monkeypatch.setattr(agents, "get_chat_client", lambda: None)
