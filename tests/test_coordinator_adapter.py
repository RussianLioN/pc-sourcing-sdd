import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]
from coordinator_adapter import Adapter, Replica, source_inventory  # noqa: E402
from lesson_consumer import new_decision  # noqa: E402
from reviewed_lessons import Rejected, digest, encoded  # noqa: E402
from test_reviewed_lessons import activate, fixture  # noqa: E402

from pc_sourcing.witness_transfer import backup, restore  # noqa: E402


class SimulatedHost:
    """Test-only externally retaining simulation; NOT a genuine platform channel."""

    def __init__(self, proposal, adapter):
        self.adapter = adapter
        self.anchor = {
            "review": {
                "provenance": "TEST_ONLY_REVIEW",
                "package_id": "test-fixture",
                "package_version": 1,
                "package_hash": "a" * 64,
                "purpose": "T018_one_operation",
                "verdict": "PASS",
            },
            "version": proposal["expected_version"],
            "hash": proposal["expected_hash"],
            "explicit_start": True,
            **{
                key: copy.deepcopy(proposal[key])
                for key in [
                    "synthetic",
                    "closure",
                    "source_inventory",
                    "replica_path",
                    "context",
                    "lesson_hash",
                    "result_hash",
                    "consumer_snapshot_hash",
                ]
            },
        }
        self.used = set()
        self.accepted_review = copy.deepcopy(self.anchor["review"])
        self.pending = None
        self.on_grant = None
        self.bad_ack = False

    def read_anchor(self):
        return copy.deepcopy(self.anchor)

    def adjudicate_once(self, proposal):
        if self.pending or proposal["request"]["request_id"] in self.used:
            raise Rejected("external grant pending/replayed")
        if encoded(self.anchor["review"]) != encoded(self.accepted_review):
            raise Rejected("externally retained provenance mismatch")
        self.pending = {
            "grant_id": proposal["request"]["request_id"],
            "proposal_hash": proposal["proposal_hash"],
            "operation": proposal["operation"],
            "request_id": proposal["request"]["request_id"],
            "version": proposal["expected_version"],
            "hash": proposal["expected_hash"],
            "anchor_hash": digest(self.anchor),
        }
        self.used.add(proposal["request"]["request_id"])
        if self.on_grant:
            self.on_grant()
        return copy.deepcopy(self.pending)

    def commit_verified_result(self, grant, receipt):
        # Independent test-host inspection, not trust in a writer receipt flag.
        current = self.adapter.replica.current()
        assert (
            current["version"] == receipt["version"]
            and current["snapshot_sha256"] == receipt["hash"]
        )
        assert (
            source_inventory(self.adapter.source_path)
            == self.anchor["source_inventory"]
            == receipt["source_inventory"]
        )
        assert self.pending == grant
        if self.bad_ack:
            return {"writer_local_PASS": True}
        self.anchor["version"], self.anchor["hash"] = receipt["version"], receipt["hash"]
        self.pending = None
        return {
            "grant_id": grant["grant_id"],
            "receipt_hash": digest(receipt),
            "version": receipt["version"],
            "hash": receipt["hash"],
        }


