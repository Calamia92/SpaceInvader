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


@dataclass(frozen=True)
class PhaseFourResult:
    model_name: str
    used_columns: list[str]
    train_size: int
    test_size: int
    test_hoax_count: int
    predicted_hoax_count: int
    recall: float
    precision: float
    accuracy: float
    test_line_examples: list[int]


@dataclass(frozen=True)
class ColumnAudit:
    column: str
    writer: str
    moment: str
    knew_hoax_already: bool


@dataclass(frozen=True)
class PhaseFiveResult:
    column_audit: list[ColumnAudit]
    before: PhaseFourResult
    after: PhaseFourResult


@dataclass(frozen=True)
class PhaseSixResult:
    intern_accuracy: float
    real_model_accuracy: float
    intern_recall: float
    intern_precision: float
    real_model_recall: float
    real_model_precision: float


@dataclass(frozen=True)
class PhaseSevenResult:
    event_columns: list[str]
    multi_witness_event_count: int
    largest_event_witness_count: int
    random_split_crossed_event_count: int
    random_split_crossed_row_count: int
    duplicate_comment_group_count: int
    duplicate_comment_row_count: int
    duplicate_comment_same_event_group_count: int
    before: PhaseFourResult
    after: PhaseFourResult
    corrected_before: PhaseFourResult
    corrected_after: PhaseFourResult
    largest_event_rows: list[dict[str, Any]]
    largest_event_side: str


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
MODEL_RANDOM_STATE = 42
TEST_SIZE = 0.25


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


def row_to_text(row: dict[str, Any], columns: list[str]) -> str:
    values: list[str] = []
    for column in columns:
        value = row.get(column)
        if isinstance(value, datetime):
            value = value.isoformat(sep=" ")
        values.append(f"{column}={'' if value is None else value}")
    return " | ".join(values)


