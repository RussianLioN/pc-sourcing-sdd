"""OPS-09 product→real parser→durable CLI/SQLite/evidence, entirely synthetic."""

import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from pc_sourcing.durable_cli import fixture_jobs
from pc_sourcing.durable_jobs import Store
from pc_sourcing.durable_product import prepare_product_fixture

URL = "https://synthetic-product.example.test/card"
REQUEST = {
    "name": "MSI RTX 5090 SUPRIM LIQUID OC",
    "mpn": "G5090-32SLC",
    "category": "gpu",
    "quantity": 1,
    "region": "Москва",
}


def fixture(**changes):
    product = {
        "@type": "Product",
        "name": REQUEST["name"],
        "mpn": REQUEST["mpn"],
        "offers": {"@type": "Offer", "price": "450000", "priceCurrency": "RUB"},
    }
    return {
        "synthetic": True,
        "source": "synthetic-product",
        "url": URL,
        "context": {"scenario": "product-bridge"},
        "request": REQUEST,
        "primary_html": '<script type="application/ld+json">' + json.dumps(product) + "</script>",
        "observed_at": datetime(2026, 10, 12, tzinfo=UTC).isoformat(),
        "policy": {"budget": 3, "interval": 0},
        **changes,
    }


def test_real_product_parser_is_used_without_promoting_synthetic_to_live():
    row = prepare_product_fixture(fixture())
    receipt = row["receipt"]
    observation = receipt["facts"]["observation"]
    assert observation["match"] == "exact" and observation["eligible"] is False
    assert observation["price_rub"] == 450000
    assert receipt["synthetic"] is True and receipt["origin"] == "synthetic_fixture"
    assert receipt["facts"]["input_provenance"].startswith("synthetic_primary_html")
    assert observation["facts"] and observation["primary"]["retained_sha256"]
    assert row["context"]["product_request"]["mpn"] == REQUEST["mpn"]


def test_changed_product_request_cannot_reuse_same_context_key(tmp_path):
    first = prepare_product_fixture(fixture())
    second = prepare_product_fixture(fixture(request={**REQUEST, "quantity": 2}))
    store = Store(tmp_path / "runtime")
    store.configure_source("synthetic-product", limit=3, interval=0)
    assert store.enqueue(first["source"], first["url"], first["context"]) != store.enqueue(
        second["source"], second["url"], second["context"]
    )


def test_product_cli_checkpoint_report_and_backup_restore_e2e(tmp_path):
    path = tmp_path / "fixtures.json"
    path.write_text(json.dumps([fixture()]))
    root = tmp_path / "runtime"

    def cli(action, runtime=root, *extra, code=0):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pc_sourcing.durable_cli",
                action,
                "--root",
                str(runtime),
                *extra,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == code, result.stderr
        return json.loads(result.stdout if code == 0 else result.stderr)

    jobs = cli("submit", root, "--fixtures", str(path))["jobs"]
    assert cli("submit", root, "--fixtures", str(path))["jobs"] == jobs
    assert cli("work", root, "--fixtures", str(path))["results"][0]["status"] == "done"
    snapshot = cli("status")
    o = snapshot["current"][0]["receipt"]["facts"]["observation"]
    assert o["match"] == "exact" and o["eligible"] is False
    report = tmp_path / "report.json"
    cli("report", root, "--output", str(report))
    assert json.loads(report.read_text()) == snapshot
    backup = tmp_path / "backup"
    cli("backup", root, "--output", str(backup))
    restored = tmp_path / "restored"
    cli("restore", restored, "--backup", str(backup))
    assert cli("status", restored) == snapshot
    altered = fixture(primary_html=fixture()["primary_html"] + "<p>packaging only</p>")
    path.write_text(json.dumps([altered]))
    failure = cli("submit", root, "--fixtures", str(path), code=1)
    assert "input changed" in failure["reason"]
    assert cli("status") == snapshot
    altered["generation"] = 1
    path.write_text(json.dumps([altered]))
    cli("submit", root, "--fixtures", str(path))
    assert cli("work", root, "--fixtures", str(path))["results"][0]["status"] == "done"
    after = cli("status")
    assert len(after["current"]) == 1 and len(after["history"]) == 2
    assert after["sources"][0]["spent"] == 2


def test_changed_uncommitted_fixture_is_rejected_before_claim(tmp_path):
    path = tmp_path / "fixtures.json"
    path.write_text(json.dumps([fixture()]))
    root = tmp_path / "runtime"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pc_sourcing.durable_cli",
            "submit",
            "--root",
            str(root),
            "--fixtures",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    before = Store(root).report()
    path.write_text(
        json.dumps([fixture(primary_html=fixture()["primary_html"] + "<p>only receiver</p>")])
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pc_sourcing.durable_cli",
            "work",
            "--root",
            str(root),
            "--fixtures",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1 and "input changed" in json.loads(result.stderr)["reason"]
    assert Store(root).report() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"synthetic": False},
        {"primary_html": ""},
        {"observed_at": "2026-10-12"},
        {"receipt": {}},
        {"blocked_reason": "denied"},
    ],
)
def test_product_fixture_malformed_or_mixed_mode_fails_before_store(tmp_path, changes):
    path = tmp_path / "fixtures.json"
    path.write_text(json.dumps([fixture(**changes)]))
    with pytest.raises((ValueError, KeyError)):
        fixture_jobs(path)
