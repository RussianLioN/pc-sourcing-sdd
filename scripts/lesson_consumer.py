"""Synthetic bootstrap proof tied to a real isolated Git change and bounded recipe."""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from reviewed_lessons import Rejected, checked, encoded, hash_id, read, safe_root

BEFORE = b"def resolve(values):\n    return values[-1]\n"
AFTER = b"def resolve(values):\n    return tuple(dict.fromkeys(values))\n"
COUNTERFACTUAL = {"before": [64, 96], "after": [[96, 64], [64, 96]]}


def limited_file(path, maximum=1_000_000):
    path = safe_root(path)
    if not path.is_file() or path.stat().st_size > maximum:
        raise Rejected("bounded regular file required")
    return path.read_bytes()


def head_oid(repo):
    directory = safe_root(repo / ".git")
    value = limited_file(directory / "HEAD", 256).decode().strip()
    if value.startswith("ref: "):
        name = value[5:]
        if not re.fullmatch(r"refs/heads/[A-Za-z0-9_. /-]+", name) or ".." in name or " " in name:
            raise Rejected("unsupported symbolic HEAD")
        ref = safe_root(directory / name)
        if ref.is_file():
            value = limited_file(ref, 128).decode().strip()
        elif (directory / "packed-refs").is_file():
            values = [
                line.split()
                for line in limited_file(directory / "packed-refs").decode().splitlines()
                if line and not line.startswith(("#", "^"))
            ]
            found = [parts[0] for parts in values if len(parts) == 2 and parts[1] == name]
            if len(found) > 1:
                raise Rejected("ambiguous packed HEAD")
            if not found:
                return None
            value = found[0]
        else:
            return None
    hash_id(value, "git")
    return value


class ObjectView:
    """Git sees only trusted temporary metadata, original objects and a minimal env."""

    def __init__(self, repo):
        self.repo = safe_root(repo)
        self.objects = safe_root(self.repo / ".git" / "objects")
        if not self.objects.is_dir():
            raise Rejected("ordinary local object database required")
        for p in self.objects.rglob("*"):
            if p.is_symlink() or p.name.endswith(".promisor"):
                raise Rejected("symlink/promisor object storage unsupported")
        for name in ["alternates", "http-alternates"]:
            path = self.objects / "info" / name
            if path.exists() and limited_file(path):
                raise Rejected("external object alternates unsupported")
        self.binary = shutil.which("git")
        if not self.binary:
            raise Rejected("installed Git unavailable")

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pc-consumer-object-view-")
        self.directory = Path(self.temp.name)
        (self.directory / "objects").mkdir()
        (self.directory / "refs/heads").mkdir(parents=True)
        (self.directory / "config").write_text(
            "[core]\n repositoryformatversion = 0\n bare = false\n hooksPath = /dev/null\n"
            " fsmonitor = false\n attributesFile = /dev/null\n[commit]\n gpgSign = false\n"
        )
        current = head_oid(self.repo)
        (self.directory / "HEAD").write_text((current or "ref: refs/heads/main") + "\n")
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_OBJECT_DIRECTORY": str(self.objects),
            "GIT_AUTHOR_NAME": "Synthetic Consumer",
            "GIT_COMMITTER_NAME": "Synthetic Consumer",
            "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
            "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
        }
        return self

    def __exit__(self, *_args):
        self.temp.cleanup()

    def run(self, *args, data=None):
        try:
            return subprocess.run(
                [
                    self.binary,
                    "--no-replace-objects",
                    "--git-dir=" + str(self.directory),
                    "--work-tree=" + str(self.repo),
                    *args,
                ],
                input=data,
                capture_output=True,
                check=True,
                timeout=10,
                cwd=self.directory,
                env=self.env,
            ).stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise Rejected("raw original Git object operation unavailable") from exc

    def object(self, oid, kind):
        hash_id(oid, "git")
        description = self.run("cat-file", "--batch-check", data=(oid + "\n").encode()).split()
        if len(description) != 3 or description[:2] != [oid.encode(), kind.encode()]:
            raise Rejected("original object type missing/mismatch")
        size = int(description[2])
        if not 0 <= size <= 1_000_000:
            raise Rejected("original object exceeds bound")
        raw = self.run("cat-file", "--batch", data=(oid + "\n").encode())
        header, separator, payload = raw.partition(b"\n")
        if (
            not separator
            or header.split() != description
            or len(payload) != size + 1
            or payload[-1:] != b"\n"
        ):
            raise Rejected("original object framing/size mismatch")
        value = payload[:-1]
        identity = hashlib.sha1(
            kind.encode() + b" " + str(len(value)).encode() + b"\0" + value
        ).hexdigest()
        if identity != oid:
            raise Rejected("original immutable object hash mismatch")
        return value

    def commit_header(self, oid):
        raw = self.object(oid, "commit")
        headers, separator, _body = raw.partition(b"\n\n")
        if not separator:
            raise Rejected("invalid original commit header")
        trees = [line[5:].decode() for line in headers.splitlines() if line.startswith(b"tree ")]
        parents = [
            line[7:].decode() for line in headers.splitlines() if line.startswith(b"parent ")
        ]
        if len(trees) != 1:
            raise Rejected("original commit requires one tree")
        for value in trees + parents:
            hash_id(value, "git")
        return trees[0], parents

    def tree(self, oid):
        raw, result = self.object(oid, "tree"), {}
        while raw:
            prefix, separator, rest = raw.partition(b"\0")
            if not separator or len(rest) < 20 or b" " not in prefix:
                raise Rejected("invalid original tree framing")
            mode, name = prefix.split(b" ", 1)
            name = name.decode()
            if (
                mode != b"100644"
                or name in result
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name)
            ):
                raise Rejected("unsupported original tree entry")
            result[name] = rest[:20].hex()
            raw = rest[20:]
            if len(result) > 32:
                raise Rejected("bounded original tree required")
        return result