def setup(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    store, lesson, approval = fixture(knowledge)
    activate(store, lesson, approval)
    receipt = new_decision(store, "declarations", tmp_path / "new-result.json")
    source = tmp_path / "source-copy"
    backup(ROOT / "artifacts/source-state", tmp_path / "source-snapshot")
    restore(tmp_path / "source-snapshot", source)
    replica = Replica(tmp_path / "replica", True)
    initial = replica.bootstrap_untrusted()
    (replica.root / "incidents/conflict_incident.json").write_bytes(
        (store.root / "incidents/conflict_incident.json").read_bytes()
    )
    lesson_path, result_path = tmp_path / "lesson.json", tmp_path / "result-receipt.json"
    lesson_path.write_bytes(encoded(lesson))
    result_path.write_bytes(encoded(receipt))
    adapter = Adapter(replica.root, source, True)
    request = {
        "request_id": "operation1",
        "context": "declarations",
        "lesson_path": str(lesson_path),
        "result_path": str(result_path),
    }
    payload = encoded(request)
    proposal = adapter.proposal("promote", payload, 0, initial["snapshot_sha256"])
    return adapter, request, initial, SimulatedHost(proposal, adapter)


def test_proposal_local_flags_never_authority(tmp_path):
    adapter, request, initial, _host = setup(tmp_path)
    before = (adapter.replica.root / "active.json").read_bytes()
    for host in [None, {"independent": True}, object()]:
        result = adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
        assert result["status"] == "BLOCKED" and result["learning_enabled"] is False
        assert (adapter.replica.root / "active.json").read_bytes() == before
    for extra in [{"anchor": {}}, {"independent": True}, {"explicit_start": True}]:
        with pytest.raises(Rejected):
            adapter.coordinator_once(
                "promote", encoded(request | extra), 0, initial["snapshot_sha256"]
            )
    duplicate = '{"request_id":"a","request_id":"b","context":"declarations"}'
    with pytest.raises(Rejected):
        adapter.proposal("retrieve", duplicate, 0, initial["snapshot_sha256"])


def test_simulated_one_operation_retrieve_and_visible_rollback(tmp_path):
    adapter, request, initial, host = setup(tmp_path)
    source_before = source_inventory(adapter.source_path)
    result = adapter.coordinator_once(
        "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
    )
    assert result["status"] == "SIMULATED_RECEIPT" and not result["learning_enabled"]
    current = adapter.replica.current()
    assert current["version"] == host.anchor["version"] == 1
    retrieval = encoded({"request_id": "retrieve1", "context": "declarations"})
    p = adapter.proposal("retrieve", retrieval, 1, current["snapshot_sha256"])
    host2 = SimulatedHost(p, adapter)
    result2 = adapter.coordinator_once(
        "retrieve", retrieval, 1, current["snapshot_sha256"], host=host2
    )
    assert (
        result2["receipt"]["knowledge_is_untrusted"] and len(result2["receipt"]["knowledge"]) == 1
    )
    rollback = encoded(
        {
            "request_id": "rollback1",
            "context": "declarations",
            "target_hash": initial["snapshot_sha256"],
        }
    )
    host3 = SimulatedHost(
        adapter.proposal("rollback", rollback, 1, current["snapshot_sha256"]), adapter
    )
    before_audit = (adapter.replica.root / "audit.jsonl").read_bytes()
    rolled = adapter.coordinator_once(
        "rollback", rollback, 1, current["snapshot_sha256"], host=host3
    )
    assert rolled["receipt"]["version"] == 2 and adapter.replica.current()["entries"] == []
    assert (adapter.replica.root / "audit.jsonl").read_bytes().startswith(before_audit)
    assert source_inventory(adapter.source_path) == source_before


@pytest.mark.parametrize(
    "key",
    [
        "purpose",
        "provenance",
        "explicit_start",
        "package_hash",
        "package_id",
        "package_version",
        "package_version_bool",
        "valid_wrong_package_hash",
        "closure",
        "lesson_hash",
        "result_hash",
        "context",
        "hash",
    ],
)
def test_external_mismatch_refuses_before_switch(tmp_path, key):
    adapter, request, initial, host = setup(tmp_path)
    if key == "purpose":
        host.anchor["review"]["purpose"] = "T017_inactive"
    elif key == "provenance":
        host.anchor["review"]["provenance"] = "writer-local-json"
    elif key == "package_hash":
        host.anchor["review"]["package_hash"] = "not-a-hash"
    elif key == "package_id":
        host.anchor["review"]["package_id"] = "wrong-package"
    elif key == "package_version":
        host.anchor["review"]["package_version"] = 2
    elif key == "package_version_bool":
        host.anchor["review"]["package_version"] = True
    elif key == "valid_wrong_package_hash":
        host.anchor["review"]["package_hash"] = "b" * 64
    elif key == "explicit_start":
        host.anchor[key] = False
    elif key == "closure":
        host.anchor[key] = host.anchor[key] | {"closure_sha256": "b" * 64}
    else:
        host.anchor[key] = "b" * 64
    before = (adapter.replica.root / "active.json").read_bytes()
    with pytest.raises((Rejected, ValueError)):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    assert (adapter.replica.root / "active.json").read_bytes() == before


@pytest.mark.parametrize("fault", ["before_switch", "after_switch"])
def test_interrupted_grant_not_replayed_and_anchor_divergence(tmp_path, fault):
    adapter, request, initial, host = setup(tmp_path)
    with pytest.raises(Rejected, match="interrupt|diverge"):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host, fault=fault
        )
    assert host.anchor["version"] == 0 and host.pending
    assert adapter.replica.current()["version"] == (0 if fault == "before_switch" else 1)
    with pytest.raises(Rejected, match="pending|replay|stale"):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )


