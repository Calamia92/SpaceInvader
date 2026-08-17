from __future__ import annotations

import csv
import hashlib
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DATA_URL = (
    "https://raw.githubusercontent.com/planetsig/ufo-reports/"
    "c0915f18186e5e2227083702049a838258001a2a/"
    "csv-data/ufo-complete-geocoded-time-standardized.csv"
)
DATA_DIR = Path("data")
DATA_PATH = DATA_DIR / "releves_klaxo3.csv"
EXPECTED_SHA256 = "6cdc2d8014c6308517956236cdd059c14af6b19b4be5e6698977583cfd7b85f9"

HEADERS = [
    "datetime",
    "city",
    "state",
    "country",
    "shape",
    "duration_seconds",
    "duration_hours_min",
    "comments",
    "date_posted",
    "latitude",
    "longitude",
]


@dataclass(frozen=True)
class ProblemRow:
    line_number: int
    field_count: int
    raw_fields: list[str]


@dataclass(frozen=True)
class PhaseOneResult:
    total_rows: int
    loaded_rows: int
    problem_rows: list[ProblemRow]


@dataclass(frozen=True)
class ConversionIssue:
    field: str
    line_number: int
    value: str
    reason: str


@dataclass(frozen=True)
class PhaseTwoResult:
    typed_rows: list[dict[str, Any]]
    issues: list[ConversionIssue]


@dataclass(frozen=True)
class PhaseThreeResult:
    hoax_count: int
    total_rows: int
    proportion: float
    examples: list[dict[str, Any]]


