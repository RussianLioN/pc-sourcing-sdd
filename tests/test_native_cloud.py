"""Synthetic receipt unit controls, never evidence of actual cloud task review."""

import copy
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
native = importlib.import_module("native_cloud")
CONTRACT = "97fd8b21f8aee68c625a1101df04fc36d9b14625"


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def commit(root, message):
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Unit Test",
            "-c",
            "user.email=unit@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            message,
        ],
        check=True,
    )
    return native.git(root, "rev-parse", "HEAD").decode().strip()


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "unit checkout with spaces"
    subprocess.run(["git", "clone", "--shared", "--quiet", str(ROOT), str(root)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "checkout",
            "--detach",
            "5e031fcdd2daf7690585ed84f1b731c0972f4dc3",
        ],
        check=True,
    )
    shutil.copy2(ROOT / "scripts/native_cloud.py", root / "scripts/native_cloud.py")
    expected = commit(root, "unit candidate; no real cloud tasks")
    profile, binding, current = native.verify_project(root, expected, CONTRACT)
    quality_snapshot = native.quality_snapshot(root)
    refs = {}
    for role in ("writer", "reviewer"):
        out = root / "artifacts/native-cloud/unit" / role
        q = out / "quality"
        q.mkdir(parents=True)
        for name in ("tests.xml", "pilot.sqlite", "report.md"):
            (q / name).write_text("SYNTHETIC UNIT RECEIPT; NOT CLOUD EVIDENCE\n")
        checks = []
        for name in native.REQUIRED:
            (out / (name + ".log")).write_text("synthetic check log\n")
            checks.append(
                {
                    "id": name,
                    "exit_code": 0,
                    "command": ["unit-fixture", name],
                    "log": name + ".log",
                }
            )
        quality = {
            "status": "passed",
            "unchanged_during_checks": True,
            "snapshot": quality_snapshot,
            "checks": [{"exit_code": 0}] * 4,
        }
        write_json(q / "manifest.json", quality)
        state = {
            "db_sha256": native.sha(q / "pilot.sqlite"),
            "report_sha256": native.sha(q / "report.md"),
            "counts": {"runs": 1, "offers": 20, "evaluations": 20, "rejections": 2},
        }
        write_json(out / "repeat.json", {"before": state, "after": state, "exit_code": 0})
        record = {
            "schema": profile["record_schema"],
            "role": role,
            "task_id": "unit-" + role,
            "environment_id": "unit-environment",
            "checkout_identity": "unit-checkout-" + role,
            "contract": binding,
            "snapshot": current,
            "status": "passed",
            "clean_before": True,
            "clean_after": True,
            "unchanged_during_checks": True,
            "claims": profile["claims"],
            "limitations": profile["limitations"],
            "environment": profile["required_environment"],
            "checks": checks,
            "quality_snapshot": quality_snapshot,
            "evidence": {
                str(p.relative_to(out)): native.sha(p) for p in out.rglob("*") if p.is_file()
            },
        }
        path = out / "record.json"
        write_json(path, record)
        refs[role] = native.reference(path)
    review = {
        "schema": profile["review_schema"],
        "task_id": "unit-reviewer",
        "commit": expected,
        "contract": binding,
        "writer_record_sha256": refs["writer"]["sha256"],
        "reviewer_record_sha256": refs["reviewer"]["sha256"],
        "verdict": "passed",
        "findings": [],
        "clean_after": True,
        "snapshot_after": current,
        "summary": "Synthetic unit fixture, not an independent review",
        "limitations": profile["limitations"],
    }
    review_path = root / "artifacts/native-cloud/unit/review.json"
    write_json(review_path, review)
    refs["review"] = native.reference(review_path)
    provenance = {
        "schema": "native-cloud-provenance/1",
        "commit": expected,
        "contract_commit": CONTRACT,
        "writer_task_id": "unit-writer",
        "reviewer_task_id": "unit-reviewer",
        "verified_real_tasks": True,
        "separate_checkouts": True,
        "reviewer_did_not_integrate_patches": True,
        **{k + "_sha256": refs[k]["sha256"] for k in ("writer", "reviewer", "review")},
    }
    provenance_path = root / "artifacts/native-cloud/unit/provenance.json"
    write_json(provenance_path, provenance)
    refs["provenance"] = native.reference(provenance_path)
    manifest = {
        "schema": profile["manifest_schema"],
        "status": "passed",
        "snapshot": current,
        "contract": binding,
        "claims": profile["claims"],
        "limitations": profile["limitations"],
        "references": refs,
    }
    return root, expected, manifest


