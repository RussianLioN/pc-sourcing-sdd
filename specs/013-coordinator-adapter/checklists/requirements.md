# Requirements Checklist — One Explicit Coordinator Operation

Draft contract reviewed against the supplied bounded proposal; implementation/activation acceptance is separate.

- [x] Bounded four known operations, exactly one per call
- [x] Local proposals never grant authority
- [x] External caller/executor trust assumption explicit
- [x] Complete tuple, closure and active anchor checks
- [x] CAS/one-use grant/interruption semantics
- [x] Raw new result and synthetic distinction
- [x] Source restrictions and audit preservation
- [x] No new credentials/security/network/infrastructure
- [x] Simulated tests do not claim actual channel authentication
- [x] Independent review and separate verified start remain gates