def init_fixture(repo):
    directory = repo / ".git"
    (directory / "objects").mkdir(parents=True)
    (directory / "refs/heads").mkdir(parents=True)
    (directory / "info").mkdir()
    (directory / "HEAD").write_text("ref: refs/heads/main\n")
    (directory / "config").write_text("[core]\n repositoryformatversion = 0\n bare = false\n")


def commit(repo, message):
    # Producer also ignores repository/global config, hooks and attribute/filter programs.
    repo = safe_root(repo)
    files = sorted(p.name for p in repo.iterdir() if p.name != ".git")
    for name in files:
        if name.startswith(".") or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9]+", name):
            raise Rejected("bounded fixture files required")
        limited_file(repo / name)
    if len(files) > 32:
        raise Rejected("bounded fixture file set required")
    with ObjectView(repo) as view:
        view.run("add", "--", *files)
        view.run("commit", "--quiet", "-m", message)
        oid = view.run("rev-parse", "HEAD").decode().strip()
        hash_id(oid, "git")
        safe_root(repo / ".git/index").write_bytes(limited_file(view.directory / "index"))
    safe_root(repo / ".git/HEAD").write_text(oid + "\n")
    return oid


def prove_recipe(before, after):
    # Exact fixed bootstrap recipe only; arbitrary Git/lesson/evidence code is never executed.
    if before != BEFORE or after != AFTER:
        raise Rejected("consumer change does not match bounded conflict-preservation recipe")

    def evaluate(source):
        namespace = {"__builtins__": {"tuple": tuple, "dict": dict}}
        exec(compile(source, "synthetic-reviewed-recipe", "exec"), namespace)
        return [namespace["resolve"]([96, 64]), namespace["resolve"]([64, 96])]

    observed = {"before": evaluate(before), "after": [list(x) for x in evaluate(after)]}
    if observed != COUNTERFACTUAL:
        raise Rejected("meaningful counterfactual failed")
    return observed