def download_data_if_missing(path: Path = DATA_PATH) -> None:
    if path.exists() and path.stat().st_size > 0:
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".part")

    try:
        with urllib.request.urlopen(DATA_URL, timeout=60) as response:
            tmp_path.write_bytes(response.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Impossible de telecharger la transmission: {exc}") from exc

    tmp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_phase_one(path: Path = DATA_PATH) -> PhaseOneResult:
    loaded_rows: list[dict[str, str | int]] = []
    problem_rows: list[ProblemRow] = []

    with path.open(newline="", encoding="utf-8", errors="replace") as file:
        reader = csv.reader(file)
        for line_number, row in enumerate(reader, start=1):
            if len(row) == len(HEADERS):
                loaded = dict(zip(HEADERS, row, strict=True))
                loaded["_line_number"] = line_number
                loaded_rows.append(loaded)
                continue

            problem_rows.append(
                ProblemRow(
                    line_number=line_number,
                    field_count=len(row),
                    raw_fields=row,
                )
            )

    return PhaseOneResult(
        total_rows=len(loaded_rows) + len(problem_rows),
        loaded_rows=len(loaded_rows),
        problem_rows=problem_rows,
    )


def load_well_formed_rows(path: Path = DATA_PATH) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []

    with path.open(newline="", encoding="utf-8", errors="replace") as file:
        reader = csv.reader(file)
        for line_number, row in enumerate(reader, start=1):
            if len(row) != len(HEADERS):
                continue

            loaded = dict(zip(HEADERS, row, strict=True))
            loaded["_line_number"] = line_number
            rows.append(loaded)

    return rows


def parse_observation_datetime(value: str) -> tuple[datetime | None, str | None]:
    try:
        return datetime.strptime(value, "%m/%d/%Y %H:%M"), None
    except ValueError:
        pass

    if value.endswith(" 24:00"):
        date_part = value.removesuffix(" 24:00")
        try:
            normalized = datetime.strptime(date_part, "%m/%d/%Y") + timedelta(days=1)
            return normalized, "heure 24:00 normalisee au lendemain 00:00"
        except ValueError:
            return None, "date invalide"

    return None, "date/heure invalide"


def parse_posted_date(value: str) -> tuple[datetime | None, str | None]:
    try:
        return datetime.strptime(value, "%m/%d/%Y"), None
    except ValueError:
        return None, "date invalide"


def parse_float(value: str) -> tuple[float | None, str | None]:
    if value == "":
        return None, "valeur vide"

    try:
        return float(value), None
    except ValueError:
        return None, "nombre invalide"


def convert_phase_two(rows: list[dict[str, str | int]]) -> PhaseTwoResult:
    typed_rows: list[dict[str, Any]] = []
    issues: list[ConversionIssue] = []

    for row in rows:
        line_number = int(row["_line_number"])
        typed: dict[str, Any] = {"_line_number": line_number}

        for field in ["city", "state", "country", "shape", "duration_hours_min", "comments"]:
            typed[field] = row[field]

        for field in ["duration_seconds", "latitude", "longitude"]:
            value = str(row[field])
            parsed, reason = parse_float(value)
            typed[field] = parsed
            if reason is not None:
                issues.append(ConversionIssue(field, line_number, value, reason))

        observed_at, reason = parse_observation_datetime(str(row["datetime"]))
        typed["datetime"] = observed_at
        if reason is not None:
            issues.append(ConversionIssue("datetime", line_number, str(row["datetime"]), reason))

        posted_at, reason = parse_posted_date(str(row["date_posted"]))
        typed["date_posted"] = posted_at
        if reason is not None:
            issues.append(ConversionIssue("date_posted", line_number, str(row["date_posted"]), reason))

        typed_rows.append(typed)

    return PhaseTwoResult(typed_rows=typed_rows, issues=issues)


HOAX_PATTERN = re.compile(r"\bhoax(?:es|ed)?\b", re.IGNORECASE)


def is_hoax_from_comment(comment: str) -> bool:
    return HOAX_PATTERN.search(comment) is not None


def label_phase_three(rows: list[dict[str, Any]]) -> PhaseThreeResult:
    examples: list[dict[str, Any]] = []
    hoax_count = 0

    for row in rows:
        row["is_hoax"] = is_hoax_from_comment(str(row["comments"]))
        if row["is_hoax"]:
            hoax_count += 1
            if len(examples) < 3:
                examples.append(row)

    total_rows = len(rows)
    proportion = hoax_count / total_rows if total_rows else 0.0
    return PhaseThreeResult(
        hoax_count=hoax_count,
        total_rows=total_rows,
        proportion=proportion,
        examples=examples,
    )


def print_phase_one(result: PhaseOneResult) -> None:
    print("Phase 1 - Ouvrir la caisse")
    print(f"Lignes contenues dans le fichier : {result.total_rows}")
    print(f"Lignes chargees normalement : {result.loaded_rows}")
    print(f"Lignes traitees a part : {len(result.problem_rows)}")

    if result.problem_rows:
        first_problem = result.problem_rows[0]
        print()
        print("Premiere ligne problematique :")
        print(f"- ligne : {first_problem.line_number}")
        print(f"- nombre de champs : {first_problem.field_count}")
        print(f"- champs : {first_problem.raw_fields}")


def print_phase_two(result: PhaseTwoResult) -> None:
    print()
    print("Phase 2 - Rien n'est du bon type")

    converted_fields = ["duration_seconds", "latitude", "longitude", "datetime", "date_posted"]
    for field in converted_fields:
        field_issues = [issue for issue in result.issues if issue.field == field]
        print(f"{field} : {len(field_issues)} valeur(s) signalee(s)")

        examples: list[ConversionIssue] = []
        seen: set[tuple[str, str]] = set()
        for issue in field_issues:
            key = (issue.value, issue.reason)
            if key in seen:
                continue
            seen.add(key)
            examples.append(issue)
            if len(examples) == 3:
                break

        for issue in examples:
            print(f"  - ligne {issue.line_number}: {issue.value!r} ({issue.reason})")


def print_phase_three(result: PhaseThreeResult) -> None:
    print()
    print("Phase 3 - Le Conseil veut trier les canulars")
    print("Regle : le commentaire contient le mot 'hoax'.")
    print(f"Canulars marques : {result.hoax_count} / {result.total_rows}")
    print(f"Proportion : {result.proportion:.3%}")

    if result.examples:
        print("Exemples :")
        for row in result.examples:
            comment = str(row["comments"])
            print(f"  - ligne {row['_line_number']}: {comment[:120]}")


def main() -> int:
    download_data_if_missing()

    actual_sha256 = sha256_file(DATA_PATH)
    if actual_sha256 != EXPECTED_SHA256:
        print(
            "Attention: le hash SHA-256 du fichier local ne correspond pas au fichier attendu.",
            file=sys.stderr,
        )
        print(f"Attendu : {EXPECTED_SHA256}", file=sys.stderr)
        print(f"Obtenu  : {actual_sha256}", file=sys.stderr)

    phase_one = load_phase_one()
    print_phase_one(phase_one)

    well_formed_rows = load_well_formed_rows()
    phase_two = convert_phase_two(well_formed_rows)
    print_phase_two(phase_two)

    phase_three = label_phase_three(phase_two.typed_rows)
    print_phase_three(phase_three)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
