"""Accept only real same-snapshot evidence; generate a human-readable pilot summary."""

import argparse
import hashlib
import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from quality import ROOT, snapshot


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(database, evidence):
    def cell(value):
        return escape(str(value)).replace("|", "&#124;").replace("\n", " ")

    with sqlite3.connect(database) as con:
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity failed")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite foreign keys failed")
        records = con.execute(
            "SELECT o.data,e.data FROM offers o JOIN evaluations e "
            "ON o.run_id=e.run_id AND o.id=e.offer_id "
            "WHERE o.run_id=? ORDER BY o.id",
            ("acceptance-pilot",),
        ).fetchall()
        rejected = con.execute(
            "SELECT input_index,data,reason FROM rejections WHERE run_id=? ORDER BY input_index",
            ("acceptance-pilot",),
        ).fetchall()
        stored_run = json.loads(
            con.execute("SELECT data FROM runs WHERE run_id=?", ("acceptance-pilot",)).fetchone()[0]
        )
    pairs = [(json.loads(o), json.loads(e)) for o, e in records]
    if not all(o["synthetic"] and e["synthetic"] for o, e in pairs):
        raise ValueError("Offline acceptance corpus must be explicitly synthetic")
    if len(pairs) != stored_run["valid"] or len(rejected) != stored_run["rejected"]:
        raise ValueError("Stored summary and retained rows disagree")
    if sum(e["eligible"] for _, e in pairs) != stored_run["eligible"]:
        raise ValueError("Stored eligibility and summary disagree")
    lines = [
        "# Результат offline-пилота pc-sourcing-sdd",
        "",
        "**Все предложения ниже — ТЕСТОВЫЕ. Это проверка алгоритма на синтетических данных.**",
        "Реальные цены, наличие и условия покупки здесь не подтверждены. Производственная готовность не заявлена.",
        "",
        "Commit: `" + evidence["snapshot"]["commit"] + "`.",
        "Spec hash: `" + evidence["snapshot"]["spec_hash"] + "`.",
        "Fixtures hash: `" + evidence["snapshot"]["fixtures_hash"] + "`.",
        "",
        f"Сохранено {stored_run['valid']} допустимых и {stored_run['rejected']} отклонённых входных строк. "
        f"По алгоритму подходят {stored_run['eligible']} тестовых предложений.",
        "",
        "Оплата, наличие и eligibility прочитаны из сохранённого Evaluation в SQLite.",
        "Положительный платёжный gate не является гарантией безопасности покупки.",
        "",
        "| Тестовая запись | SKU | Тестовая цена | Наличие | Платёжный gate | Результат |",
        "|---|---|---:|---|---|---|",
    ]
    for offer, result in pairs:
        lines.append(
            "| "
            + " | ".join(
                map(
                    cell,
                    [
                        offer["id"],
                        offer["sku"],
                        f"{offer['price_rub']} {offer['currency']}"
                        if offer["price_rub"] is not None
                        else "неизвестна",
                        offer["stock"],
                        ", ".join(result["passed_routes"])
                        if result["payment_gate_passed"]
                        else "не пройден",
                        result["label"],
                    ],
                )
            )
            + " |"
        )
    lines += ["", "## Причины и происхождение", ""]
    for offer, result in pairs:
        lines += ["### " + cell(offer["id"]), "", cell(result["label"]), ""]
        lines += ["- " + cell(reason) for reason in result["reasons"]]
        lines += ["", "Источники evidence (ТЕСТОВЫЕ):", ""]
        for e in offer["evidence"]:
            lines.append(
                "- "
                + cell(e["id"])
                + ": "
                + cell(e["field"])
                + " = "
                + cell(e["value"])
                + "; "
                + cell(e["origin"])
                + "; "
                + cell(e["observed_at"])
                + "; "
                + cell(e["url"])
            )
        lines += [""]
    lines += ["## Отклонённые входы", ""]
    for index, data, reason in rejected:
        raw = json.loads(data)
        lines += [
            f"- Строка {index}, id="
            + cell(raw.get("id", "unknown") if isinstance(raw, dict) else raw)
            + ": "
            + cell(reason)
        ]
    lines += [
        "",
        "## Ограничения",
        "",
        "- Live-источники blocked: локальный Tavily-доступ не настроен; прямой Avito-доступ ранее запрещён.",
        "- Recovery Spec Kit из running после смерти координатора blocked; paused/failed resume проверены отдельно.",
        "- Два одновременных writers, fan-out/fan-in, Converge и 24/7 deployment не испытывались.",
        "- Сумма денежных затрат не измерялась; новый платный API, ключ или подписка не создавались.",
        "",
        "Полный audit-отчёт: [report.md](report.md); БД: [pilot.sqlite](pilot.sqlite).",
        "",
    ]
    return "\n".join(lines), stored_run


