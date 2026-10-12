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


class StreamFixture:
    """Synthetic decoded-body reader; no socket or actual HTTP."""

    def __init__(self, body, *, declared=None, chunk=65536, clock=None, advance=0):
        self.body = body
        self.cursor = 0
        self.chunk = chunk
        self.clock = clock
        self.advance = advance
        self.asks = []
        self.headers = {} if declared is None else {"content-length": str(declared)}
        self.length = declared
        self.chunked = False

    def read1(self, n):
        self.asks.append(n)
        if self.clock is not None:
            self.clock[0] += self.advance
        data = self.body[self.cursor : self.cursor + min(n, self.chunk)]
        self.cursor += len(data)
        if self.length is not None:
            self.length -= len(data)
        return data

    def isclosed(self):
        return self.cursor == len(self.body)


@pytest.mark.parametrize("size", [999999, 1000000])
def test_profile_streaming_accepts_in_budget_neighbor_and_exact_known_length(size):
    from pc_sourcing.witness_controller import read_profile_body

    r = StreamFixture(b"x" * size, declared=size)
    assert len(read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: 0)) == size
    assert r.cursor <= 1000000 and max(r.asks) <= 65536


@pytest.mark.parametrize("size", [1000001, 1200000, 2000000])
def test_profile_streaming_never_reads_extra_body_to_reject_oversize(size):
    from pc_sourcing.witness_controller import read_profile_body

    r = StreamFixture(b"x" * size)
    with pytest.raises(AccessBlocked, match="byte"):
        read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: 0)
    assert r.cursor <= 1000000 and sum(r.asks) <= 1000000


def test_declared_oversize_rejected_before_first_read():
    from pc_sourcing.witness_controller import read_profile_body

    r = StreamFixture(b"x" * 1200000, declared=1200000)
    with pytest.raises(AccessBlocked, match="byte"):
        read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: 0)
    assert r.asks == [] and r.cursor == 0


@pytest.mark.parametrize("advance", [15, 16, 30])
def test_profile_streaming_checks_total_elapsed_after_chunk_not_only_before(advance):
    from pc_sourcing.witness_controller import read_profile_body

    timer = [0]
    r = StreamFixture(b"abc", clock=timer, advance=advance)
    with pytest.raises(AccessBlocked, match="deadline"):
        read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: timer[0])
    assert len(r.asks) == 1


def test_slow_multiple_chunks_do_not_accumulate_past_total_limit():
    from pc_sourcing.witness_controller import read_profile_body

    timer = [0]
    r = StreamFixture(b"x" * 10, chunk=1, clock=timer, advance=4)
    with pytest.raises(AccessBlocked, match="deadline"):
        read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: timer[0])
    assert len(r.asks) == 4


def test_empty_declared_response_never_reads_body():
    from pc_sourcing.witness_controller import read_profile_body

    r = StreamFixture(b"ignored protocol trailing data", declared=0)
    assert read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: 0) == b""
    assert r.asks == []


def test_unknown_length_at_cap_without_proven_eof_is_refused_without_probe_byte():
    from pc_sourcing.witness_controller import read_profile_body

    r = StreamFixture(b"x" * 1000000)
    r.isclosed = lambda: False
    with pytest.raises(AccessBlocked, match="EOF"):
        read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: 0)
    assert r.cursor == 1000000 and sum(r.asks) == 1000000


def test_open_and_body_share_same_deadline_with_neighbor_success():
    from pc_sourcing.witness_controller import read_profile_body

    timer = [14.0]
    r = StreamFixture(b"abc", declared=3, clock=timer, advance=0.5)
    assert read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: timer[0]) == b"abc"
    timer = [14.0]
    r = StreamFixture(b"abc", declared=3, clock=timer, advance=1.01)
    with pytest.raises(AccessBlocked, match="deadline"):
        read_profile_body(r, byte_limit=1000000, deadline=15, clock=lambda: timer[0])


def test_bounded_transport_worker_success_stays_offline_and_uses_profile(monkeypatch):
    from dataclasses import replace

    import pc_sourcing.witness_controller as m

    profile = replace(PROFILES["tdvat"], byte_limit=16, timeout=1)

    def synthetic_request(p, url, deadline):
        assert p.byte_limit == 16
        return b"SYNTHETIC", {"content-type": "text/html"}

    monkeypatch.setattr(m, "_request_with_profile_limits", synthetic_request)
    body, headers = m.fixed_transport(profile, profile.url)
    assert body == b"SYNTHETIC" and headers["content-type"] == "text/html"