def test_failed_external_anchor_advance_blocks_visible_result(tmp_path):
    adapter, request, initial, host = setup(tmp_path)
    host.bad_ack = True
    with pytest.raises(Rejected, match="not advanced"):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    assert adapter.replica.current()["version"] == 1 and host.anchor["version"] == 0


def test_synthetic_bootstrap_cannot_be_labeled_real(tmp_path):
    adapter, request, initial, host = setup(tmp_path)
    real = Adapter(adapter.replica.root, adapter.source_path, False)
    with pytest.raises(Rejected, match="realm|schema"):
        real.coordinator_once("promote", encoded(request), 0, initial["snapshot_sha256"], host=host)


def test_drift_after_external_adjudication_refuses_switch(tmp_path):
    adapter, request, initial, host = setup(tmp_path)
    path = Path(request["lesson_path"])
    host.on_grant = lambda: path.write_text('{"tampered":true}')
    with pytest.raises(Rejected):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    assert adapter.replica.current()["version"] == 0


def test_read_only_validation_and_grant_replay(tmp_path):
    adapter, request, initial, _ = setup(tmp_path)
    proposal = adapter.proposal("validate_result", encoded(request), 0, initial["snapshot_sha256"])
    host = SimulatedHost(proposal, adapter)
    result = adapter.coordinator_once(
        "validate_result", encoded(request), 0, initial["snapshot_sha256"], host=host
    )
    assert result["receipt"]["version"] == 0
    with pytest.raises(Rejected, match="replay"):
        adapter.coordinator_once(
            "validate_result", encoded(request), 0, initial["snapshot_sha256"], host=host
        )


def test_loaded_code_drift_before_apply_is_rejected(tmp_path, monkeypatch):
    adapter, request, initial, host = setup(tmp_path)
    original = Adapter.proposal
    host.on_grant = lambda: monkeypatch.setattr(Adapter, "proposal", lambda *_args, **_kwargs: {})
    with pytest.raises((Rejected, ValueError)):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    # Restore trusted function to inspect the unchanged pointer.
    monkeypatch.setattr(Adapter, "proposal", original)
    assert adapter.replica.current()["version"] == 0


def test_source_inventory_drift_after_grant_preserves_pointer(tmp_path):
    adapter, request, initial, host = setup(tmp_path)
    stop = adapter.source_path / "tavily-stop.json"

    def drift():
        stop.write_bytes(stop.read_bytes() + b"\n")

    host.on_grant = drift
    with pytest.raises(Rejected, match="drift"):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    assert adapter.replica.current()["version"] == 0


@pytest.mark.parametrize(
    "mutation", ["snapshot", "snapshot_bool", "metadata_program", "commit_replace"]
)
def test_adapter_original_git_and_snapshot_binding(tmp_path, mutation):
    from lesson_consumer import AFTER, commit
    from test_lesson_consumer import git_setup, marker_script

    adapter, request, initial, _ = setup(tmp_path)
    receipt_path = Path(request["result_path"])
    import json

    receipt = json.loads(receipt_path.read_bytes())
    repo = Path(receipt["change_repository"])
    marker = tmp_path / "repository-program-executed"
    if mutation in {"snapshot", "snapshot_bool"}:
        receipt["snapshot_sha256"] = "wrong" if mutation == "snapshot" else True
        receipt_path.write_bytes(encoded(receipt))
    elif mutation == "metadata_program":
        script = marker_script(tmp_path, marker)
        git_setup(repo, "config", "core.fsmonitor", str(script))
        proposal = adapter.proposal("promote", encoded(request), 0, initial["snapshot_sha256"])
        host = SimulatedHost(proposal, adapter)
        assert (
            adapter.coordinator_once(
                "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
            )["status"]
            == "SIMULATED_RECEIPT"
        )
        assert not marker.exists()
        return
    else:
        good = receipt["resulting_commit"]
        git_setup(repo, "reset", "--soft", receipt["base_commit"])
        (repo / "resolver.py").write_bytes(b"def resolve(values):\n    return values[-1]\n")
        bad = commit(repo, "Synthetic incorrect result")
        git_setup(repo, "replace", bad, good)
        (repo / "resolver.py").write_bytes(AFTER)
        receipt["resulting_commit"] = bad
        receipt_path.write_bytes(encoded(receipt))
        assert git_setup(repo, "show", bad + ":resolver.py") == AFTER
    with pytest.raises((Rejected, ValueError)):
        adapter.proposal("promote", encoded(request), 0, initial["snapshot_sha256"])
    assert adapter.replica.current()["version"] == 0 and not marker.exists()


