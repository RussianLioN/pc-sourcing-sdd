"""Fixed release/URL/target and source-policy admission constraints."""

import json

import pytest

from pc_sourcing.live_transport import AccessBlocked
from pc_sourcing.witness_profiles import PROFILES, release_gate


def test_profiles_have_exact_small_budgets_and_no_denied_domains():
    assert set(PROFILES) == {"tdvat", "evens", "ram28", "ramregard"}
    for p in PROFILES.values():
        assert p.card_limit == 1 and p.http_limit == 2 and p.interval >= 10
        assert "?" not in p.url and p.byte_limit == 1_000_000 and p.timeout == 15


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"status": "limited_controller_PASS", "independent": False},
        {"reviewed_commit": "0" * 40},
    ],
)
def test_unbound_or_nonindependent_release_fails_before_live(value, tmp_path):
    from pc_sourcing.durable_jobs import digest

    p = tmp_path / "review.json"
    raw = json.dumps(value).encode()
    p.write_bytes(raw)
    with pytest.raises(AccessBlocked):
        release_gate(p, digest(raw))


def test_bound_release_requires_clean_exact_reviewed_snapshot(tmp_path, monkeypatch):
    import subprocess

    import pc_sourcing.witness_profiles as module
    from pc_sourcing.durable_jobs import digest

    repo = tmp_path / "reviewed"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=synthetic-fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "synthetic reviewed snapshot",
        ],
        check=True,
    )
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    value = {
        "status": "limited_controller_PASS",
        "independent": True,
        "reviewed_commit": sha,
        "profile_hashes": {k: PROFILES[k].fingerprint for k in ("tdvat", "evens")},
    }
    raw = json.dumps(value).encode()
    p = tmp_path / "review.json"
    p.write_bytes(raw)
    monkeypatch.setattr(module, "ROOT", repo)
    assert release_gate(p, digest(raw))["reviewed_commit"] == sha
    (repo / "unreviewed.py").write_text("synthetic unrelated dirty change")
    with pytest.raises(AccessBlocked, match="dirty"):
        release_gate(p, digest(raw))