@pytest.mark.parametrize("phase", ["open", "body_read1", "chunked_header_read"])
def test_total_deadline_terminates_blocking_worker_without_surviving_fetch(
    monkeypatch, tmp_path, phase
):
    import multiprocessing
    import time
    from dataclasses import replace

    import pc_sourcing.witness_controller as m

    profile = replace(PROFILES["tdvat"], timeout=0.06)
    late = tmp_path / "would-be-late-read"

    def blocked(p, url, deadline):
        # Simulates blocking DNS/open/header/read1 that drips or never returns.
        time.sleep(0.3)
        late.write_text(phase)
        return b"late", {}

    monkeypatch.setattr(m, "_request_with_profile_limits", blocked)
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(AccessBlocked, match="deadline"):
        m.fixed_transport(profile, profile.url)
    assert time.monotonic() - started < 0.25
    assert {p.pid for p in multiprocessing.active_children()} == before
    time.sleep(0.32)
    assert not late.exists()


@pytest.mark.parametrize("declared", [None, 1200000])
def test_production_transport_streams_with_profile_cap_not_old_default(
    monkeypatch, tmp_path, declared
):
    from dataclasses import replace

    import pc_sourcing.witness_controller as m

    profile = replace(PROFILES["tdvat"], timeout=1)
    log = tmp_path / "read-counts.jsonl"

    class Response(StreamFixture):
        status = 200

        def __init__(self):
            super().__init__(b"x" * 1200000, declared=declared)
            self.headers["content-type"] = "text/html"

        def geturl(self):
            return profile.url

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read1(self, n):
            with log.open("a") as f:
                f.write(str(n) + "\n")
            return super().read1(n)

    class Opener:
        def open(self, request, timeout):
            assert 0 < timeout <= profile.timeout
            return Response()

    monkeypatch.setattr(m, "public_address", lambda _: None)
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(AccessBlocked, match="byte"):
        m.fixed_transport(profile, profile.url)
    counts = [int(n) for n in log.read_text().splitlines()] if log.exists() else []
    assert sum(counts) <= profile.byte_limit
    if declared is not None:
        assert counts == []


def test_exact_profile_stream_in_production_helper_returns_small_safe_headers(monkeypatch):
    from dataclasses import replace

    import pc_sourcing.witness_controller as m

    profile = replace(PROFILES["tdvat"], byte_limit=4, timeout=1)

    class Response(StreamFixture):
        status = 200

        def __init__(self):
            super().__init__(b"abcd", declared=4)
            self.headers["content-type"] = "text/html"
            self.headers["set-cookie"] = "not retained"

        def geturl(self):
            return profile.url

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr(m, "public_address", lambda _: None)
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *_: Opener())
    body, headers = m.fixed_transport(profile, profile.url)
    assert body == b"abcd" and "set-cookie" not in headers


def test_dripping_chunked_response_is_cancelled_at_total_deadline(monkeypatch, tmp_path):
    import multiprocessing
    import time
    from dataclasses import replace

    import pc_sourcing.witness_controller as m

    profile = replace(PROFILES["tdvat"], timeout=0.09)
    late = tmp_path / "late-chunk"

    class Response:
        status = 200
        chunked = True
        headers = {"content-type": "text/html", "transfer-encoding": "chunked"}

        def __init__(self):
            self.chunks = 0

        def geturl(self):
            return profile.url

        def isclosed(self):
            return False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read1(self, n):
            time.sleep(0.025)
            self.chunks += 1
            if self.chunks >= 8:
                late.write_text("dripped beyond total deadline")
            return b"x"

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr(m, "public_address", lambda _: None)
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *_: Opener())
    before = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(AccessBlocked, match="deadline"):
        m.fixed_transport(profile, profile.url)
    assert (
        time.monotonic() - started < 0.3
        and {p.pid for p in multiprocessing.active_children()} == before
    )
    time.sleep(0.25)
    assert not late.exists()


def test_open_time_consumes_body_deadline_in_actual_helper(monkeypatch):
    import time
    from dataclasses import replace

    import pc_sourcing.witness_controller as m

    profile = replace(PROFILES["tdvat"], timeout=0.09)

    class Response(StreamFixture):
        status = 200

        def __init__(self):
            super().__init__(b"abc", declared=3)
            self.headers["content-type"] = "text/html"

        def geturl(self):
            return profile.url

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read1(self, n):
            time.sleep(0.06)
            return super().read1(n)

    class Opener:
        def open(self, request, timeout):
            time.sleep(0.05)
            return Response()

    monkeypatch.setattr(m, "public_address", lambda _: None)
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(AccessBlocked, match="deadline"):
        m.fixed_transport(profile, profile.url)
