---
category: bugfix
title: "Bound audit chain lock wait to prevent 30s orchestrator shutdown hang"
---

The intent-capsule sealing path during `Orchestrator.run()` shutdown previously used an unbounded `fcntl.flock(LOCK_EX)` call. On parallel CI runners contending for the same file lock, this caused a ~30-second indefinite hang. The lock acquisition in `audit.py` now uses a bounded 5-second wait with `LOCK_NB` and raises `LockTimeout` instead of blocking forever, which the orchestrator catches and logs gracefully.

Closes #4729