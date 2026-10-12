"""OFFER-09/10: consistent exports, literal spreadsheet text and durable realm boundary."""

import json
import sqlite3
import zipfile

import pytest
from test_normalized_offers import NOW, proven, row

from pc_sourcing.normalized_exports import export_bundle, verify_bundle
from pc_sourcing.normalized_models import NormalizedOffer


def test_roundtrip_all_formats_same_rows_and_decimal_unknowns(tmp_path):
    offer = NormalizedOffer.model_validate(proven(row(delivery_cost=None)))
    data = export_bundle([offer], tmp_path / "result", NOW)
    assert verify_bundle(tmp_path / "result")["status"] == "passed"
    assert data["rows"][0]["decision"]["full_total_rub"] is None
    with sqlite3.connect(tmp_path / "result/normalized.sqlite") as db:
        assert json.loads(db.execute("SELECT data FROM rows").fetchone()[0]) == data["rows"][0]


def test_xlsx_uses_literal_inline_strings_and_cannot_create_formula(tmp_path):
    offer = NormalizedOffer.model_validate(proven(row(seller_name="=DANGEROUS()")))
    export_bundle([offer], tmp_path / "result", NOW)
    with zipfile.ZipFile(tmp_path / "result/offers.xlsx") as z:
        xml = z.read("xl/worksheets/sheet1.xml")
        assert b"<f>" not in xml and b"inlineStr" in xml
    assert verify_bundle(tmp_path / "result")["status"] == "passed"


def test_modified_export_fails_hash_verification(tmp_path):
    export_bundle([NormalizedOffer.model_validate(proven(row()))], tmp_path / "result", NOW)
    (tmp_path / "result/offers.csv").write_text("tampered")
    with pytest.raises(ValueError):
        verify_bundle(tmp_path / "result")


def test_durable_bridge_preserves_rows_and_restore(tmp_path):
    from pc_sourcing.durable_jobs import Store
    from pc_sourcing.normalized_cli import persist_synthetic

    offer = NormalizedOffer.model_validate(proven(row()))
    result = persist_synthetic([offer], tmp_path / "runtime", NOW)
    assert result["results"][0]["status"] == "done"
    store = Store(tmp_path / "runtime")
    store.backup(tmp_path / "backup")
    Store.restore(tmp_path / "backup", tmp_path / "restored")
    assert Store(tmp_path / "restored").report() == store.report()
    again = persist_synthetic([offer], tmp_path / "restored", NOW)
    assert again["results"][0]["status"] == "idle"


def test_real_records_never_relabelled_by_durable_bridge(tmp_path):
    from pc_sourcing.normalized_cli import persist_synthetic

    data = proven(row())
    data["synthetic"] = False
    for evidence in data["evidence"]:
        evidence["synthetic"] = False
    offer = NormalizedOffer.model_validate(data)
    with pytest.raises(ValueError, match="real records"):
        persist_synthetic([offer], tmp_path / "runtime", NOW)
    assert not (tmp_path / "runtime").exists()


def test_invalid_xml_cannot_publish_a_success_bundle(tmp_path):
    offer = NormalizedOffer.model_validate(proven(row(seller_name="bad\x01text")))
    with pytest.raises(ValueError, match=r"U\+0001"):
        export_bundle([offer], tmp_path / "result", NOW)
    assert not (tmp_path / "result").exists()


