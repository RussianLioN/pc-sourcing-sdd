"""Локальный ввод, атомарная запись SQLite и восстанавливаемый отчёт."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime
from html import escape
from pathlib import Path

from pydantic import ValidationError

from pc_sourcing.evaluate import evaluate, utc_time
from pc_sourcing.models import Offer


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


class _OversizedInteger:
    """Маркер числа без преобразования в строковое поле или большой int."""

    __slots__ = ()

    def __repr__(self):
        return "<Целое JSON превышает лимит>"


def _input_rows(raw):
    def reject_constant(value):
        raise ValueError(f"Недопустимая константа JSON: {value}")

    # Соблюдаем текущий предел и ограничиваем работу даже при отключённом извне
    # лимите. Сам маркер не хранит токен: исходный текст сохраняется срезом ниже.
    default_limit = sys.int_info.default_max_str_digits
    digit_limit = min(sys.get_int_max_str_digits() or default_limit, default_limit)

    def parse_integer(value):
        if len(value) - value.startswith("-") > digit_limit:
            return _OversizedInteger()
        return int(value)

    text = raw.decode(json.detect_encoding(raw))
    decoder = json.JSONDecoder(parse_constant=reject_constant, parse_int=parse_integer)
    # Сначала проверяем весь документ, включая разделители и остаток после списка.
    rows = decoder.decode(text)
    if not isinstance(rows, list):
        raise ValueError("Вход JSON должен быть списком предложений")
    whitespace = re.compile(r"[ \t\n\r]*")
    cursor = whitespace.match(text, 0).end() + 1
    for row in rows:
        start = whitespace.match(text, cursor).end()
        _, end = decoder.raw_decode(text, start)
        # Срез сохраняет исходные числовые токены, даже если float переполнился.
        yield row, text[start:end]
        cursor = whitespace.match(text, end).end() + 1


def _fingerprint(raw, as_of):
    root = Path(__file__).resolve().parents[2]
    files = sorted((root / "src/pc_sourcing").glob("*.py")) + [
        root / "specs/001-offline/spec.md",
        root / "specs/001-offline/decision-table.md",
        root / ".specify/memory/constitution.md",
    ]
    digest = hashlib.sha256()
    for part in [raw, as_of.isoformat().encode()] + [
        str(p.relative_to(root)).encode() + b"\0" + p.read_bytes() for p in files
    ]:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _render(run_id, as_of, pairs, rejections):
    # Внешний текст экранируется, чтобы он оставался данными отчёта.
    def literal(value):
        return "<pre>" + escape(str(value)) + "</pre>"

    lines = ["# Отчёт локальной оценки", "", "ТЕСТОВЫЕ данные отмечены для каждой записи."]
    lines += [literal(run_id), f"Время оценки UTC: {as_of.isoformat()}"]
    lines += ["", "## Подтверждённые предложения"]
    lines.extend(literal(o.id) for o, e in pairs if e.eligible)
    for offer, result in pairs:
        lines += [
            "",
            "## Предложение",
            literal(offer.id),
            literal(offer.title),
            "ТЕСТОВЫЕ" if offer.synthetic else "НЕ ТЕСТОВЫЕ: внешние данные",
            literal(offer.url),
            literal(result.label),
            "Оценка (тот же объект, что в SQLite):",
            literal(result.model_dump_json()),
            "Причины:",
        ]
        lines.extend(literal(reason) for reason in result.reasons)
        lines += ["Исходное предложение:", literal(offer.model_dump_json()), "Свидетельства:"]
        for evidence in offer.evidence:
            lines.append(
                literal(
                    f"{evidence.id}: {evidence.field} = {evidence.value}; "
                    f"URL: {evidence.url}; UTC: {utc_time(evidence.observed_at).isoformat()}; "
                    f"origin: {evidence.origin}; offer_id: {evidence.offer_id}; "
                    f"synthetic: {evidence.synthetic}"
                )
            )
    lines += ["", "## Отклонённые входные строки"]
    for index, raw, reason in rejections:
        lines += [f"Индекс входа: {index}", literal(reason), literal(raw)]
    return "\n\n".join(lines) + "\n"


def _schema(con):
    statements = (
        "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
        "as_of TEXT NOT NULL, data TEXT NOT NULL, report TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS offers (run_id TEXT, id TEXT, data TEXT NOT NULL, "
        "PRIMARY KEY(run_id,id), FOREIGN KEY(run_id) REFERENCES runs(run_id))",
        "CREATE TABLE IF NOT EXISTS evaluations (run_id TEXT, offer_id TEXT, data TEXT NOT NULL, "
        "PRIMARY KEY(run_id,offer_id), FOREIGN KEY(run_id,offer_id) REFERENCES offers(run_id,id))",
        "CREATE TABLE IF NOT EXISTS evidence (run_id TEXT, offer_id TEXT, id TEXT, data TEXT NOT NULL, "
        "PRIMARY KEY(run_id,offer_id,id), FOREIGN KEY(run_id,offer_id) REFERENCES offers(run_id,id))",
        "CREATE TABLE IF NOT EXISTS rejections (run_id TEXT, input_index INTEGER, data TEXT NOT NULL, "
        "reason TEXT NOT NULL, PRIMARY KEY(run_id,input_index), "
        "FOREIGN KEY(run_id) REFERENCES runs(run_id))",
    )
    for statement in statements:
        con.execute(statement)


def run(input_path, db_path, report_path, *, as_of, run_id) -> dict:
    as_of = utc_time(as_of)
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id должен быть непустой строкой")
    inp, db, report = (Path(p).resolve() for p in (input_path, db_path, report_path))
    if len({inp, db, report}) != 3 or any(
        a.exists() and b.exists() and a.samefile(b)
        for a, b in ((inp, db), (inp, report), (db, report))
    ):
        raise ValueError("Ввод, база и отчёт должны быть разными файлами")
    raw = inp.read_bytes()
    rows = _input_rows(raw)
    fingerprint = _fingerprint(raw, as_of)
    pairs, rejections, seen = [], [], set()
    for index, (row, serialized) in enumerate(rows):
        row_id = row.get("id") if isinstance(row, dict) else None
        duplicate = isinstance(row_id, str) and row_id in seen
        if isinstance(row_id, str):
            seen.add(row_id)
        try:
            if duplicate:
                raise ValueError(f"Повторный идентификатор: {row_id}")
            offer = Offer.model_validate(row)
        except (ValidationError, ValueError) as exc:
            rejections.append((index, serialized, str(exc)))
        else:
            pairs.append((offer, evaluate(offer, as_of)))
    summary = {
        "run_id": run_id,
        "valid": len(pairs),
        "rejected": len(rejections),
        "eligible": sum(e.eligible for _, e in pairs),
    }
    rendered = _render(run_id, as_of, pairs, rejections)
    staged = None
    con = sqlite3.connect(db)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("BEGIN IMMEDIATE")
        _schema(con)
        existing = con.execute(
            "SELECT fingerprint, data, report FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if existing:
            if existing[0] != fingerprint:
                raise ValueError("fingerprint изменился для существующего run_id")
            summary, rendered = json.loads(existing[1]), existing[2]
        else:
            con.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?)",
                (
                    run_id,
                    fingerprint,
                    as_of.isoformat(),
                    _json(summary),
                    rendered,
                ),
            )
            for offer, result in pairs:
                con.execute(
                    "INSERT INTO offers VALUES (?,?,?)",
                    (
                        run_id,
                        offer.id,
                        offer.model_dump_json(),
                    ),
                )
                con.execute(
                    "INSERT INTO evaluations VALUES (?,?,?)",
                    (
                        run_id,
                        offer.id,
                        result.model_dump_json(),
                    ),
                )
                con.executemany(
                    "INSERT INTO evidence VALUES (?,?,?,?)",
                    [(run_id, offer.id, e.id, e.model_dump_json()) for e in offer.evidence],
                )
            con.executemany(
                "INSERT INTO rejections VALUES (?,?,?,?)",
                [(run_id, index, data, reason) for index, data, reason in rejections],
            )
        # Подготовка отчёта до фиксации: ошибка записи откатывает всю транзакцию.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=report.parent, prefix=".pc-report-", delete=False
        ) as handle:
            staged = Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        con.commit()
        # SQLite — источник истины; после сбоя замены повтор восстанавливает отчёт.
        os.replace(staged, report)
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()
        if staged is not None:
            staged.unlink(missing_ok=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Локальная оценка предложений")
    for name in ("input", "db", "report", "as-of", "run-id"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.input,
            args.db,
            args.report,
            as_of=datetime.fromisoformat(args.as_of),
            run_id=args.run_id,
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    print(_json(result))


if __name__ == "__main__":
    main()