def random_split_indices(rows: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    from sklearn.model_selection import train_test_split

    indices = list(range(len(rows)))
    labels = [int(row["is_hoax"]) for row in rows]
    train_indices, test_indices = train_test_split(
        indices,
        test_size=TEST_SIZE,
        random_state=MODEL_RANDOM_STATE,
        stratify=labels,
    )
    return list(train_indices), list(test_indices)


def train_classifier_on_indices(
    rows: list[dict[str, Any]],
    used_columns: list[str],
    train_indices: list[int],
    test_indices: list[int],
) -> PhaseFourResult:
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    from sklearn.pipeline import Pipeline

    features = [row_to_text(row, used_columns) for row in rows]
    labels = [int(row["is_hoax"]) for row in rows]
    line_numbers = [int(row["_line_number"]) for row in rows]
    features_train = [features[index] for index in train_indices]
    features_test = [features[index] for index in test_indices]
    labels_train = [labels[index] for index in train_indices]
    labels_test = [labels[index] for index in test_indices]
    lines_test = [line_numbers[index] for index in test_indices]

    model = Pipeline(
        [
            (
                "vectorizer",
                CountVectorizer(
                    lowercase=True,
                    token_pattern=r"(?u)\b\w+\b",
                    ngram_range=(1, 2),
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=500,
                    solver="liblinear",
                    random_state=MODEL_RANDOM_STATE,
                ),
            ),
        ]
    )
    model.fit(features_train, labels_train)
    predictions = model.predict(features_test)

    return PhaseFourResult(
        model_name="CountVectorizer + LogisticRegression",
        used_columns=used_columns,
        train_size=len(labels_train),
        test_size=len(labels_test),
        test_hoax_count=sum(labels_test),
        predicted_hoax_count=int(sum(predictions)),
        recall=recall_score(labels_test, predictions, zero_division=0),
        precision=precision_score(labels_test, predictions, zero_division=0),
        accuracy=accuracy_score(labels_test, predictions),
        test_line_examples=sorted(lines_test[:10]),
    )


def train_classifier(rows: list[dict[str, Any]], used_columns: list[str]) -> PhaseFourResult:
    train_indices, test_indices = random_split_indices(rows)
    return train_classifier_on_indices(rows, used_columns, train_indices, test_indices)


def train_phase_four(rows: list[dict[str, Any]]) -> PhaseFourResult:
    return train_classifier(rows, ["comments"])


def train_phase_five(rows: list[dict[str, Any]], before: PhaseFourResult) -> PhaseFiveResult:
    column_audit = [
        ColumnAudit(
            column="comments",
            writer="temoin puis note editoriale du Bureau",
            moment="recit initial puis traitement du dossier",
            knew_hoax_already=True,
        ),
        ColumnAudit(
            column="datetime",
            writer="temoin",
            moment="au moment du signalement",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="city",
            writer="temoin",
            moment="au moment du signalement",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="state",
            writer="temoin ou formulaire",
            moment="au moment du signalement",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="country",
            writer="temoin ou formulaire",
            moment="au moment du signalement",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="shape",
            writer="temoin",
            moment="au moment du signalement",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="duration_seconds",
            writer="service de normalisation",
            moment="apres saisie de la duree",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="duration_hours_min",
            writer="temoin",
            moment="au moment du signalement",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="latitude",
            writer="capteur ou geocodage",
            moment="avant l'analyse du dossier",
            knew_hoax_already=False,
        ),
        ColumnAudit(
            column="longitude",
            writer="capteur ou geocodage",
            moment="avant l'analyse du dossier",
            knew_hoax_already=False,
        ),
    ]
    allowed_columns = [
        audit.column
        for audit in column_audit
        if not audit.knew_hoax_already and audit.column != "date_posted"
    ]

    return PhaseFiveResult(
        column_audit=column_audit,
        before=before,
        after=train_classifier(rows, allowed_columns),
    )


def score_phase_six(rows: list[dict[str, Any]], real_model: PhaseFourResult) -> PhaseSixResult:
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    from sklearn.model_selection import train_test_split

    labels = [int(row["is_hoax"]) for row in rows]
    _labels_train, labels_test = train_test_split(
        labels,
        test_size=TEST_SIZE,
        random_state=MODEL_RANDOM_STATE,
        stratify=labels,
    )
    intern_predictions = [0] * len(labels_test)

    return PhaseSixResult(
        intern_accuracy=accuracy_score(labels_test, intern_predictions),
        real_model_accuracy=real_model.accuracy,
        intern_recall=recall_score(labels_test, intern_predictions, zero_division=0),
        intern_precision=precision_score(labels_test, intern_predictions, zero_division=0),
        real_model_recall=real_model.recall,
        real_model_precision=real_model.precision,
    )


def normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def event_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    observed_at = row.get("datetime")
    observed_date = observed_at.date().isoformat() if isinstance(observed_at, datetime) else "date_inconnue"
    return (
        observed_date,
        normalized_text(row.get("city")),
        normalized_text(row.get("state")),
        normalized_text(row.get("country")),
    )


def group_split_indices(rows: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    from sklearn.model_selection import GroupShuffleSplit

    indices = list(range(len(rows)))
    labels = [int(row["is_hoax"]) for row in rows]
    groups = ["|".join(event_key(row)) for row in rows]
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=TEST_SIZE,
        random_state=MODEL_RANDOM_STATE,
    )
    train_indices, test_indices = next(splitter.split(indices, labels, groups))
    return list(train_indices), list(test_indices)


def count_crossed_events(
    rows: list[dict[str, Any]],
    train_indices: list[int],
    test_indices: list[int],
) -> tuple[int, int]:
    train_set = set(train_indices)
    test_set = set(test_indices)
    event_to_indices: dict[tuple[str, str, str, str], list[int]] = {}

    for index, row in enumerate(rows):
        event_to_indices.setdefault(event_key(row), []).append(index)

    crossed_events = 0
    crossed_rows = 0
    for indices in event_to_indices.values():
        if len(indices) < 2:
            continue
        in_train = any(index in train_set for index in indices)
        in_test = any(index in test_set for index in indices)
        if in_train and in_test:
            crossed_events += 1
            crossed_rows += len(indices)

    return crossed_events, crossed_rows


def count_duplicate_comments(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    from collections import Counter, defaultdict

    comments = [str(row.get("comments", "")).strip() for row in rows]
    global_counts = Counter(comment for comment in comments if comment)
    duplicate_group_count = sum(1 for count in global_counts.values() if count > 1)
    duplicate_row_count = sum(count for count in global_counts.values() if count > 1)

    event_comment_counts: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        comment = str(row.get("comments", "")).strip()
        if comment:
            event_comment_counts[event_key(row)][comment] += 1

    same_event_duplicate_group_count = sum(
        1
        for counter in event_comment_counts.values()
        for count in counter.values()
        if count > 1
    )
    return duplicate_group_count, duplicate_row_count, same_event_duplicate_group_count


CORRECTED_MODEL_COLUMNS = [
    "datetime",
    "city",
    "state",
    "country",
    "shape",
    "duration_seconds",
    "duration_hours_min",
    "latitude",
    "longitude",
]


def train_phase_seven(
    rows: list[dict[str, Any]],
    before: PhaseFourResult,
    corrected_before: PhaseFourResult,
) -> PhaseSevenResult:
    from collections import defaultdict

    event_to_indices: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        event_to_indices[event_key(row)].append(index)

    multi_witness_events = [indices for indices in event_to_indices.values() if len(indices) > 1]
    largest_event_indices = max(event_to_indices.values(), key=len)

    random_train_indices, random_test_indices = random_split_indices(rows)
    crossed_events, crossed_rows = count_crossed_events(rows, random_train_indices, random_test_indices)

    group_train_indices, group_test_indices = group_split_indices(rows)
    after = train_classifier_on_indices(rows, ["comments"], group_train_indices, group_test_indices)
    corrected_after = train_classifier_on_indices(
        rows,
        CORRECTED_MODEL_COLUMNS,
        group_train_indices,
        group_test_indices,
    )
    group_test_set = set(group_test_indices)
    largest_event_side = "test" if largest_event_indices[0] in group_test_set else "apprentissage"

    (
        duplicate_comment_group_count,
        duplicate_comment_row_count,
        duplicate_comment_same_event_group_count,
    ) = count_duplicate_comments(rows)

    return PhaseSevenResult(
        event_columns=["datetime.date", "city", "state", "country"],
        multi_witness_event_count=len(multi_witness_events),
        largest_event_witness_count=len(largest_event_indices),
        random_split_crossed_event_count=crossed_events,
        random_split_crossed_row_count=crossed_rows,
        duplicate_comment_group_count=duplicate_comment_group_count,
        duplicate_comment_row_count=duplicate_comment_row_count,
        duplicate_comment_same_event_group_count=duplicate_comment_same_event_group_count,
        before=before,
        after=after,
        corrected_before=corrected_before,
        corrected_after=corrected_after,
        largest_event_rows=[rows[index] for index in largest_event_indices],
        largest_event_side=largest_event_side,
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


def print_phase_four(result: PhaseFourResult) -> None:
    print()
    print("Phase 4 - Le premier verdict")
    print(f"Modele : {result.model_name}")
    print(f"Colonnes utilisees : {', '.join(result.used_columns)}")
    print(f"Apprentissage : {result.train_size} releves")
    print(f"Test jamais vu : {result.test_size} releves")
    print(f"Canulars reels dans le test : {result.test_hoax_count}")
    print(f"Signalements marques par le modele : {result.predicted_hoax_count}")
    print(f"Canulars attrapes sur 100 canulars reels : {result.recall * 100:.1f}")
    print(f"Vrais canulars sur 100 signalements marques : {result.precision * 100:.1f}")
    print(f"Taux de bonnes reponses : {result.accuracy * 100:.2f}%")
    print(f"Exemples de lignes du jeu de test : {result.test_line_examples}")


def print_phase_five(result: PhaseFiveResult) -> None:
    print()
    print("Phase 5 - Le Conseil ne vous croit pas")
    print("Audit des colonnes :")
    for audit in result.column_audit:
        answer = "oui" if audit.knew_hoax_already else "non"
        print(f"  - {audit.column}: {audit.writer}, {audit.moment}, savait deja ? {answer}")

    print("Scores avant / apres retrait des colonnes interdites :")
    print(
        f"  - avant : rappel {result.before.recall * 100:.1f}, "
        f"precision {result.before.precision * 100:.1f}"
    )
    print(
        f"  - apres : rappel {result.after.recall * 100:.1f}, "
        f"precision {result.after.precision * 100:.1f}"
    )


def print_phase_six(result: PhaseSixResult) -> None:
    print()
    print("Phase 6 - Le modele le plus bete du Bureau")
    print(f"Taux de bonnes reponses du stagiaire : {result.intern_accuracy * 100:.2f}%")
    print(f"Taux de bonnes reponses du vrai modele : {result.real_model_accuracy * 100:.2f}%")
    print(f"Rappel canular du stagiaire : {result.intern_recall * 100:.1f}")
    print(f"Rappel canular du vrai modele : {result.real_model_recall * 100:.1f}")
    print(f"Precision canular du stagiaire : {result.intern_precision * 100:.1f}")
    print(f"Precision canular du vrai modele : {result.real_model_precision * 100:.1f}")


def print_phase_seven(result: PhaseSevenResult) -> None:
    print()
    print("Phase 7 - Plusieurs temoins, un seul evenement")
    print(f"Colonnes de regroupement : {', '.join(result.event_columns)}")
    print(f"Evenements avec plusieurs temoins : {result.multi_witness_event_count}")
    print(f"Temoins dans le plus gros evenement : {result.largest_event_witness_count}")
    print(f"Evenements coupes dans l'ancienne decoupe : {result.random_split_crossed_event_count}")
    print(f"Releves a cheval dans l'ancienne decoupe : {result.random_split_crossed_row_count}")
    print(
        "Commentaires recopies exactement : "
        f"{result.duplicate_comment_group_count} groupes, {result.duplicate_comment_row_count} releves"
    )
    print(
        "Commentaires recopies exactement dans un meme evenement : "
        f"{result.duplicate_comment_same_event_group_count} groupes"
    )
    print("Scores phase 4 avant / apres decoupe par evenement :")
    print(f"  - avant : rappel {result.before.recall * 100:.1f}, precision {result.before.precision * 100:.1f}")
    print(f"  - apres : rappel {result.after.recall * 100:.1f}, precision {result.after.precision * 100:.1f}")
    print("Scores du modele corrige avant / apres decoupe par evenement :")
    print(
        f"  - avant : rappel {result.corrected_before.recall * 100:.1f}, "
        f"precision {result.corrected_before.precision * 100:.1f}"
    )
    print(
        f"  - apres : rappel {result.corrected_after.recall * 100:.1f}, "
        f"precision {result.corrected_after.precision * 100:.1f}"
    )
    print(f"Plus gros evenement, cote {result.largest_event_side} :")
    for row in result.largest_event_rows:
        print(
            f"  - ligne {row['_line_number']}: {row['datetime']} | "
            f"{row['city']} | {row['state']} | {row['country']} | {str(row['comments'])[:80]}"
        )


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

    phase_four = train_phase_four(phase_two.typed_rows)
    print_phase_four(phase_four)

    phase_five = train_phase_five(phase_two.typed_rows, phase_four)
    print_phase_five(phase_five)

    phase_six = score_phase_six(phase_two.typed_rows, phase_five.after)
    print_phase_six(phase_six)

    phase_seven = train_phase_seven(phase_two.typed_rows, phase_four, phase_five.after)
    print_phase_seven(phase_seven)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