def test_cloud_cli_export_verify_and_durable_subprocess(tmp_path):
    import os
    import subprocess
    import sys

    source = tmp_path / "input.json"
    source.write_text(json.dumps([proven(row())]))
    env = {
        **os.environ,
        "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"),
    }
    command = [sys.executable, "-m", "pc_sourcing.normalized_cli"]
    run = subprocess.run(
        command
        + [
            "run",
            "--input",
            str(source),
            "--output",
            str(tmp_path / "report"),
            "--as-of",
            NOW.isoformat(),
            "--runtime-root",
            str(tmp_path / "runtime"),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["runtime"]["results"][0]["status"] == "done"
    check = subprocess.run(
        command + ["verify", "--output", str(tmp_path / "report")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout)["formats"] == 5


@pytest.mark.parametrize("target", ["offers.csv", "offers.xlsx", "report.md", "normalized.sqlite"])
def test_rehashed_but_inconsistent_format_fails_canonical_readback(tmp_path, target):
    import hashlib
    import io

    root = tmp_path / "result"
    export_bundle([NormalizedOffer.model_validate(proven(row()))], root, NOW)
    path = root / target
    if target == "offers.csv":
        path.write_text(path.read_text().replace("450000.00", "450001.00", 1))
    elif target == "report.md":
        path.write_text(path.read_text() + "unrecorded extra statement\n")
    elif target == "normalized.sqlite":
        with sqlite3.connect(path) as db:
            db.execute("UPDATE rows SET data='{}'")
    else:
        original = path.read_bytes()
        output = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(original)) as source,
            zipfile.ZipFile(output, "w") as result,
        ):
            for name in source.namelist():
                blob = source.read(name)
                if name == "xl/worksheets/sheet1.xml":
                    blob = blob.replace(b"450000.00", b"450001.00", 1)
                result.writestr(name, blob)
        path.write_bytes(output.getvalue())
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["files"][target] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="canonical"):
        verify_bundle(root)


def test_every_export_retains_unknowns_alternatives_and_duplicate_evidence(tmp_path):
    from datetime import timedelta

    old = proven(row(id="old", delivery_cost=None))
    old["observed_at"] = (NOW - timedelta(minutes=1)).isoformat()
    new = proven(
        row(
            id="new",
            delivery_cost=None,
            conditional_prices=[
                {
                    "id": "special",
                    "money": {"amount": "1.01", "currency": "RUB"},
                    "kind": "conditional",
                    "basis": "purchase",
                    "quantity": 1,
                    "conditions": ["SYNTHETIC condition"],
                }
            ],
        )
    )
    dataset = export_bundle(
        [NormalizedOffer.model_validate(old), NormalizedOffer.model_validate(new)],
        tmp_path / "result",
        NOW,
    )
    assert verify_bundle(tmp_path / "result") == {"status": "passed", "rows": 1, "formats": 5}
    decision = dataset["rows"][0]["decision"]
    assert decision["full_total_rub"] is None
    assert dataset["rows"][0]["offer"]["conditional_prices"][0]["money"]["amount"] == "1.01"
    assert dataset["rejections"][0]["offer"]["evidence"]
    with sqlite3.connect(tmp_path / "result/normalized.sqlite") as db:
        assert (
            json.loads(db.execute("SELECT data FROM rejections").fetchone()[0])
            == dataset["rejections"][0]
        )


def test_duplicate_url_batch_is_atomic_coalesced_and_idempotent(tmp_path):
    from datetime import timedelta

    from pc_sourcing.normalized_cli import persist_synthetic

    old = NormalizedOffer.model_validate(
        proven(row(id="old", observed_at=(NOW - timedelta(seconds=1)).isoformat()))
    )
    new = NormalizedOffer.model_validate(proven(row(id="new")))
    first = persist_synthetic([old, new], tmp_path / "runtime", NOW)
    assert len(first["runtime"]["jobs"]) == 1
    receipt = first["runtime"]["current"][0]["receipt"]
    assert receipt["facts"]["normalized_offer"]["id"] == "new"
    assert {o["id"] for o in receipt["facts"]["raw_observations"]} == {"old", "new"}
    second = persist_synthetic([new, old], tmp_path / "runtime", NOW + timedelta(seconds=1))
    assert second["results"][0]["status"] == "idle"
    assert second["runtime"] == first["runtime"]


