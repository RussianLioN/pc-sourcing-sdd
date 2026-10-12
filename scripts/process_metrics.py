"""Reproducible public process metrics; unknown telemetry stays unknown."""

import argparse
import json
from datetime import UTC, datetime

from reviewed_lessons import Rejected, checked, identifier, read

FIELDS = {
    "event_id",
    "event_type",
    "at",
    "incident_id",
    "root_cause",
    "actor_type",
    "eligible",
    "reproducible",
    "evidence",
}
KINDS = {
    "local_attempt",
    "independent_rejection",
    "submission",
    "acceptance",
    "intervention",
    "replay",
}


def timestamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise Rejected("explicit UTC event time required")
    return parsed


def summarize(events, cohort, taxonomy):
    if not isinstance(cohort, list) or len(set(cohort)) != len(cohort):
        raise Rejected("frozen unique cohort required")
    if not isinstance(taxonomy, list) or len(set(taxonomy)) != len(taxonomy):
        raise Rejected("frozen unique taxonomy required")
    seen, counts, first, accepted = set(), {}, {}, {}
    local = independent = human = eligible = replayed = blocked = 0
    for event in events:
        checked(event, FIELDS)
        identifier(event["event_id"])
        if event["event_id"] in seen:
            raise Rejected("duplicate process event")
        seen.add(event["event_id"])
        if event["incident_id"] not in cohort or event["root_cause"] not in taxonomy:
            raise Rejected("event outside frozen baseline")
        if event["actor_type"] not in {"human", "coordinator_automatic", "writer", "reviewer"}:
            raise Rejected("unknown actor")
        if event["event_type"] not in KINDS or not event["evidence"]:
            raise Rejected("event type/evidence required")
        if (
            type(event["eligible"]) is not bool
            or event["reproducible"] is not None
            and type(event["reproducible"]) is not bool
        ):
            raise Rejected("typed eligibility/reproducibility")
        at = timestamp(event["at"])
        key = event["incident_id"]
        counts.setdefault(event["root_cause"], set()).add(key)
        local += event["event_type"] == "local_attempt"
        independent += event["event_type"] == "independent_rejection"
        human += event["event_type"] == "intervention" and event["actor_type"] == "human"
        if event["event_type"] == "submission":
            first[key] = (
                min(first.get(key, at), at)
                if at is not None and first.get(key, at) is not None
                else None
            )
        if event["event_type"] == "acceptance":
            accepted[key] = (
                min(accepted.get(key, at), at)
                if at is not None and accepted.get(key, at) is not None
                else None
            )
        if event["event_type"] == "replay":
            eligible += event["eligible"]
            replayed += event["eligible"] and event["reproducible"] is True
            blocked += not event["eligible"] or event["reproducible"] is None
    durations = {}
    for key in sorted(cohort):
        start, end = first.get(key), accepted.get(key)
        if start is not None and end is not None and end < start:
            raise Rejected("acceptance before first submission")
        durations[key] = (
            (end - start).total_seconds() if start is not None and end is not None else None
        )
    return {
        "cohort": sorted(cohort),
        "taxonomy": sorted(taxonomy),
        "root_cause_incidents": {k: len(v) for k, v in sorted(counts.items())},
        "local_attempts": local,
        "independent_repair_rounds": independent,
        "direct_human_interventions": human,
        "replay_eligible": eligible,
        "replay_pass": replayed,
        "replay_blocked": blocked,
        "acceptance_seconds": durations,
        "cost": None,
        "active_user_time": None,
        "improvement_claim": None,
        "unknown_reason": "no measured usage/activity telemetry",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    args = parser.parse_args()
    value = read(args.input)
    print(json.dumps(summarize(value["events"], value["cohort"], value["taxonomy"])))


if __name__ == "__main__":
    main()