@pytest.mark.parametrize(
    "symbol", ["atomic", "checked", "read", "prove_recipe", "validate_source", "loaded_image"]
)
def test_live_dependency_alias_drift_after_grant_is_rejected(tmp_path, monkeypatch, symbol):
    import coordinator_adapter as module

    adapter, request, initial, host = setup(tmp_path)
    original = getattr(module, symbol)

    def substitute(*args, **kwargs):
        return original(*args, **kwargs)

    host.on_grant = lambda: monkeypatch.setattr(module, symbol, substitute)
    with pytest.raises(Rejected, match="loaded|alias"):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    monkeypatch.setattr(module, symbol, original)
    assert adapter.replica.current()["version"] == 0


@pytest.mark.parametrize(
    "method", ["__init__", "__enter__", "__exit__", "run", "object", "commit_header", "tree"]
)
def test_review_R1_transitive_git_run_drift_rejected_before_execution(
    tmp_path, monkeypatch, method
):
    from lesson_consumer import ObjectView

    adapter, request, initial, host = setup(tmp_path)
    marker = tmp_path / "unreviewed-git-run-executed"
    original = getattr(ObjectView, method)

    def substituted(self, *args, **kwargs):
        marker.write_text("unexpected execution")
        return original(self, *args, **kwargs)

    host.on_grant = lambda: monkeypatch.setattr(ObjectView, method, substituted)
    blocked = False
    try:
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    except Rejected:
        blocked = True
    assert not marker.exists(), "Unreviewed transitive ObjectView.run executed after grant"
    assert blocked and adapter.replica.current()["version"] == 0
    assert host.anchor["version"] == 0