def validate_use(store, receipt, external_result_review=None):
    checked(
        receipt,
        {
            "explicit_skill",
            "snapshot_sha256",
            "lesson_sha256",
            "context",
            "applicability",
            "outcome_kind",
            "outcome_path",
            "outcome_sha256",
            "base_commit",
            "resulting_commit",
            "change_repository",
            "synthetic",
        },
    )
    if receipt["explicit_skill"] != "$pc-reviewed-lessons" or receipt["synthetic"] is not True:
        raise Rejected("explicit synthetic bootstrap invocation required")
    for key in ["base_commit", "resulting_commit"]:
        hash_id(receipt[key], "git")
    snapshot = store.search(receipt["context"])
    if (
        receipt["applicability"] != "applicable"
        or snapshot["snapshot_sha256"] != receipt["snapshot_sha256"]
        or receipt["lesson_sha256"] not in {x["lesson_sha256"] for x in snapshot["lessons"]}
    ):
        raise Rejected("not applicable or wrong active snapshot")
    if receipt["outcome_kind"] != "design_decision":
        raise Rejected("MVP requires a substantive change-bound decision, not reused evidence/test")
    repo = safe_root(receipt["change_repository"])
    path = safe_root(receipt["outcome_path"])
    if path != repo / "decision.json":
        raise Rejected("outcome must be the new committed decision in its isolated change")
    hash_id(receipt["outcome_sha256"])
    base, result = receipt["base_commit"], receipt["resulting_commit"]
    with ObjectView(repo) as view:
        base_tree, _base_parents = view.commit_header(base)
        result_tree, parents = view.commit_header(result)
        if head_oid(repo) != result:
            raise Rejected("consumer result must be current actual HEAD")
        if parents != [base]:
            raise Rejected("consumer change must directly follow original recorded baseline")
        before_entries, after_entries = view.tree(base_tree), view.tree(result_tree)
        if set(before_entries) != {"resolver.py"} or set(after_entries) != {
            "decision.json",
            "resolver.py",
        }:
            raise Rejected("new decision and original bounded implementation change required")
        before = view.object(before_entries["resolver.py"], "blob")
        after = view.object(after_entries["resolver.py"], "blob")
        raw = view.object(after_entries["decision.json"], "blob")
        entries = {p.name: p for p in repo.iterdir() if p.name != ".git"}
        if set(entries) != set(after_entries):
            raise Rejected("consumer worktree differs from original committed file set")
        for name, p in entries.items():
            if (
                limited_file(p) != view.object(after_entries[name], "blob")
                or stat.S_IMODE(p.stat().st_mode) & 0o111
            ):
                raise Rejected("consumer worktree differs from original immutable objects")
    if (
        not path.is_file()
        or path.read_bytes() != raw
        or hashlib.sha256(raw).hexdigest() != receipt["outcome_sha256"]
    ):
        raise Rejected("observable outcome missing, changed or uncommitted")
    decision = read(path)
    checked(
        decision,
        {
            "schema_version",
            "synthetic",
            "lesson_sha256",
            "context",
            "decision_id",
            "base_commit",
            "change_path",
            "before_sha256",
            "after_sha256",
            "counterfactual",
        },
    )
    expected = {
        "schema_version": "1.0.0",
        "synthetic": True,
        "lesson_sha256": receipt["lesson_sha256"],
        "context": "declarations",
        "decision_id": "preserve_conflicting_declarations",
        "base_commit": base,
        "change_path": "resolver.py",
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "counterfactual": prove_recipe(before, after),
    }
    if encoded(decision) != encoded(expected) or receipt["context"] != "declarations":
        raise Rejected("substantive decision not bound to actual learned change")
    if external_result_review is not None:
        raise Rejected("writer cannot inject real independent result authority")
    return {
        "status": "BOOTSTRAP_PROOF_ONLY",
        "synthetic": True,
        "outcome_sha256": receipt["outcome_sha256"],
        "actual_base_commit": base,
        "actual_resulting_commit": result,
        "counterfactual": expected["counterfactual"],
        "independent_review": "PENDING",
        "real_learning_enabled": False,
    }


def new_decision(store, context, output):
    snapshot = store.search(context)
    if not snapshot["lessons"]:
        raise Rejected("no applicable active fixture lesson")
    lesson = snapshot["lessons"][0]
    if lesson["lesson_id"] != "conflict" or context != "declarations":
        raise Rejected("consumer recipe not applicable to this lesson")
    output = safe_root(output)
    repo = output.with_name(output.name + ".isolated-change")
    if output.exists() or repo.exists():
        raise Rejected("new observable output required")
    repo.mkdir()
    init_fixture(repo)
    (repo / "resolver.py").write_bytes(BEFORE)
    base = commit(repo, "Synthetic baseline: last declaration hides conflict")
    decision = {
        "schema_version": "1.0.0",
        "synthetic": True,
        "lesson_sha256": lesson["lesson_sha256"],
        "context": context,
        "decision_id": "preserve_conflicting_declarations",
        "base_commit": base,
        "change_path": "resolver.py",
        "before_sha256": hashlib.sha256(BEFORE).hexdigest(),
        "after_sha256": hashlib.sha256(AFTER).hexdigest(),
        "counterfactual": prove_recipe(BEFORE, AFTER),
    }
    (repo / "resolver.py").write_bytes(AFTER)
    path = repo / "decision.json"
    path.write_bytes(encoded(decision))
    result = commit(repo, "Synthetic reviewed lesson: retain both conflicting declarations")
    output.write_text(json.dumps(decision, indent=2) + "\n")
    return {
        "explicit_skill": "$pc-reviewed-lessons",
        "snapshot_sha256": snapshot["snapshot_sha256"],
        "lesson_sha256": lesson["lesson_sha256"],
        "context": context,
        "applicability": "applicable",
        "outcome_kind": "design_decision",
        "outcome_path": str(path),
        "outcome_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "base_commit": base,
        "resulting_commit": result,
        "change_repository": str(repo),
        "synthetic": True,
    }
