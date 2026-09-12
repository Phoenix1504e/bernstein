## Cross-task collusion detection in benchmark evaluation

Benchmark evaluation suites now include cross-task collusion detection: paired
fixtures where each half passes its gate alone but the pair jointly violates a
stated invariant. A CrossTaskCollusionDetector checks lineage dependencies
(task B reads what task A wrote) and runs invariant checks over the combined
effect of both tasks.

Five colluding pairs (permissive test injection, dangerous shell split, config
permission widening, gate disable, sensitive file access) and five benign pairs
are shipped as fixtures under 	ests/eval/cases/collusion/. Each flag names the
violated invariant and both task IDs (#5398).