def test_conflicting_existing_generation_rejects_whole_batch_without_enqueue(tmp_path):
    from pc_sourcing.durable_jobs import Store
    from pc_sourcing.normalized_cli import persist_synthetic

    original = NormalizedOffer.model_validate(proven(row()))
    persist_synthetic([original], tmp_path / "runtime", NOW)
    before = Store(tmp_path / "runtime").report()
    changed = NormalizedOffer.model_validate(proven(row(seller_name="changed")))
    unrelated = NormalizedOffer.model_validate(
        proven(row(id="other", url="https://other-synthetic.example.test/item"))
    )
    with pytest.raises(ValueError, match="generation input changed"):
        persist_synthetic([unrelated, changed], tmp_path / "runtime", NOW)
    assert Store(tmp_path / "runtime").report() == before


def test_batch_transaction_rolls_back_all_enqueues_and_sources_on_sql_failure(
    tmp_path, monkeypatch
):
    from contextlib import contextmanager

    from pc_sourcing import normalized_cli
    from pc_sourcing.durable_jobs import Store

    root = tmp_path / "runtime"
    store = Store(root)
    before = store.report()

    class FailSecondInsert:
        def __init__(self, db):
            self.db, self.inserts = db, 0

        def execute(self, sql, args=()):
            if sql.startswith("INSERT OR IGNORE INTO jobs"):
                self.inserts += 1
                if self.inserts == 2:
                    raise sqlite3.IntegrityError("injected batch failure")
            return self.db.execute(sql, args)

    class FailingStore(Store):
        @contextmanager
        def transaction(self):
            with super().transaction() as db:
                yield FailSecondInsert(db)

    monkeypatch.setattr(normalized_cli, "Store", FailingStore)
    a = NormalizedOffer.model_validate(
        proven(row(id="one", url="https://synthetic.example.test/one"))
    )
    b = NormalizedOffer.model_validate(
        proven(row(id="two", url="https://other-synthetic.example.test/two"))
    )
    with pytest.raises(sqlite3.IntegrityError, match="injected batch failure"):
        normalized_cli.persist_synthetic([a, b], root, NOW)
    assert store.report() == before
    monkeypatch.setattr(normalized_cli, "Store", Store)
    assert len(normalized_cli.persist_synthetic([a, b], root, NOW)["runtime"]["current"]) == 2


def test_listing_id_aliases_are_raw_runtime_observations_and_canonical_export(tmp_path):
    from pc_sourcing.normalized_cli import persist_synthetic

    a = NormalizedOffer.model_validate(
        proven(row(id="alias-one", url="https://synthetic.example.test/one", listing_id="same"))
    )
    b = NormalizedOffer.model_validate(
        proven(row(id="alias-two", url="https://synthetic.example.test/two", listing_id="same"))
    )
    runtime = persist_synthetic([a, b], tmp_path / "runtime", NOW)
    dataset = export_bundle([a, b], tmp_path / "report", NOW)
    assert len(runtime["runtime"]["current"]) == 2
    assert len(dataset["rows"]) == 1
    assert len(dataset["rejections"]) == 1
    assert dataset["rejections"][0]["offer"]["evidence"]


def test_xml_control_cli_failure_is_structured_preserves_input_and_runtime(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    source = tmp_path / "input.json"
    original = json.dumps([proven(row(seller_name="bad\x01text"))]).encode()
    source.write_bytes(original)
    command = [
        sys.executable,
        "-m",
        "pc_sourcing.normalized_cli",
        "run",
        "--input",
        str(source),
        "--output",
        str(tmp_path / "out"),
        "--as-of",
        NOW.isoformat(),
        "--runtime-root",
        str(tmp_path / "runtime"),
    ]
    result = subprocess.run(
        command,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stderr)["status"] == "failed"
    assert "U+0001" in json.loads(result.stderr)["reason"]
    assert "Traceback" not in result.stderr
    assert source.read_bytes() == original
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "runtime").exists()


def test_valid_xml_carriage_return_and_whitespace_roundtrip(tmp_path):
    offer = NormalizedOffer.model_validate(proven(row(seller_name=" leading\rline\t trailing ")))
    export_bundle([offer], tmp_path / "out", NOW)
    assert verify_bundle(tmp_path / "out")["status"] == "passed"
