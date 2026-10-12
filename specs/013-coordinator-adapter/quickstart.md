# Validation and Host Handoff

Status: mechanism implemented and tested with a simulated host; independent adapter review and real platform call/start/activation remain pending.

The local CLI exposes status only (`.venv/bin/python scripts/coordinator_adapter.py status`); `Adapter.proposal` prepares bounded untrusted data. It accepts no anchor/grant/independent flags and never switches an active pointer. A missing coordinator host returns BLOCKED/OFF.

The library handler is intended ONLY for the existing authenticated coordinator-controlled executor. The host retains genuine verdict/hash anchors outside writer control, verifies the accepted execution image before loading it, provides one-operation adjudication and validates the visible receipt before external anchor advance. Passing an arbitrary Python provider in the writer process does not authenticate it and cannot be presented as a real invocation.

Synthetic host tests cover exact tuples, one-use grant, CAS, interruption, raw Git result and immutable source inventory. Real end-to-end acceptance additionally requires independently accepted adapter SHA, actual existing channel, a genuine independently accepted new non-synthetic result, and a separate explicit coordinator start. No local JSON/chmod/token substitute is implemented. If this host binding is unavailable, keep learning OFF and resume accepted T016 product work after review.

Quality exit 0/native completed mean code/data checks completed. Inspect checks_status and toolchain_pins_status independently: CHECKS_PASS_PINS_BLOCKED and reproducibility_status BLOCKED are not full PASS. Existing Codex/UV mismatches remain explicit; no pin update/download is authorized by the helper.
