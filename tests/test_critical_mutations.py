import importlib.util
import json
import os
import py_compile
import sys
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from critical_mutations import CORPUS, bounded, execute  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_eight_critical_families_killed_by_loaded_semantics(tmp_path):
    result = execute(tmp_path / "experiment")
    assert result["status"] == "PASS"
    assert result["meaningfully_killed"] == 8
    for entry in result["outcomes"]:
        proof = entry["result"]["proof"]
        assert entry["baseline"]["outcome"] == "survived"
        assert entry["original_sha256"] != entry["mutated_sha256"]
        assert proof["source_sha256"] == entry["mutated_sha256"]
        assert proof["actually_loaded_matches_source"]
        assert entry["result"]["assertion"].startswith("SEMANTIC:")


def test_stale_bytecode_is_unapplied_not_a_kill(tmp_path):
    module = tmp_path / "stale_target.py"
    module.write_text("def f():\n    return 1\n")
    stamp = module.stat().st_mtime
    py_compile.compile(str(module), doraise=True)
    assert Path(importlib.util.cache_from_source(str(module))).exists()
    module.write_text("def f():\n    return 2\n")
    os.utime(module, (stamp, stamp))
    code = (
        "import sys,json;sys.path[:0]=" + repr([str(tmp_path), str(ROOT / "scripts")]) + ";"
        "from critical_mutations import loaded_proof;"
        "p=loaded_proof('stale_target','f'," + repr(str(tmp_path)) + ");"
        "print(json.dumps({'outcome':'unapplied' if not p['actually_loaded_matches_source'] else 'survived','proof':p}))"
    )
    result = bounded([sys.executable, "-c", code], tmp_path)
    assert result["outcome"] == "unapplied"
    assert not result["proof"]["actually_loaded_matches_source"]


@pytest.mark.parametrize(
    "code,category",
    [("import no_such_module", "import_error"), ("syntax ?", "invalid_syntax")],
)
def test_operational_errors_never_kills(tmp_path, code, category):
    result = bounded([sys.executable, "-c", code], tmp_path)
    assert result["outcome"] in {category, "import_error"}
    assert result["outcome"] != "killed"


def test_timeout_killed_process_is_not_semantic_kill(tmp_path):
    result = bounded([sys.executable, "-c", "import time;time.sleep(5)"], tmp_path, 0.02)
    assert result == {"outcome": "timeout", "killed": False}


def test_corpus_is_frozen_eight_families():
    assert len(CORPUS) == len({x["id"] for x in CORPUS}) == 8
    assert {x["id"] for x in CORPUS} == {
        "conflict",
        "duplicate",
        "payment_or",
        "unknown",
        "evidence_kind",
        "budget_reset",
        "schema",
        "stream",
    }


@given(st.lists(st.integers(), min_size=2, max_size=12))
def test_removal_and_order_cannot_erase_conflict(values):
    from pc_sourcing.product_extraction import unique_members

    for ordered in [values, values[::-1]]:
        with pytest.raises(ValueError):
            unique_members([("x", x) for x in ordered])


def test_wrong_import_root_is_scope_error(tmp_path):
    command = (
        "import sys;sys.path.insert(0," + repr(str(ROOT / "scripts")) + ");"
        "from critical_mutations import loaded_proof;"
        "loaded_proof('critical_mutations','code_hash'," + repr(str(tmp_path)) + ")"
    )
    result = bounded([sys.executable, "-c", command], tmp_path)
    assert result["outcome"] == "scope_error"


def test_equivalent_semantic_survivor_is_not_killed(tmp_path):
    module = tmp_path / "equivalent_case.py"
    module.write_text('def f():\n    return int("1")\n')
    command = (
        "import sys,json;sys.path[:0]=" + repr([str(tmp_path), str(ROOT / "scripts")]) + ";"
        "from critical_mutations import loaded_proof;import equivalent_case;"
        "p=loaded_proof('equivalent_case','f'," + repr(str(tmp_path)) + ");"
        "assert equivalent_case.f()==1;"
        "print(json.dumps({'outcome':'survived','proof':p,'equivalence':'requires independent review'}))"
    )
    result = bounded([sys.executable, "-c", command], tmp_path)
    assert result["outcome"] == "survived"
    assert result["proof"]["actually_loaded_matches_source"]


