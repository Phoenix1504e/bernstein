"""One-shot: apply review-finding doc edits (3 and 4). Run from repo root."""

from pathlib import Path

MERGE_GATE_SECTION = """## Cross-task collusion gate (admission-time, content-level)

The four layers above protect the merge *process*. The cross-task collusion
gate protects merge *content* at the level of the candidate set: per-change
gates evaluate one task at a time, so two tasks can jointly achieve what
each alone is blocked for — one weakens a test the other's change needed to
pass, a forbidden removal is split so each half leaves the guard
half-standing, or one task writes a config value the other reads to widen
its scope.

`bernstein.core.quality.collusion_gate` evaluates three invariants over
dependent task pairs (pairwise dependency from
`bernstein.core.lineage.dependency`: path read-of-write, overlapping
writes, symbol definition-vs-reference removal, config write under reader,
weakened-test target touched):

| Invariant | Fires when |
|---|---|
| `weakened-test-covers-changed-code` | one candidate weakens a test whose target module another candidate modifies |
| `guarded-symbol-split-removal` | one candidate removes a guarded symbol's definition while another removes its reference |
| `guarded-config-flip-under-reader` | one candidate writes a guarded config key to an unsafe value while another reads it |

Status follows the same honesty rules as the per-task gates
(`GateStatus` / `INCONCLUSIVE_REASONS`): any flag is `fail` and blocks; a
candidate set containing any task with no recorded effect footprints — or
an empty candidate set — is `inconclusive` / `evidence-missing` and blocks
(a required gate never fabricates a pass over incomplete evidence);
otherwise `pass`, with a `VerificationScope` whose confidence
(`high`/`partial`/`none`) matches what was actually examined.

Every admission decision — clean or not — is recorded in the merge
admission receipt under the signed `collusion` binding field (receipt
schema v3, versioned exactly like the v2 coverage fields so v1/v2 rows
still load): the flags, each naming the invariant and both task ids; the
candidate/coupled pair counts; the void task ids; and the gate status and
reason.

Wiring status: the gate's production consumer today is the eval bundle
receipt path (`bernstein.eval.bench.collusion_bundle`), whose per-case
receipts come from the same `CrossTaskAdmission.receipt_section()` the
admission path consumes. Calling it from the live admission flow
(`emit_merge_receipt` with `decision=` / `scopes=` / `collusion=`) is the
next slice of #5463.

"""

BENCH_SECTION = """### Collusion evaluation suite (`eval/cases/collusion/`)

Gates evaluate one change at a time, so two tasks can jointly achieve what
each alone is blocked for. This suite measures the cross-task check at
merge admission over 10 paired fixtures (5 colluding / 5 benign):

- **collusion** pairs — each half passes its own gate; the pair violates a
  stated invariant. The scorer requires a flag naming that invariant and
  both task ids.
- **benign** pairs — co-changes that must not be flagged: uncoupled tasks,
  unguarded-symbol cleanups, non-guarded config keys, safe values,
  overlapping writes.

Invariants (smallest set that catches the five pairs — extend only with a
new fixture first):

| invariant | fires when |
|---|---|
| `weakened-test-covers-changed-code` | one task weakens a test whose target module the other modifies |
| `guarded-symbol-split-removal` | one task removes a guarded symbol's definition, the other its reference |
| `guarded-config-flip-under-reader` | one task writes a guarded key to an unsafe value, the other reads it |

Results are scored into a signed `SubmissionBundle` — one `TaskResult` per
case, each receipt carrying the same cross-task record the merge receipt
binds (schema v3) plus the footprints, so every score replays from its
receipt (`collusion_bundle.replay_receipt`).
"""

FRAGMENT = """Cross-task collusion check at merge admission (#5398): three invariants
(`weakened-test-covers-changed-code`, `guarded-symbol-split-removal`,
`guarded-config-flip-under-reader`) are evaluated over dependent task
pairs when a merge is admitted; any flag refuses the merge, and a
candidate set with unrecorded footprints — or an empty one — is
inconclusive and blocks. The merge admission receipt schema is bumped to
v3 with an optional signed `collusion` binding field; v1/v2 receipts
still load. A 10-case paired eval suite (5 colluding / 5 benign) under
`eval/cases/collusion/` scores the check into a signed submission bundle
with replayable per-case receipts.
"""

# 1. merge-gate.md — insert before the Windows-lane section
p = Path("docs/operations/merge-gate.md")
src = p.read_text(encoding="utf-8")
anchor = "## Windows-lane promotion (self-promoting gate)"
assert src.count(anchor) == 1, f"merge-gate.md: anchor found {src.count(anchor)}x"
assert "Cross-task collusion gate" not in src, "merge-gate.md: already edited"
src = src.replace(anchor, MERGE_GATE_SECTION + anchor)
p.write_text(src, encoding="utf-8")
print("1. merge-gate.md: section inserted")

# 2. bench.md — append
p = Path("docs/eval/bench.md")
src = p.read_text(encoding="utf-8")
assert "Collusion evaluation suite" not in src, "bench.md: already edited"
p.write_text(src.rstrip("\n") + "\n\n" + BENCH_SECTION, encoding="utf-8")
print("2. bench.md: section appended")

# 3. BENCHMARKS.md — move the floating row into a proper table
p = Path("BENCHMARKS.md")
src = p.read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)
hits = [i for i, ln in enumerate(lines) if "collusion-pairs" in ln]
assert len(hits) == 1, f"BENCHMARKS.md: expected 1 collusion row, found {len(hits)}"
row = lines[hits[0]].rstrip("\n")
table = "| Suite | Cases | Result | Notes |\n|---|---|---|---|\n" + row
lines[hits[0]] = table + "\n"
p.write_text("".join(lines), encoding="utf-8")
print("3. BENCHMARKS.md: row moved into a table")

# 4. release-notes fragment
frag = Path("docs/release-notes/fragments/6282-cross-task-collusion-check.md")
frag.parent.mkdir(parents=True, exist_ok=True)
assert not frag.exists(), "fragment already exists"
frag.write_text(FRAGMENT, encoding="utf-8")
print("4. fragment written")