def test_review_R2_candidate_swap_after_intent_never_switches_ungranted_lesson(tmp_path):
    import os
    import subprocess

    adapter, request, initial, host = setup(tmp_path)
    swapped = tmp_path / "candidate-swapped"
    script = tmp_path / "independent-candidate-swap.py"
    script.write_text(r"""
import ctypes,os,select,signal,struct,sys
from pathlib import Path
from reviewed_lessons import bind,encoded,read
parent=int(sys.argv[1]);directory=sys.argv[2];candidate=Path(sys.argv[3]);marker=Path(sys.argv[4])
libc=ctypes.CDLL(None,use_errno=True)
fd=libc.inotify_init1(os.O_CLOEXEC)
assert fd >= 0
assert libc.inotify_add_watch(fd,directory.encode(),0x100|0x2|0x8) >= 0
print("READY",flush=True)
assert select.select([fd],[],[],5)[0], "intent publication not observed"
found=False
while not found:
    events=os.read(fd,65536);offset=0
    while offset<len(events):
        _wd,_mask,_cookie,length=struct.unpack_from("iIII",events,offset)
        name=events[offset+16:offset+16+length].split(b"\0",1)[0]
        offset+=16+length
        if name==b"audit.jsonl":found=True
    if not found:assert select.select([fd],[],[],5)[0]
stopped=False
try:
    os.kill(parent,signal.SIGSTOP);stopped=True
    value=read(candidate)
    value["knowledge_text"]="Different valid synthetic candidate"
    candidate.write_bytes(encoded(bind(value,"lesson_sha256")))
    marker.write_text("done")
finally:
    if stopped:os.kill(parent,signal.SIGCONT)
    os.close(fd)
""")
    original_commit = host.commit_verified_result

    def independent_anchored_lesson_check(grant, receipt):
        current = adapter.replica.current()
        if (
            current["entries"]
            and current["entries"][0]["lesson"]["lesson_sha256"] != host.anchor["lesson_hash"]
        ):
            raise Rejected("independent host: visible lesson differs from adjudicated anchor")
        return original_commit(grant, receipt)

    host.commit_verified_result = independent_anchored_lesson_check
    child = subprocess.Popen(
        [
            sys.executable,
            str(script),
            str(os.getpid()),
            str(adapter.replica.root),
            request["lesson_path"],
            str(swapped),
        ],
        env=os.environ.copy() | {"PYTHONPATH": str(ROOT / "scripts")},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    blocked = False
    try:
        assert child.stdout.readline().strip() == "READY"
        try:
            adapter.coordinator_once(
                "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
            )
        except Rejected:
            blocked = True
        _output, error = child.communicate(timeout=10)
        assert child.returncode == 0, error
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
        # This only addresses the test's own controlled process.
        os.kill(os.getpid(), __import__("signal").SIGCONT)
    assert swapped.exists()
    assert adapter.replica.current()["version"] == 0, (
        "Changed candidate became visible without exact grant"
    )
    assert blocked and host.anchor["version"] == 0


@pytest.mark.parametrize("check_exit", [0, 1])
def test_review_pins_blocked_never_report_full_PASS(tmp_path, monkeypatch, check_exit):
    import json
    import shutil
    import types

    import coordinator_adapter_quality as quality

    (tmp_path / "fixtures").mkdir()
    for name in ["golden.json", "invalid.json"]:
        shutil.copyfile(ROOT / "fixtures" / name, tmp_path / "fixtures" / name)
    monkeypatch.setattr(quality, "ROOT", tmp_path)
    monkeypatch.setattr(quality, "snapshot", lambda: {"fixed": "snapshot"})
    monkeypatch.setattr(
        quality,
        "observed_versions",
        lambda _root: {
            "tools": {
                "codex": {"status": "blocked", "reason": "hash mismatch"},
                "uv": {
                    "status": "blocked",
                    "observed_version": "0.12.23",
                    "expected_version": "0.10.2",
                },
                "spec_kit": {"status": "passed"},
            }
        },
    )
    monkeypatch.setattr(
        quality.subprocess,
        "run",
        lambda *_args, **_kwargs: types.SimpleNamespace(
            stdout="Controlled check output", stderr="", returncode=check_exit
        ),
    )
    assert quality.main() == check_exit
    manifests = list((tmp_path / "artifacts/T018").glob("quality-*/manifest.json"))
    assert len(manifests) == 1
    result = json.loads(manifests[0].read_text())
    assert result["status"] != "PASS"
    assert (
        result["toolchain_pins_status"] == "BLOCKED"
        and result["reproducibility_status"] == "BLOCKED"
    )
    assert result["checks_status"] == ("PASS" if check_exit == 0 else "FAIL")


@pytest.mark.parametrize(
    "attack", ["adapter_proposal", "replica_audit", "replica_current", "object_constructor"]
)
def test_review_actual_instance_dispatch_cannot_escape_pinned_callable(
    tmp_path, monkeypatch, attack
):
    import types

    import coordinator_adapter as module
    from lesson_consumer import ObjectView

    adapter, request, initial, host = setup(tmp_path)
    marker = tmp_path / "unaccepted-instance-call"
    if attack == "object_constructor":
        original = ObjectView.run

        def forged_run(self, *args, **kwargs):
            marker.write_text("unexpected instance run")
            return original(self, *args, **kwargs)

        # A separate class avoids corrupting CPython's original tp_new slot.
        class ForgedObjectView(ObjectView):
            def __new__(kind, *_args, **_kwargs):
                marker.write_text("unexpected constructor")
                value = object.__new__(kind)
                value.run = types.MethodType(forged_run, value)
                return value

        host.on_grant = lambda: monkeypatch.setattr(module, "ObjectView", ForgedObjectView)
    else:
        target, name = {
            "adapter_proposal": (adapter, "proposal"),
            "replica_audit": (adapter.replica, "audit"),
            "replica_current": (adapter.replica, "current"),
        }[attack]
        original = getattr(target, name)

        def substitute(*args, **kwargs):
            marker.write_text("unexpected bound method")
            return original(*args, **kwargs)

        host.on_grant = lambda: monkeypatch.setattr(target, name, substitute)
    with pytest.raises(Rejected, match="dispatch|instance|binding|alias"):
        adapter.coordinator_once(
            "promote", encoded(request), 0, initial["snapshot_sha256"], host=host
        )
    assert not marker.exists()
    assert adapter.replica.load(initial["snapshot_sha256"])["version"] == 0
    assert (adapter.replica.root / "active.json").read_bytes() == encoded(
        {"version": 0, "sha256": initial["snapshot_sha256"]}
    )