def finalize(out, review_path):
    out, review_path = Path(out).resolve(), Path(review_path).resolve()
    evidence = json.loads((out / "manifest.json").read_text())
    review = json.loads(review_path.read_text())
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if dirty or evidence["snapshot"] != snapshot() or not evidence["unchanged_during_checks"]:
        raise ValueError("snapshot changed; acceptance invalidated")
    if evidence["status"] != "passed" or any(c["exit_code"] != 0 for c in evidence["checks"]):
        raise ValueError("required quality checks failed")
    worker = json.loads((review_path.parent / "result.json").read_text())
    if (
        worker.get("kind") != "real_codex_exec"
        or worker["mode"] != "verifier"
        or worker["exit_code"] != 0
    ):
        raise ValueError("independent review is not a successful actual Codex verifier")
    if worker["project_access"] != "read-only":
        raise ValueError("verifier project was writable")
    if review["verdict"] != "passed" or review["commit"] != evidence["snapshot"]["commit"]:
        raise ValueError("independent verifier did not pass the same commit")
    for required in (
        "verify_readonly.py",
        "-m pytest",
        "ruff check",
        "ruff format",
        "verify_scope.py",
    ):
        if not any(required in c["command"] and c["exit_code"] == 0 for c in review["checks"]):
            raise ValueError("independent required check missing: " + required)
    scope_cmd = [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/verify_scope.py"),
        str(ROOT / "tasks/T002.json"),
        str(ROOT),
    ]
    scope = subprocess.run(scope_cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
    (out / "scope.json").write_text(scope.stdout + scope.stderr)
    if scope.returncode != 0:
        raise ValueError("common snapshot scope check failed")
    readable, stored = summary(out / "pilot.sqlite", evidence)
    (out / "summary.md").write_text(readable)
    evidence.update(
        independent_review=review,
        independent_review_path=str(review_path),
        accepted_at=datetime.now(UTC).isoformat(),
        accepted_scope="offline pilot only",
        pilot_result=stored,
        coordinator_scope={"command": scope_cmd, "exit_code": 0},
        production_ready=False,
        repair_rounds=2,
        new_paid_api=False,
        next_step="resolve a lawful local primary-source route and budget before any live collection",
        blocked=[
            "local live data authorization",
            "Avito direct access",
            "Spec Kit running-state recovery",
        ],
        not_run=[
            "two simultaneous writers",
            "fan-out/fan-in and loops",
            "Converge command",
            "live primary-source smoke",
            "24/7 deployment",
        ],
    )
    checked = [
        out / n for n in ("pilot.sqlite", "report.md", "summary.md", "tests.xml", "scope.json")
    ]
    checked += [
        review_path,
        review_path.parent / "invocation.json",
        review_path.parent / "result.json",
    ]
    evidence["artifact_hashes"] = {str(p): sha(p) for p in checked}
    (out / "manifest.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "passed",
                "scope": "offline pilot only",
                "snapshot": evidence["snapshot"],
                "report": str(out / "summary.md"),
            }
        )
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artifacts/acceptance"))
    ap.add_argument("--review", required=True)
    args = ap.parse_args()
    finalize(args.out, args.review)
