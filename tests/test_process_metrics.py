import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from process_metrics import summarize  # noqa: E402
from reviewed_lessons import Rejected  # noqa: E402


def event(id, kind, actor="writer", at=None, eligible=True, reproducible=None):
    return {
        "event_id": id,
        "event_type": kind,
        "at": at,
        "incident_id": "incident",
        "root_cause": "hash_binding",
        "actor_type": actor,
        "eligible": eligible,
        "reproducible": reproducible,
        "evidence": ["public-Git-reference"],
    }


def test_metrics_replay_unknown_censored_and_interventions():
    events = [
        event("a", "local_attempt"),
        event("b", "independent_rejection", "reviewer"),
        event("c", "intervention", "coordinator_automatic"),
        event("d", "intervention", "human"),
        event("e", "replay", reproducible=True),
        event("f", "replay", eligible=False),
    ]
    one = summarize(events, ["incident"], ["hash_binding"])
    assert summarize(events[::-1], ["incident"], ["hash_binding"]) == one
    assert one["local_attempts"] == one["independent_repair_rounds"] == 1
    assert one["direct_human_interventions"] == 1
    assert one["acceptance_seconds"] == {"incident": None}
    assert one["cost"] is one["active_user_time"] is one["improvement_claim"] is None
    assert one["replay_eligible"] == one["replay_pass"] == one["replay_blocked"] == 1


def test_elapsed_and_invalid_chronology():
    events = [
        event("a", "submission", at="2026-10-12T12:00:00Z"),
        event("b", "acceptance", at="2026-10-12T12:01:00Z"),
    ]
    assert summarize(events, ["incident"], ["hash_binding"])["acceptance_seconds"]["incident"] == 60
    with pytest.raises(Rejected):
        summarize(events + events[:1], ["incident"], ["hash_binding"])
    with pytest.raises(Rejected):
        summarize(events, [], ["hash_binding"])
    with pytest.raises(Rejected):
        summarize(
            [events[0] | {"at": "2026-10-12T12:02:00Z"}, events[1]], ["incident"], ["hash_binding"]
        )


def test_censored_submission_order_is_reproducible():
    events = [
        event("a", "submission"),
        event("b", "submission", at="2026-10-12T12:00:00Z"),
        event("c", "acceptance", at="2026-10-12T12:01:00Z"),
    ]
    assert summarize(events, ["incident"], ["hash_binding"]) == summarize(
        events[::-1], ["incident"], ["hash_binding"]
    )
    assert (
        summarize(events, ["incident"], ["hash_binding"])["acceptance_seconds"]["incident"] is None
    )
