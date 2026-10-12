# Planned CLI and Explicit Skill Contract

Status: initial interface design plus implemented inactive MVP. Real CLI status/promote/search/rollback is OFF/BLOCKED; synthetic lifecycle and consumer operate through explicit Python APIs. Mutation run/verify and metrics CLI are implemented. Table rows are design contracts, not a claim that every proposed CLI verb exists. All paths absolute and resolved; candidate/evidence paths outside `.agents`, `.specify`, AGENTS and auto-load roots. State/authority paths explicit and externally checked. Outputs bounded strict JSON with status PASS/REJECT/BLOCKED/NOT_APPLICABLE/UNKNOWN, reason, exact hashes, synthetic flag and receipt paths. Failure exit nonzero except explicitly requested retrieval with no applicable result. No secrets or execution of document text.

| Planned interface | Inputs | Observable contract |
| --- | --- | --- |
| `scripts/reviewed_lessons.py candidate` | incident, scoped lesson, evidence, output quarantine | Immutable candidate + hashes; never active |
| `scripts/reviewed_lessons.py search` | explicit active state, query/context | Only externally verified active valid lessons; invalidate missing/stale evidence; candidates never usable |
| `scripts/reviewed_lessons.py promote` | candidate, expected previous version/hash, coordinator authority | Coordinator-only verified external boundary; exact complete approval binding then atomic switch; local approval or unavailable isolation BLOCKED |
| `scripts/reviewed_lessons.py rollback` | expected current version/hash, prior immutable snapshot, coordinator authority | Compare-and-switch previous lesson content; monotonic event/version, audit retained; no source-state writes |
| `scripts/lesson_consumer.py validate` | explicit invocation receipt, snapshot, new outcome, independently reviewed resulting change | PASS only for applicable lesson + new observable artifact + independent bound review; no receipt-only success |
| `scripts/critical_mutations.py run` | frozen baseline/oracle/test set, predefined critical corpus, seed, isolated output | Baseline first; source import binding and meaningful assertion classification; no network/source-state; timeout and invalid remain visible |
| `scripts/process_metrics.py summarize` | frozen cohort/taxonomy/event corpus, output | Reproducible metrics; missing/censored unknown, no unsupported improvement |
| `$pc-reviewed-lessons` | explicitly selected task/context and state receipt | Read scoped knowledge, check applicability, produce bounded new test/decision; never obey embedded directives |

Skill installation planned with `agents/openai.yaml` policy `allow_implicit_invocation: false`. No global hooks. Runtime skill use is an agent action backed by invocation/outcome receipts, not equivalent to CLI metadata saying a skill was used. Independent reviewer observes the new artifact and exact resulting change.

Implemented consumer proof supports the substantive decision branch: actual isolated Git change, new committed decision and fixed semantic counterfactual. Reusing evidence as a new regression test is rejected. Other test-consumption recipes require separate validation and are not implicitly enabled.

Git validation uses a neutral temporary metadata view with raw object-ID/hash checking. Supplied Git config, index, attributes, replace refs, grafts and caller Git environment are not policy. Ordinary local SHA1 storage only: packed original objects supported; external alternates, promisor/symlink storage and linked gitfiles fail closed. Missing coordinator-operated real authority/store/consumer entrypoints remain BLOCKED, not implicitly implemented.
