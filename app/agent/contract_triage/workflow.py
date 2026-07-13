"""Assemble the triage workflow graph — a 1:1 wiring of docs/agent-graph.mmd.

Solid edges = deterministic transitions; ``add_switch_case_edge_group`` = the
diamond routers (branch on ``state.route``); ``add_fan_out_edges`` /
``add_fan_in_edges`` = the validator fan-out → gather; the human_gate is a
re-entrant ``request_info`` interrupt reachable from every escalation point.
"""

from __future__ import annotations

from agent_framework import Case, Default, Workflow, WorkflowBuilder

from . import executors as X


def build_workflow() -> Workflow:
    # ── nodes ────────────────────────────────────────────────────────────────
    ingest = X.Ingest(id="ingest")
    classify = X.Classify(id="classify")
    intake_gate = X.IntakeGate(id="intake_gate")
    triage = X.TriageRouter(id="triage")
    cheap_guard = X.CheapGuard(id="cheap_guard")
    guard_check = X.GuardCheck(id="guard_check")
    fanout = X.FanOut(id="fanout")
    dpa = X.ValidatorDPA(id="dpa")
    statutory = X.ValidatorStatutory(id="statutory")
    finance = X.ValidatorFinance(id="finance")
    gather = X.Gather(id="gather")
    gate_outcome = X.GateOutcome(id="gate_outcome")
    negotiability = X.Negotiability(id="negotiability")
    gap_analysis = X.GapAnalysis(id="gap_analysis")
    gap_check = X.GapCheck(id="gap_check")
    map_redline = X.MapRedline(id="map_redline")
    disposition = X.Disposition(id="disposition")
    hold = X.Hold(id="hold")
    fallback = X.Fallback(id="fallback")
    strike = X.Strike(id="strike")
    loop_control = X.LoopControl(id="loop_control")
    approval = X.Approval(id="approval")
    execute = X.Execute(id="execute")
    side_effects = X.SideEffects(id="side_effects")
    human_gate = X.HumanGate(id="human_gate")
    declined = X.Declined(id="declined")
    escalated = X.Escalated(id="escalated")

    b = WorkflowBuilder(start_executor=ingest, max_iterations=50,
                        name="Contract Triage", description="Northgate contract-review decision graph",
                        output_from=[side_effects, declined, escalated])

    # ── intake & classification ──────────────────────────────────────────────
    b.add_edge(ingest, classify)
    b.add_edge(classify, intake_gate)
    b.add_switch_case_edge_group(intake_gate, [
        Case(lambda s: s.route in ("more_info", "blocked"), human_gate),
        Default(triage),
    ])

    # ── fast path ─────────────────────────────────────────────────────────────
    b.add_switch_case_edge_group(triage, [
        Case(lambda s: s.route == "guard", cheap_guard),
        Default(fanout),
    ])
    b.add_edge(cheap_guard, guard_check)
    b.add_switch_case_edge_group(guard_check, [
        Case(lambda s: s.route == "approve", approval),
        Default(fanout),
    ])

    # ── policy gates: fan-out → gather ────────────────────────────────────────
    b.add_fan_out_edges(fanout, [dpa, statutory, finance])
    b.add_fan_in_edges([dpa, statutory, finance], gather)
    b.add_edge(gather, gate_outcome)
    b.add_switch_case_edge_group(gate_outcome, [
        Case(lambda s: s.route == "blocked", human_gate),
        Default(negotiability),
    ])

    # ── negotiability fork ────────────────────────────────────────────────────
    b.add_switch_case_edge_group(negotiability, [
        Case(lambda s: s.route == "nonneg", gap_analysis),
        Default(map_redline),
    ])
    b.add_edge(gap_analysis, gap_check)
    b.add_switch_case_edge_group(gap_check, [
        Case(lambda s: s.route == "business_decision", human_gate),
        Default(approval),
    ])

    # ── redline loop (bounded) ────────────────────────────────────────────────
    b.add_edge(map_redline, disposition)
    b.add_switch_case_edge_group(disposition, [
        Case(lambda s: s.route == "escalate", human_gate),
        Case(lambda s: s.route == "fallback", fallback),
        Case(lambda s: s.route == "strike", strike),
        Default(hold),  # 'hold'
    ])
    b.add_edge(hold, loop_control)
    b.add_edge(fallback, loop_control)
    b.add_edge(strike, loop_control)
    b.add_switch_case_edge_group(loop_control, [
        Case(lambda s: s.route == "resolved", approval),
        Case(lambda s: s.route == "maxed", human_gate),
        Default(map_redline),
    ])

    # ── approval & side-effects ───────────────────────────────────────────────
    b.add_edge(approval, execute)
    b.add_edge(execute, side_effects)

    # ── human-in-the-loop resume routing ─────────────────────────────────────
    b.add_switch_case_edge_group(human_gate, [
        Case(lambda s: s.route == "resolved", approval),
        Case(lambda s: s.route == "declined", declined),
        Default(escalated),  # 'escalated'
    ])

    return b.build()