def check(bundle):
    root, expected, manifest = bundle
    return native.validate_bundle(
        root, manifest, expected, CONTRACT, "unit-writer", "unit-reviewer"
    )


def edit_reference(manifest, key, edit):
    path = Path(manifest["references"][key]["path"])
    data = json.loads(path.read_text())
    edit(data)
    write_json(path, data)
    manifest["references"][key] = native.reference(path)


def test_consistent_unit_bundle_and_finalize_check(bundle):
    assert check(bundle)["status"] == "passed"
    root, expected, manifest = bundle
    paths = {k: v["path"] for k, v in manifest["references"].items()}
    out = root / "artifacts/native-cloud/unit/accepted.json"
    native.finalize(
        root,
        out=out,
        expected=expected,
        contract_commit=CONTRACT,
        writer_task_id="unit-writer",
        reviewer_task_id="unit-reviewer",
        **paths,
    )
    assert (
        native.validate_bundle(
            root, json.loads(out.read_text()), expected, CONTRACT, "unit-writer", "unit-reviewer"
        )["status"]
        == "passed"
    )
    with pytest.raises(FileExistsError):
        native.finalize(
            root,
            out=out,
            expected=expected,
            contract_commit=CONTRACT,
            writer_task_id="unit-writer",
            reviewer_task_id="unit-reviewer",
            **paths,
        )


@pytest.mark.parametrize("expected", ["802e001", "0" * 40])
def test_wrong_or_short_sha_rejected(bundle, expected):
    root, _, manifest = bundle
    with pytest.raises(native.AcceptanceError):
        native.validate_bundle(root, manifest, expected, CONTRACT, "unit-writer", "unit-reviewer")


@pytest.mark.parametrize(
    "key,field,value",
    [
        ("writer", "contract", {}),
        ("reviewer", "clean_after", False),
        ("reviewer", "task_id", "wrong-task"),
        ("writer", "task_id", None),
        ("writer", "checks", []),
        ("review", "verdict", "pending"),
        ("review", "clean_after", False),
        ("review", "findings", [{"severity": "medium", "reason": "needs repair"}]),
        ("review", "writer_record_sha256", "0" * 64),
        ("review", "commit", "0" * 40),
        ("provenance", "verified_real_tasks", False),
        ("provenance", "reviewer_did_not_integrate_patches", False),
        ("provenance", "review_sha256", "0" * 64),
    ],
)
def test_receipt_review_and_provenance_mismatch_rejected(bundle, key, field, value):
    edit_reference(bundle[2], key, lambda data: data.update({field: value}))
    with pytest.raises(native.AcceptanceError):
        check(bundle)


def test_spec_hash_drift_rejected(bundle):
    def change(data):
        data["contract"]["spec_sha256"] = "0" * 64

    edit_reference(bundle[2], "reviewer", change)
    with pytest.raises(native.AcceptanceError, match="SHA/spec"):
        check(bundle)


def test_quality_corpus_hash_is_checked_against_current_files(bundle):
    path = Path(bundle[2]["references"]["writer"]["path"])
    data = json.loads(path.read_text())
    q = path.parent / "quality/manifest.json"
    quality = json.loads(q.read_text())
    quality["snapshot"]["spec_hash"] = "0" * 64
    write_json(q, quality)
    data["quality_snapshot"] = quality["snapshot"]
    data["evidence"]["quality/manifest.json"] = native.sha(q)
    write_json(path, data)
    bundle[2]["references"]["writer"] = native.reference(path)
    with pytest.raises(native.AcceptanceError, match="quality SHA/spec/corpus"):
        check(bundle)


def test_protected_blob_change_rejected_even_when_committed(bundle):
    root, _, manifest = bundle
    with (root / "fixtures/golden.json").open("a") as file:
        file.write("\n")
    changed = commit(root, "unit negative protected mutation")
    with pytest.raises(native.AcceptanceError, match="protected baseline"):
        native.validate_bundle(root, manifest, changed, CONTRACT, "unit-writer", "unit-reviewer")


def test_committed_contract_change_rejected(bundle):
    root, _, manifest = bundle
    with (root / "specs/003-native-cloud/spec.md").open("a") as file:
        file.write("\nunauthorized unit mutation\n")
    changed = commit(root, "unit negative contract mutation")
    with pytest.raises(native.AcceptanceError, match="contract changed"):
        native.validate_bundle(root, manifest, changed, CONTRACT, "unit-writer", "unit-reviewer")


