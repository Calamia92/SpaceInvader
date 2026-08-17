from __future__ import annotations

import csv
import hashlib
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


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
    loaded_rows = 0
    problem_rows: list[ProblemRow] = []

    with path.open(newline="", encoding="utf-8", errors="replace") as file:
        reader = csv.reader(file)
        for line_number, row in enumerate(reader, start=1):
            if len(row) == len(HEADERS):
                loaded_rows += 1
                continue

            problem_rows.append(
                ProblemRow(
                    line_number=line_number,
                    field_count=len(row),
                    raw_fields=row,
                )
            )

    return PhaseOneResult(
        total_rows=loaded_rows + len(problem_rows),
        loaded_rows=loaded_rows,
        problem_rows=problem_rows,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
