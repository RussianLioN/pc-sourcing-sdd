# Plan 1.0.0

1. Freeze additive spec, task ownership and acceptance cases before implementation.
2. New durable_jobs.py: SQLite jobs/sources/history/current, process lock, fencing
leases, fsynced content-addressed receipts, integrity and explicit expiry recovery.
3. New durable_cli.py: synthetic fixture execution only; no live imports/calls.
4. Backup/restore SQLite and referenced evidence into immutable manifest-bearing
folders; CLI reports preserve synthetic marker, unknowns and source gaps.
5. Test write-boundary SIGKILL recovery, concurrency, dedup, budget/source stop,
backup tamper and subprocess CLI e2e. Scope compares every baseline byte.
6. Pin exact commit; full quality and Spec Kit workflow; publish only feature branch
and handoff evidence. Parent provides independent read-only review.

Python 3.13.3 / SQLite stdlib; no dependency, protected file or configuration changes.
One writer; no spawned agents. Advisory root locks require cooperating application
processes on a filesystem supporting flock and atomic rename. This is an explicit
operational assumption, not a guarantee across arbitrary filesystems/distributed hosts.