def test_new_commit_invalidates_old_approval(bundle):
    root, expected, manifest = bundle
    (root / "docs/native-cloud-handoff.md").write_text("unit documentation change\n")
    changed = commit(root, "unit next snapshot")
    with pytest.raises(native.AcceptanceError, match="STALE"):
        native.validate_bundle(root, manifest, expected, CONTRACT, "unit-writer", "unit-reviewer")
    with pytest.raises(native.AcceptanceError, match="STALE"):
        native.validate_bundle(root, manifest, changed, CONTRACT, "unit-writer", "unit-reviewer")


def test_artifact_tampering_rejected(bundle):
    path = Path(bundle[2]["references"]["reviewer"]["path"]).parent / "quality/report.md"
    path.write_text("changed unit artifact")
    with pytest.raises(native.AcceptanceError, match="evidence hash"):
        check(bundle)


def test_same_checkout_rejected(bundle):
    writer = json.loads(Path(bundle[2]["references"]["writer"]["path"]).read_text())
    edit_reference(
        bundle[2],
        "reviewer",
        lambda data: data.update(checkout_identity=writer["checkout_identity"]),
    )
    with pytest.raises(native.AcceptanceError, match="checkout is not separate"):
        check(bundle)


def test_unsupported_os_claim_rejected(bundle):
    manifest = copy.deepcopy(bundle[2])
    manifest["claims"]["os_readonly"] = True
    with pytest.raises(native.AcceptanceError, match="unsupported manifest claim"):
        native.validate_bundle(
            bundle[0], manifest, bundle[1], CONTRACT, "unit-writer", "unit-reviewer"
        )


def test_evidence_symlink_escape_rejected(bundle, tmp_path):
    directory = Path(bundle[2]["references"]["reviewer"]["path"]).parent
    outside = tmp_path / "outside"
    outside.write_text("unit external file")
    (directory / "escape").symlink_to(outside)
    with pytest.raises(native.AcceptanceError, match="symlink escapes"):
        native.artifact_path(directory, "escape")
    with pytest.raises(native.AcceptanceError, match="escapes directory"):
        native.artifact_path(directory, "../outside")


def test_collect_dirty_checkout_fails_before_writes(bundle):
    root, expected, _ = bundle
    (root / "untracked-unit-file").write_text("dirty")
    out = root / "artifacts/native-cloud/must-not-create"
    with pytest.raises(native.AcceptanceError, match="dirty"):
        native.collect(root, out, expected, CONTRACT, "writer", "unit-writer", "unit-environment")
    assert not out.exists()


def test_actual_checker_cli_nonzero_for_wrong_sha(bundle):
    root, _, manifest = bundle
    path = root / "artifacts/native-cloud/unit/manifest.json"
    write_json(path, manifest)
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(root / "scripts/native_cloud.py"),
            "check",
            "--manifest",
            str(path),
            "--expected-sha",
            "0" * 40,
            "--contract-commit",
            CONTRACT,
            "--writer-task-id",
            "unit-writer",
            "--reviewer-task-id",
            "unit-reviewer",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "blocked"


def test_evidence_preflight_lists_missing_bytes_without_acceptance(tmp_path):
    record = tmp_path / "record.json"
    write_json(record, {"evidence": {"b.log": "0" * 64, "a.log": "0" * 64}})
    with pytest.raises(native.AcceptanceError, match="a.log, b.log"):
        native.evidence_preflight(record)
    assert not (tmp_path / "manifest.json").exists()


def test_evidence_preflight_checks_bytes_and_rejects_tampering(tmp_path):
    artifact = tmp_path / "check.log"
    artifact.write_text("synthetic local evidence")
    record = tmp_path / "record.json"
    write_json(record, {"evidence": {"check.log": native.sha(artifact)}})
    assert native.evidence_preflight(record) == {
        "status": "available",
        "files": 1,
        "acceptance": "not evaluated",
    }
    artifact.write_text("tampered")
    with pytest.raises(native.AcceptanceError, match="evidence hash differs"):
        native.evidence_preflight(record)


def test_evidence_preflight_rejects_escape(tmp_path):
    record = tmp_path / "record.json"
    write_json(record, {"evidence": {"../outside": "0" * 64}})
    with pytest.raises(native.AcceptanceError, match="escapes"):
        native.evidence_preflight(record)
