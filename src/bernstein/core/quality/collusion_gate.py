"""Cross-task collusion gate: the merge-admission stage (#5398).

The per-task gate pipeline evaluates one task's changed files at a time;
two tasks can jointly achieve what each alone is blocked for. This module
is the admission-time counterpart: it takes the candidate set's effect
footprints, evaluates the collusion invariants over dependent pairs, and
returns the outcome as a first-class :class:`GateResult` — same closed
status set, same ``blocked`` semantics, same :class:`VerificationScope`
attestation vocabulary as every other gate — plus the two receipt-facing
projections the merge admission path consumes:

- :meth:`CrossTaskAdmission.to_receipt_scope` — the merge-receipt
  ``VerificationScope`` (``checked`` paths in the receipt's coverage
  vocabulary) folded into the signed coverage sets;
- :meth:`CrossTaskAdmission.receipt_section` — the ``collusion`` record
  bound into the signed preimage at schema v3 (flags naming the invariant
  and both tasks).

Status mapping follows the pipeline's honesty rules (``GateStatus`` /
``INCONCLUSIVE_REASONS``):

- flags present -> ``"fail"``, ``blocked=True`` (required gate).
- every candidate task void (no footprints recorded at all) ->
  ``"inconclusive"`` / ``"evidence-missing"``, ``blocked=True``: the gate
  cannot honestly claim "pass" over evidence it does not have.
- otherwise -> ``"pass"``. Candidates with no footprints alongside
  evidenced ones downgrade the scope to ``confidence="partial"`` and are
  named in ``cannot_check`` — the claim matches what was examined.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from bernstein.core.lineage.dependency import TaskEffects, detect_dependencies
from bernstein.core.quality.collusion import CollusionVerdict, cross_task_check
from bernstein.core.quality.gate_pipeline import (
    GateResult,
    GateStatus,
    VerificationScope,
)
from bernstein.core.quality.merge_receipt import (
    DECISION_ADMIT,
    DECISION_REFUSE,
)
from bernstein.core.quality.merge_receipt import (
    VerificationScope as ReceiptVerificationScope,
)

GATE_NAME = "cross_task_collusion"
#: Oracle kind in the merge receipt's coverage vocabulary.
RECEIPT_ORACLE_KIND = "cross_task_collusion"
#: Oracle identity in the gate-scope attestation vocabulary.
ORACLE_ID = "bernstein.core.quality.collusion"


def _is_void(effects: TaskEffects) -> bool:
    """True when nothing at all is recorded for the candidate."""
    return not effects.facts and not effects.writes and not effects.reads


def _void_tasks(effects: list[TaskEffects]) -> tuple[str, ...]:
    return tuple(e.task_id for e in effects if _is_void(e))


def admission_decision(admission: CrossTaskAdmission) -> str:
    """Map the gate outcome onto the receipt's decision vocabulary.

    The receipt's ``decision`` is a pure function of hashed inputs; this
    mapping is the only bridge between the cross-task gate and
    ``DECISION_REFUSE`` — an advisory can never undo it.
    """
    return DECISION_ADMIT if admission.admitted else DECISION_REFUSE


@dataclass(frozen=True)
class CrossTaskAdmission:
    """Outcome of the cross-task stage at merge admission (#5398).

    ``admitted`` is the block decision. The receipt-facing projections are
    derived, never stored: the caller passes them to
    ``emit_merge_receipt``.
    """

    gate_result: GateResult
    verdict: CollusionVerdict
    candidate_effects: tuple[TaskEffects, ...] = ()

    @property
    def admitted(self) -> bool:
        return not self.gate_result.blocked

    def receipt_section(self) -> dict[str, Any]:
        """The ``collusion`` record bound into the signed receipt preimage.

        Names every flag's invariant and both tasks, so an auditor reading
        the receipt alone can act on or appeal the refusal.
        """
        scope = self.gate_result.scope
        return {
            "check": "cross-task-collusion",
            "ran": True,
            "gate": self.gate_result.name,
            "gate_status": self.gate_result.status,
            "reason": self.gate_result.reason,
            "admitted": self.admitted,
            "checked_pairs": self.gate_result.metadata["checked_pairs"],
            "coupled_pairs": self.gate_result.metadata["coupled_pairs"],
            "void_tasks": list(self.gate_result.metadata["void_tasks"]),
            "flags": list(self.gate_result.metadata["flags"]),
            "scope_confidence": scope.confidence if scope else None,
        }

    def to_receipt_scope(self) -> ReceiptVerificationScope:
        """The check as a merge-receipt coverage scope.

        ``checked`` is the union of evidenced candidates' touched paths —
        the paths the check actually examined — folded into the receipt's
        ``verified`` set and bound by ``coverage_set_hash``. Void tasks
        contribute nothing here (their paths are unknown — that is what
        void means); they are named in the collusion record instead.
        """
        evidenced = [e for e in self.candidate_effects if not _is_void(e)]
        checked = tuple(sorted({p for e in evidenced for p in e.touched_paths()}))
        return ReceiptVerificationScope(
            oracle=RECEIPT_ORACLE_KIND,
            checked=checked,
            skipped=(),
        )


def run_cross_task_gate(candidate_effects: list[TaskEffects]) -> CrossTaskAdmission:
    started = time.perf_counter()
    verdict = cross_task_check(candidate_effects)
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))

    dependent = detect_dependencies(candidate_effects)
    flags = [f.to_dict() for f in verdict.flags]
    void = _void_tasks(candidate_effects)
    all_void = bool(candidate_effects) and len(void) == len(candidate_effects)

    if flags:
        status: GateStatus = "fail"
        blocked = True
        pairs = "; ".join(
            f"{f['invariant']} ({f['task_a']}+{f['task_b']})" for f in flags
        )
        details = f"{len(flags)} cross-task collusion flag(s): {pairs}"
    elif all_void:
        status = "inconclusive"
        blocked = True
        details = (
            "no candidate task has recorded effect footprints; the "
            "cross-task check cannot honestly evaluate admission"
        )
    else:
        status = "pass"
        blocked = False
        details = (
            f"no collusion across {len(candidate_effects)} candidate "
            f"task(s); {len(dependent)} dependent pair(s) checked"
        )

    gate = GateResult(
        name=GATE_NAME,
        status=status,
        required=True,
        blocked=blocked,
        cached=False,
        duration_ms=duration_ms,
        details=details[:2000],
        metadata={
            "flags": flags,
            "checked_pairs": verdict.checked_pairs,
            "coupled_pairs": len(dependent),
            "void_tasks": list(void),
        },
        reason="evidence-missing" if status == "inconclusive" else None,
        scope=VerificationScope(
            oracle_id=ORACLE_ID,
            kind=GATE_NAME,
            checked=tuple(
                sorted("+".join(sorted((a.task_id, b.task_id))) for a, b in dependent)
            ),
            cannot_check=tuple(f"{t} (no effect footprints recorded)" for t in void),
            confidence="partial" if void else "high",
        ),
    )
    return CrossTaskAdmission(
        gate_result=gate,
        verdict=verdict,
        candidate_effects=tuple(candidate_effects),
    )