def test_nonpassing_baseline_invalidates_whole_experiment(tmp_path):
    clone = mutation_checkout(tmp_path)
    (clone / "src/pc_sourcing/identity_attributes.py").write_text("syntax ?")
    with pytest.raises(ValueError, match="nonpassing baseline"):
        execute(tmp_path / "failed-experiment", clone)
    assert (
        json.loads((tmp_path / "failed-experiment/baseline_failure.json").read_text())["outcome"]
        == "invalid_syntax"
    )


def mutation_checkout(tmp_path):
    import shutil
    import subprocess

    target = tmp_path / "binding-checkout"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)], check=True
    )
    for name in ["src", "scripts", "fixtures", "specs", "tests"]:
        shutil.copytree(
            ROOT / name,
            target / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    return target


@pytest.mark.parametrize(
    "changed",
    [
        "specs/012-reviewed-improvement/spec.md",
        "fixtures/golden.json",
        "tests/test_lesson_consumer.py",
        "scripts/critical_mutations.py",
    ],
)
def test_review_M2_stale_mutation_result_rejected_on_input_drift(tmp_path, changed):
    from critical_mutations import verify_result

    clone = mutation_checkout(tmp_path)
    output = tmp_path / "bound-experiment"
    execute(output, clone)
    assert verify_result(output, clone)["status"] == "PASS"
    path = clone / changed
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="drift"):
        verify_result(output, clone)


def test_review_M2_drift_during_run_invalidates_before_pass(tmp_path, monkeypatch):
    import critical_mutations as harness

    clone = mutation_checkout(tmp_path)
    original = harness.bounded
    calls = 0

    def drift(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 2:
            path = clone / "specs/012-reviewed-improvement/spec.md"
            path.write_text(path.read_text() + "\nchanged during experiment\n")
        return result

    monkeypatch.setattr(harness, "bounded", drift)
    output = tmp_path / "mid-run-drift"
    with pytest.raises(ValueError, match="drift"):
        harness.execute(output, clone)
    assert not (output / "manifest.json").exists()


def test_review_M2_tampered_receipt_never_reused(tmp_path):
    from critical_mutations import verify_result

    clone = mutation_checkout(tmp_path)
    output = tmp_path / "tampered-result"
    execute(output, clone)
    p = output / "manifest.json"
    value = json.loads(p.read_text())
    value["meaningfully_killed"] = 999
    p.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="hash"):
        verify_result(output, clone)


@pytest.mark.parametrize(
    "attack",
    [
        "false_loaded_hash",
        "unchanged_source",
        "wrong_original",
        "wrong_assertion",
        "false_baseline",
        "wrong_origin",
    ],
)
def test_rehashed_semantic_contradiction_cannot_pass_reuse(tmp_path, attack):
    from critical_mutations import verify_result
    from reviewed_lessons import bind

    clone = mutation_checkout(tmp_path)
    output = tmp_path / "contradictory-result"
    execute(output, clone)
    p = output / "manifest.json"
    result = json.loads(p.read_text())
    entry = result["outcomes"][0]
    if attack == "false_loaded_hash":
        entry["result"]["proof"]["fresh_source_code_sha256"] = entry["baseline"]["proof"][
            "fresh_source_code_sha256"
        ]
    elif attack == "unchanged_source":
        entry["mutated_sha256"] = entry["original_sha256"]
        entry["result"]["proof"]["source_sha256"] = entry["original_sha256"]
    elif attack == "wrong_original":
        entry["original_sha256"] = "f" * 64
    elif attack == "wrong_assertion":
        entry["result"]["assertion"] = "SEMANTIC: unrelated assertion"
    elif attack == "false_baseline":
        entry["baseline"]["proof"]["loaded_code_sha256"] = "f" * 64
    else:
        entry["result"]["proof"]["imported_path"] = "/tmp/unrelated/other.py"
    (output / (entry["family"] + ".json")).write_text(json.dumps(entry))
    p.write_text(json.dumps(bind(result, "result_sha256")))
    with pytest.raises(ValueError):
        verify_result(output, clone)
