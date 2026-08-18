from __future__ import annotations

import csv
import hashlib
import math
import random
import statistics
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


@dataclass(frozen=True)
class PhaseEightResult:
    split_date_column: str
    cutoff_date: str
    train_size: int
    test_size: int
    train_hoax_proportion: float
    test_hoax_proportion: float
    phase_four_temporal: PhaseFourResult
    corrected_temporal: PhaseFourResult


@dataclass(frozen=True)
class MissingColumnStats:
    column: str
    missing_count: int
    filled_count: int
    missing_hoax_proportion: float
    filled_hoax_proportion: float


@dataclass(frozen=True)
class PhaseNineResult:
    top_columns: list[MissingColumnStats]
    treatment: str


@dataclass(frozen=True)
class PhaseTenResult:
    split_name: str
    train_hoax_proportion: float
    test_hoax_proportion: float
    corrected_result: PhaseFourResult
    single_prediction: int
    single_prediction_label: str
    single_report_text: str


@dataclass(frozen=True)
class LongDurationExample:
    line_number: int
    duration_seconds: float
    duration_text: str
    comments: str


@dataclass(frozen=True)
class DurationConflictExample:
    line_number: int
    numeric_seconds: float | None
    text_seconds: float | None
    duration_text: str


@dataclass(frozen=True)
class PhaseElevenResult:
    unusable_count: int
    conflict_count: int
    median_seconds: float
    longer_than_day_count: int
    longest_examples: list[LongDurationExample]
    conflict_examples: list[DurationConflictExample]


@dataclass(frozen=True)
class PhaseTwelveResult:
    before_width: int
    after_width: int
    city_rule: str
    shape_rule: str
    singleton_city_count: int
    kept_city_count: int
    raw_shape_count: int
    normalized_shape_count: int
    distance_23_to_0: float
    distance_23_to_20: float
    recall: float
    precision: float


@dataclass(frozen=True)
class PhaseTwelveModelData:
    before_width: int
    after_width: int
    city_rule: str
    shape_rule: str
    singleton_city_count: int
    kept_city_count: int
    raw_shape_count: int
    normalized_shape_count: int
    distance_23_to_0: float
    distance_23_to_20: float
    labels: list[int]
    probabilities: list[float]
    predictions: list[int]


@dataclass(frozen=True)
class ThresholdCost:
    threshold: float
    false_negative_count: int
    false_positive_count: int
    cost: int


@dataclass(frozen=True)
class PhaseThirteenResult:
    cost_table: list[ThresholdCost]
    selected: ThresholdCost
    default: ThresholdCost
    saved_credits: int


@dataclass(frozen=True)
class ProbabilityOutput:
    labels: list[int]
    probabilities: list[float]
    predictions: list[int]
    feature_count: int


@dataclass(frozen=True)
class CalibrationBin:
    label: str
    count: int
    mean_probability: float
    observed_proportion: float


@dataclass(frozen=True)
class PhaseFourteenResult:
    raw_bins: list[CalibrationBin]
    calibrated_bins: list[CalibrationBin]
    correction_method: str
    error_direction: str
    base_train_size: int
    calibration_size: int
    test_size: int


@dataclass(frozen=True)
class MetricInterval:
    minimum: float
    mean: float
    maximum: float


@dataclass(frozen=True)
class SplitMetric:
    test_size: int
    test_hoax_count: int
    recall: float
    precision: float


@dataclass(frozen=True)
class PhaseFifteenResult:
    split_count: int
    temporal_test_size: int
    temporal_test_hoax_count: int
    repeated_test_size: int
    repeated_test_hoax_count: int
    recall_interval: MetricInterval
    precision_interval: MetricInterval
    analyst_first: float
    analyst_second: float
    analyst_gap: float
    answer: str


@dataclass(frozen=True)
class TrainedPhaseTwelveModel:
    vectorizer: Any
    classifier: Any
    frequent_cities: set[str]
    frequent_shapes: set[str]
    test_indices: list[int]
    labels: list[int]
    probabilities: list[float]
    predictions: list[int]
    feature_count: int


@dataclass(frozen=True)
class LocalContribution:
    feature: str
    contribution: float


@dataclass(frozen=True)
class ExplainedReport:
    role: str
    line_number: int
    probability: float
    true_label: int
    predicted_label: int
    summary: str
    positive_reasons: list[LocalContribution]
    negative_reasons: list[LocalContribution]


@dataclass(frozen=True)
class ColumnImportance:
    column: str
    baseline_score: float
    shuffled_score: float
    drop: float


@dataclass(frozen=True)
class PhaseSixteenResult:
    threshold_used_for_explanations: float
    threshold_note: str
    reports: list[ExplainedReport]
    importances: list[ColumnImportance]
    surprising_column_note: str


@dataclass(frozen=True)
class ZonePerformance:
    zone: str
    row_count: int
    hoax_count: int
    hoax_proportion: float
    predicted_count: int
    recall: float
    precision: float
    default_cost: int
    best_threshold: float
    best_cost: int


@dataclass(frozen=True)
class PhaseSeventeenResult:
    threshold_used_for_scores: float
    zones: list[ZonePerformance]
    decision: str
    caution: str


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
MISSING_MARKER = "__missing__"


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
        if value is None or str(value).strip() == "":
            value = MISSING_MARKER
        values.append(f"{column}={value}")
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


def build_model() -> Any:
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline(
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


def fit_model_on_indices(
    rows: list[dict[str, Any]],
    used_columns: list[str],
    train_indices: list[int],
) -> Any:
    features = [row_to_text(row, used_columns) for row in rows]
    labels = [int(row["is_hoax"]) for row in rows]
    features_train = [features[index] for index in train_indices]
    labels_train = [labels[index] for index in train_indices]

    model = build_model()
    model.fit(features_train, labels_train)
    return model


def train_classifier_on_indices(
    rows: list[dict[str, Any]],
    used_columns: list[str],
    train_indices: list[int],
    test_indices: list[int],
) -> PhaseFourResult:
    from sklearn.metrics import accuracy_score, precision_score, recall_score

    features = [row_to_text(row, used_columns) for row in rows]
    labels = [int(row["is_hoax"]) for row in rows]
    line_numbers = [int(row["_line_number"]) for row in rows]
    features_test = [features[index] for index in test_indices]
    labels_train = [labels[index] for index in train_indices]
    labels_test = [labels[index] for index in test_indices]
    lines_test = [line_numbers[index] for index in test_indices]

    model = fit_model_on_indices(rows, used_columns, train_indices)
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


def temporal_split_indices(rows: list[dict[str, Any]]) -> tuple[list[int], list[int], str]:
    dated_indices = sorted(
        (row["date_posted"].date(), index)
        for index, row in enumerate(rows)
        if isinstance(row.get("date_posted"), datetime)
    )
    cutoff_date = dated_indices[int(len(dated_indices) * (1 - TEST_SIZE))][0]
    train_indices = [index for posted_date, index in dated_indices if posted_date < cutoff_date]
    test_indices = [index for posted_date, index in dated_indices if posted_date >= cutoff_date]
    return train_indices, test_indices, cutoff_date.isoformat()


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


def hoax_proportion(rows: list[dict[str, Any]], indices: list[int]) -> float:
    if not indices:
        return 0.0
    return sum(int(rows[index]["is_hoax"]) for index in indices) / len(indices)


def train_phase_eight(rows: list[dict[str, Any]]) -> PhaseEightResult:
    train_indices, test_indices, cutoff_date = temporal_split_indices(rows)
    return PhaseEightResult(
        split_date_column="date_posted",
        cutoff_date=cutoff_date,
        train_size=len(train_indices),
        test_size=len(test_indices),
        train_hoax_proportion=hoax_proportion(rows, train_indices),
        test_hoax_proportion=hoax_proportion(rows, test_indices),
        phase_four_temporal=train_classifier_on_indices(rows, ["comments"], train_indices, test_indices),
        corrected_temporal=train_classifier_on_indices(
            rows,
            CORRECTED_MODEL_COLUMNS,
            train_indices,
            test_indices,
        ),
    )


def is_missing_value(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def train_phase_nine(rows: list[dict[str, Any]]) -> PhaseNineResult:
    stats: list[MissingColumnStats] = []
    excluded_columns = {"is_hoax", "_line_number"}
    columns = [column for column in rows[0] if column not in excluded_columns]

    for column in columns:
        missing_labels: list[int] = []
        filled_labels: list[int] = []
        for row in rows:
            target = int(row["is_hoax"])
            if is_missing_value(row.get(column)):
                missing_labels.append(target)
            else:
                filled_labels.append(target)

        if not missing_labels:
            continue

        stats.append(
            MissingColumnStats(
                column=column,
                missing_count=len(missing_labels),
                filled_count=len(filled_labels),
                missing_hoax_proportion=sum(missing_labels) / len(missing_labels),
                filled_hoax_proportion=sum(filled_labels) / len(filled_labels) if filled_labels else 0.0,
            )
        )

    top_columns = sorted(stats, key=lambda item: item.missing_count, reverse=True)[:3]
    return PhaseNineResult(
        top_columns=top_columns,
        treatment=(
            f"conserver toutes les lignes et encoder chaque trou avec le marqueur {MISSING_MARKER}"
        ),
    )


def predict_single_report(model: Any, row: dict[str, Any], used_columns: list[str]) -> int:
    return int(model.predict([row_to_text(row, used_columns)])[0])


def train_phase_ten(rows: list[dict[str, Any]]) -> PhaseTenResult:
    train_indices, test_indices, _cutoff_date = temporal_split_indices(rows)
    model = fit_model_on_indices(rows, CORRECTED_MODEL_COLUMNS, train_indices)
    corrected_result = train_classifier_on_indices(rows, CORRECTED_MODEL_COLUMNS, train_indices, test_indices)
    single_report = {
        "_line_number": "manuel",
        "datetime": datetime(2014, 6, 1, 22, 30),
        "city": "tinley park",
        "state": "il",
        "country": "us",
        "shape": "light",
        "duration_seconds": 180.0,
        "duration_hours_min": "3 minutes",
        "latitude": 41.5734,
        "longitude": -87.7845,
    }
    prediction = predict_single_report(model, single_report, CORRECTED_MODEL_COLUMNS)
    return PhaseTenResult(
        split_name="decoupe temporelle sur date_posted",
        train_hoax_proportion=hoax_proportion(rows, train_indices),
        test_hoax_proportion=hoax_proportion(rows, test_indices),
        corrected_result=corrected_result,
        single_prediction=prediction,
        single_prediction_label="canular" if prediction else "pas canular",
        single_report_text=row_to_text(single_report, CORRECTED_MODEL_COLUMNS),
    )


NUMBER_WORDS = {
    "a": 1.0,
    "an": 1.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "few": 3.0,
    "couple": 2.0,
    "several": 4.0,
    "half": 0.5,
}

UNIT_SECONDS = {
    "sec": 1.0,
    "secs": 1.0,
    "second": 1.0,
    "seconds": 1.0,
    "min": 60.0,
    "mins": 60.0,
    "minute": 60.0,
    "minutes": 60.0,
    "hr": 3600.0,
    "hrs": 3600.0,
    "hour": 3600.0,
    "hours": 3600.0,
    "day": 86400.0,
    "days": 86400.0,
    "week": 604800.0,
    "weeks": 604800.0,
    "month": 2629800.0,
    "months": 2629800.0,
    "year": 31557600.0,
    "years": 31557600.0,
}


def parse_duration_text(value: Any) -> float | None:
    text = str(value or "").strip().lower()
    if not text:
        return None

    text = text.replace("&#39", "'")
    text = text.replace("&quot;", " ")
    text = text.replace("`", "")
    text = re.sub(r"[(),;]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    unknown_markers = ["unknown", "ongoing", "still", "not sure", "?", "n/a"]
    if text in unknown_markers or any(marker in text for marker in ["ongoing", "still going"]):
        return None

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*"
        r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)",
        text,
    )
    if match:
        numerator = float(match.group(1))
        denominator = float(match.group(2))
        unit = normalize_duration_unit(match.group(3))
        if denominator:
            return (numerator / denominator) * UNIT_SECONDS[unit]

    compact = text.replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(sec|secs|min|mins|hr|hrs|hour|hours|minute|minutes|second|seconds)", compact)
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        return ((low + high) / 2.0) * UNIT_SECONDS[match.group(3)]

    match = re.fullmatch(r"(\d+(?:\.\d+)?)(sec|secs|min|mins|hr|hrs|hour|hours|minute|minutes|second|seconds|day|days|week|weeks|month|months|year|years)", compact)
    if match:
        return float(match.group(1)) * UNIT_SECONDS[match.group(2)]

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*"
        r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)",
        text,
    )
    if match:
        low = float(match.group(1))
        high = float(match.group(2))
        unit = normalize_duration_unit(match.group(3))
        return ((low + high) / 2.0) * UNIT_SECONDS[unit]

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*"
        r"(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)",
        text,
    )
    if match:
        amount = float(match.group(1))
        unit = normalize_duration_unit(match.group(2))
        return amount * UNIT_SECONDS[unit]

    match = re.search(
        r"(one|two|three|four|five|six|seven|eight|nine|ten|few|couple|several|half)\s+"
        r"(seconds?|minutes?|hours?|days?|weeks?|months?|years?)",
        text,
    )
    if match:
        amount = NUMBER_WORDS[match.group(1)]
        unit = normalize_duration_unit(match.group(2))
        return amount * UNIT_SECONDS[unit]

    if text == "seconds":
        return None

    return None


def normalize_duration_unit(unit: str) -> str:
    unit = unit.lower()
    if unit.startswith("sec"):
        return "seconds"
    if unit.startswith("min"):
        return "minutes"
    if unit.startswith("hr"):
        return "hours"
    if unit.startswith("hour"):
        return "hours"
    if unit.startswith("day"):
        return "days"
    if unit.startswith("week"):
        return "weeks"
    if unit.startswith("month"):
        return "months"
    if unit.startswith("year"):
        return "years"
    return unit


def choose_duration_seconds(row: dict[str, Any]) -> float | None:
    numeric = row.get("duration_seconds")
    text_seconds = parse_duration_text(row.get("duration_hours_min"))

    if text_seconds is not None and (numeric is None or numeric == 0):
        return text_seconds
    if numeric is not None:
        return float(numeric)
    return text_seconds


def durations_conflict(numeric: float | None, text_seconds: float | None) -> bool:
    if numeric is None or text_seconds is None:
        return False
    if numeric == 0 and text_seconds > 0:
        return True
    tolerance = max(60.0, 0.25 * max(abs(numeric), abs(text_seconds)))
    return abs(numeric - text_seconds) > tolerance


def train_phase_eleven(rows: list[dict[str, Any]]) -> PhaseElevenResult:
    usable_durations: list[float] = []
    durations_for_median: list[float] = []
    conflicts: list[DurationConflictExample] = []
    longest_candidates: list[LongDurationExample] = []

    for row in rows:
        numeric = row.get("duration_seconds")
        numeric_seconds = float(numeric) if numeric is not None else None
        text_seconds = parse_duration_text(row.get("duration_hours_min"))
        chosen = choose_duration_seconds(row)

        if chosen is not None:
            usable_durations.append(chosen)
            if chosen <= 86400:
                durations_for_median.append(chosen)
            longest_candidates.append(
                LongDurationExample(
                    line_number=int(row["_line_number"]),
                    duration_seconds=chosen,
                    duration_text=str(row.get("duration_hours_min", "")),
                    comments=str(row.get("comments", ""))[:120],
                )
            )

        if durations_conflict(numeric_seconds, text_seconds):
            conflicts.append(
                DurationConflictExample(
                    line_number=int(row["_line_number"]),
                    numeric_seconds=numeric_seconds,
                    text_seconds=text_seconds,
                    duration_text=str(row.get("duration_hours_min", "")),
                )
            )

    longest_examples = sorted(
        longest_candidates,
        key=lambda item: item.duration_seconds,
        reverse=True,
    )[:3]
    return PhaseElevenResult(
        unusable_count=len(rows) - len(usable_durations),
        conflict_count=len(conflicts),
        median_seconds=statistics.median(durations_for_median),
        longer_than_day_count=sum(1 for duration in usable_durations if duration > 86400),
        longest_examples=longest_examples,
        conflict_examples=conflicts[:3],
    )


CITY_MIN_COUNT = 20
SHAPE_MIN_COUNT = 20


def canonical_shape(value: Any) -> str:
    shape = normalized_text(value)
    if not shape:
        return MISSING_MARKER
    replacements = {
        "changed": "changing",
        "round": "circle",
    }
    return replacements.get(shape, shape)


def encode_shape(value: Any, frequent_shapes: set[str]) -> str:
    shape = canonical_shape(value)
    if shape == MISSING_MARKER:
        return MISSING_MARKER
    if shape in frequent_shapes:
        return shape
    return "__rare_shape__"


def hour_components(value: Any) -> tuple[float, float]:
    if not isinstance(value, datetime):
        return 0.0, 0.0
    hour = value.hour + value.minute / 60.0
    angle = 2 * math.pi * hour / 24.0
    return math.sin(angle), math.cos(angle)


def hour_distance(first_hour: int, second_hour: int) -> float:
    first_sin, first_cos = hour_components(datetime(2000, 1, 1, first_hour, 0))
    second_sin, second_cos = hour_components(datetime(2000, 1, 1, second_hour, 0))
    return math.hypot(first_sin - second_sin, first_cos - second_cos)


def fit_frequent_cities(rows: list[dict[str, Any]], train_indices: list[int]) -> set[str]:
    from collections import Counter

    counts = Counter(normalized_text(rows[index].get("city")) for index in train_indices)
    return {city for city, count in counts.items() if city and count >= CITY_MIN_COUNT}


def fit_frequent_shapes(rows: list[dict[str, Any]], train_indices: list[int]) -> set[str]:
    from collections import Counter

    counts = Counter(canonical_shape(rows[index].get("shape")) for index in train_indices)
    return {
        shape
        for shape, count in counts.items()
        if shape != MISSING_MARKER and count >= SHAPE_MIN_COUNT
    }


def phase_twelve_features(
    row: dict[str, Any],
    frequent_cities: set[str],
    frequent_shapes: set[str],
) -> dict[str, float | str]:
    city = normalized_text(row.get("city"))
    if not city:
        city_value = MISSING_MARKER
    elif city in frequent_cities:
        city_value = city
    else:
        city_value = "__rare_city__"

    hour_sin, hour_cos = hour_components(row.get("datetime"))
    return {
        "city": city_value,
        "shape": encode_shape(row.get("shape"), frequent_shapes),
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
    }


def train_inspectable_phase_twelve_model(
    rows: list[dict[str, Any]],
    train_indices: list[int],
    test_indices: list[int],
) -> TrainedPhaseTwelveModel:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression

    frequent_cities = fit_frequent_cities(rows, train_indices)
    frequent_shapes = fit_frequent_shapes(rows, train_indices)
    train_features = [
        phase_twelve_features(rows[index], frequent_cities, frequent_shapes)
        for index in train_indices
    ]
    test_features = [
        phase_twelve_features(rows[index], frequent_cities, frequent_shapes)
        for index in test_indices
    ]
    train_labels = [int(rows[index]["is_hoax"]) for index in train_indices]
    test_labels = [int(rows[index]["is_hoax"]) for index in test_indices]

    vectorizer = DictVectorizer(sparse=True)
    train_matrix = force_sparse_int32(vectorizer.fit_transform(train_features))
    test_matrix = force_sparse_int32(vectorizer.transform(test_features))
    classifier = LogisticRegression(
        class_weight="balanced",
        max_iter=500,
        solver="liblinear",
        random_state=MODEL_RANDOM_STATE,
    )
    classifier.fit(train_matrix, train_labels)
    probabilities = classifier.predict_proba(test_matrix)[:, 1]
    predictions = classifier.predict(test_matrix)

    return TrainedPhaseTwelveModel(
        vectorizer=vectorizer,
        classifier=classifier,
        frequent_cities=frequent_cities,
        frequent_shapes=frequent_shapes,
        test_indices=test_indices,
        labels=test_labels,
        probabilities=[float(probability) for probability in probabilities],
        predictions=[int(prediction) for prediction in predictions],
        feature_count=len(vectorizer.get_feature_names_out()),
    )


def force_sparse_int32(matrix: Any) -> Any:
    matrix.indices = matrix.indices.astype("int32", copy=False)
    matrix.indptr = matrix.indptr.astype("int32", copy=False)
    return matrix


def phase_twelve_probability_output(
    rows: list[dict[str, Any]],
    train_indices: list[int],
    test_indices: list[int],
) -> ProbabilityOutput:
    trained = train_inspectable_phase_twelve_model(rows, train_indices, test_indices)

    return ProbabilityOutput(
        labels=trained.labels,
        probabilities=trained.probabilities,
        predictions=trained.predictions,
        feature_count=trained.feature_count,
    )


def train_phase_twelve_model_data(rows: list[dict[str, Any]]) -> PhaseTwelveModelData:
    from collections import Counter

    train_indices, test_indices, _cutoff_date = temporal_split_indices(rows)
    probability_output = phase_twelve_probability_output(rows, train_indices, test_indices)
    frequent_cities = fit_frequent_cities(rows, train_indices)
    frequent_shapes = fit_frequent_shapes(rows, train_indices)

    city_counts = Counter(normalized_text(row.get("city")) for row in rows)
    raw_city_count = sum(1 for city in city_counts if city)
    raw_shapes = {normalized_text(row.get("shape")) for row in rows if normalized_text(row.get("shape"))}
    canonical_shapes = {canonical_shape(row.get("shape")) for row in rows}
    canonical_shapes.discard(MISSING_MARKER)
    has_rare_shape = any(shape not in frequent_shapes for shape in canonical_shapes)

    before_width = raw_city_count + len(raw_shapes) + 24
    return PhaseTwelveModelData(
        before_width=before_width,
        after_width=probability_output.feature_count,
        city_rule=f"garder les villes presentes au moins {CITY_MIN_COUNT} fois dans l'apprentissage",
        shape_rule=(
            "fusionner changed/changing et round/circle, puis regrouper les formes presentes "
            f"moins de {SHAPE_MIN_COUNT} fois dans l'apprentissage"
        ),
        singleton_city_count=sum(1 for city, count in city_counts.items() if city and count == 1),
        kept_city_count=len(frequent_cities),
        raw_shape_count=len(raw_shapes),
        normalized_shape_count=len(frequent_shapes) + int(has_rare_shape),
        distance_23_to_0=hour_distance(23, 0),
        distance_23_to_20=hour_distance(23, 20),
        labels=probability_output.labels,
        probabilities=probability_output.probabilities,
        predictions=probability_output.predictions,
    )


def summarize_phase_twelve(model_data: PhaseTwelveModelData) -> PhaseTwelveResult:
    from sklearn.metrics import precision_score, recall_score

    return PhaseTwelveResult(
        before_width=model_data.before_width,
        after_width=model_data.after_width,
        city_rule=model_data.city_rule,
        shape_rule=model_data.shape_rule,
        singleton_city_count=model_data.singleton_city_count,
        kept_city_count=model_data.kept_city_count,
        raw_shape_count=model_data.raw_shape_count,
        normalized_shape_count=model_data.normalized_shape_count,
        distance_23_to_0=model_data.distance_23_to_0,
        distance_23_to_20=model_data.distance_23_to_20,
        recall=recall_score(model_data.labels, model_data.predictions, zero_division=0),
        precision=precision_score(model_data.labels, model_data.predictions, zero_division=0),
    )


def train_phase_twelve(rows: list[dict[str, Any]]) -> PhaseTwelveResult:
    return summarize_phase_twelve(train_phase_twelve_model_data(rows))


def cost_at_threshold(labels: list[int], probabilities: list[float], threshold: float) -> ThresholdCost:
    false_negatives = 0
    false_positives = 0
    for label, probability in zip(labels, probabilities, strict=True):
        predicted_hoax = probability >= threshold
        if label == 1 and not predicted_hoax:
            false_negatives += 1
        elif label == 0 and predicted_hoax:
            false_positives += 1

    return ThresholdCost(
        threshold=threshold,
        false_negative_count=false_negatives,
        false_positive_count=false_positives,
        cost=false_negatives * 30 + false_positives * 2,
    )


def summarize_phase_thirteen(model_data: PhaseTwelveModelData) -> PhaseThirteenResult:
    labels = model_data.labels
    probabilities = model_data.probabilities
    candidates = sorted({0.0, 0.5, 1.0, *probabilities})
    selected = min(
        (cost_at_threshold(labels, probabilities, threshold) for threshold in candidates),
        key=lambda item: (item.cost, -item.threshold),
    )

    table_thresholds = {round(step / 10, 1) for step in range(11)}
    table_thresholds.add(round(selected.threshold, 6))
    cost_table = [
        cost_at_threshold(labels, probabilities, threshold)
        for threshold in sorted(table_thresholds)
    ]
    default = cost_at_threshold(labels, probabilities, 0.5)
    return PhaseThirteenResult(
        cost_table=cost_table,
        selected=selected,
        default=default,
        saved_credits=default.cost - selected.cost,
    )


def train_phase_thirteen(rows: list[dict[str, Any]]) -> PhaseThirteenResult:
    return summarize_phase_thirteen(train_phase_twelve_model_data(rows))


def calibration_bins(labels: list[int], probabilities: list[float], bin_count: int = 10) -> list[CalibrationBin]:
    bins: list[CalibrationBin] = []
    for bin_index in range(bin_count):
        low = bin_index / bin_count
        high = (bin_index + 1) / bin_count
        selected = [
            (label, probability)
            for label, probability in zip(labels, probabilities, strict=True)
            if low <= probability < high or (bin_index == bin_count - 1 and probability == 1.0)
        ]
        count = len(selected)
        mean_probability = statistics.mean(probability for _label, probability in selected) if selected else 0.0
        observed_proportion = statistics.mean(label for label, _probability in selected) if selected else 0.0
        bins.append(
            CalibrationBin(
                label=f"[{low:.1f};{high:.1f}{']' if bin_index == bin_count - 1 else '['}",
                count=count,
                mean_probability=mean_probability,
                observed_proportion=observed_proportion,
            )
        )
    return bins


def split_training_for_calibration(train_indices: list[int]) -> tuple[list[int], list[int]]:
    split_at = int(len(train_indices) * 0.8)
    return train_indices[:split_at], train_indices[split_at:]


def train_phase_fourteen(rows: list[dict[str, Any]]) -> PhaseFourteenResult:
    from sklearn.isotonic import IsotonicRegression

    train_indices, test_indices, _cutoff_date = temporal_split_indices(rows)
    base_train_indices, calibration_indices = split_training_for_calibration(train_indices)
    calibration_output = phase_twelve_probability_output(rows, base_train_indices, calibration_indices)
    test_output = phase_twelve_probability_output(rows, base_train_indices, test_indices)

    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(calibration_output.probabilities, calibration_output.labels)
    calibrated_probabilities = [
        float(probability)
        for probability in calibrator.transform(test_output.probabilities)
    ]

    raw_bins = calibration_bins(test_output.labels, test_output.probabilities)
    calibrated_bins = calibration_bins(test_output.labels, calibrated_probabilities)
    non_empty_diffs = [
        item.mean_probability - item.observed_proportion
        for item in raw_bins
        if item.count >= 100
    ]
    mean_diff = statistics.mean(non_empty_diffs) if non_empty_diffs else 0.0
    if mean_diff > 0.02:
        error_direction = "trop confiant : les probabilites annoncees sont au-dessus des proportions observees"
    elif mean_diff < -0.02:
        error_direction = "trop prudent : les probabilites annoncees sont sous les proportions observees"
    else:
        error_direction = "globalement proche sur les grosses tranches"

    return PhaseFourteenResult(
        raw_bins=raw_bins,
        calibrated_bins=calibrated_bins,
        correction_method=(
            "calibration isotone apprise sur les 20% les plus recents de l'apprentissage temporel"
        ),
        error_direction=error_direction,
        base_train_size=len(base_train_indices),
        calibration_size=len(calibration_indices),
        test_size=len(test_indices),
    )


def metric_interval(values: list[float]) -> MetricInterval:
    return MetricInterval(
        minimum=min(values),
        mean=statistics.mean(values),
        maximum=max(values),
    )


def train_phase_fifteen(rows: list[dict[str, Any]], split_count: int = 20) -> PhaseFifteenResult:
    from sklearn.metrics import precision_score, recall_score
    from sklearn.model_selection import StratifiedShuffleSplit

    labels = [int(row["is_hoax"]) for row in rows]
    splitter = StratifiedShuffleSplit(
        n_splits=split_count,
        test_size=TEST_SIZE,
        random_state=MODEL_RANDOM_STATE,
    )

    metrics: list[SplitMetric] = []
    for train_indices_array, test_indices_array in splitter.split(rows, labels):
        train_indices = [int(index) for index in train_indices_array]
        test_indices = [int(index) for index in test_indices_array]
        output = phase_twelve_probability_output(rows, train_indices, test_indices)
        metrics.append(
            SplitMetric(
                test_size=len(test_indices),
                test_hoax_count=sum(output.labels),
                recall=recall_score(output.labels, output.predictions, zero_division=0),
                precision=precision_score(output.labels, output.predictions, zero_division=0),
            )
        )

    temporal_train_indices, temporal_test_indices, _cutoff_date = temporal_split_indices(rows)
    temporal_labels = [int(rows[index]["is_hoax"]) for index in temporal_test_indices]
    recall_values = [item.recall for item in metrics]
    precision_values = [item.precision for item in metrics]
    analyst_first = 0.31
    analyst_second = 0.34
    analyst_gap = abs(analyst_second - analyst_first)
    recall_width = max(recall_values) - min(recall_values)
    answer = (
        "impossible de trancher seulement avec ces deux chiffres : "
        f"leur ecart de {analyst_gap:.2f} est plus petit que la largeur observee "
        f"de l'intervalle de rappel ({recall_width:.3f})"
    )

    return PhaseFifteenResult(
        split_count=split_count,
        temporal_test_size=len(temporal_test_indices),
        temporal_test_hoax_count=sum(temporal_labels),
        repeated_test_size=metrics[0].test_size,
        repeated_test_hoax_count=metrics[0].test_hoax_count,
        recall_interval=metric_interval(recall_values),
        precision_interval=metric_interval(precision_values),
        analyst_first=analyst_first,
        analyst_second=analyst_second,
        analyst_gap=analyst_gap,
        answer=answer,
    )


def report_summary(row: dict[str, Any]) -> str:
    observed_at = row.get("datetime")
    observed = observed_at.isoformat(sep=" ") if isinstance(observed_at, datetime) else "date inconnue"
    return (
        f"{observed} | city={row.get('city') or MISSING_MARKER} | "
        f"state={row.get('state') or MISSING_MARKER} | "
        f"country={row.get('country') or MISSING_MARKER} | "
        f"shape={row.get('shape') or MISSING_MARKER}"
    )


def explain_report(
    rows: list[dict[str, Any]],
    trained: TrainedPhaseTwelveModel,
    test_position: int,
    role: str,
) -> ExplainedReport:
    row = rows[trained.test_indices[test_position]]
    features = phase_twelve_features(row, trained.frequent_cities, trained.frequent_shapes)
    matrix = trained.vectorizer.transform([features])
    feature_names = trained.vectorizer.get_feature_names_out()
    coefficients = trained.classifier.coef_[0]
    contributions = [
        LocalContribution(feature=feature_names[index], contribution=float(coefficients[index] * value))
        for index, value in zip(matrix.indices, matrix.data, strict=True)
    ]
    positive_reasons = sorted(
        [item for item in contributions if item.contribution > 0],
        key=lambda item: item.contribution,
        reverse=True,
    )[:3]
    negative_reasons = sorted(
        [item for item in contributions if item.contribution < 0],
        key=lambda item: item.contribution,
    )[:3]

    return ExplainedReport(
        role=role,
        line_number=int(row["_line_number"]),
        probability=trained.probabilities[test_position],
        true_label=trained.labels[test_position],
        predicted_label=trained.predictions[test_position],
        summary=report_summary(row),
        positive_reasons=positive_reasons,
        negative_reasons=negative_reasons,
    )


def choose_phase_sixteen_reports(
    rows: list[dict[str, Any]],
    trained: TrainedPhaseTwelveModel,
    threshold: float,
) -> list[ExplainedReport]:
    predicted_positions = [
        index
        for index, probability in enumerate(trained.probabilities)
        if probability >= threshold
    ]
    high_position = max(predicted_positions, key=lambda index: trained.probabilities[index])
    boundary_position = min(predicted_positions, key=lambda index: trained.probabilities[index])
    missed_positions = [
        index
        for index, (label, probability) in enumerate(zip(trained.labels, trained.probabilities, strict=True))
        if label == 1 and probability < threshold
    ]
    missed_position = max(missed_positions, key=lambda index: trained.probabilities[index])

    return [
        explain_report(rows, trained, high_position, "marque canular avec forte confiance"),
        explain_report(rows, trained, boundary_position, "marque canular juste au-dessus de 0,5"),
        explain_report(rows, trained, missed_position, "canular laisse passer"),
    ]


def phase_sixteen_score(
    rows: list[dict[str, Any]],
    trained: TrainedPhaseTwelveModel,
    damaged_column: str | None = None,
) -> float:
    from sklearn.metrics import average_precision_score

    rng = random.Random(MODEL_RANDOM_STATE)
    values = [rows[index].get("datetime" if damaged_column == "hour" else damaged_column) for index in trained.test_indices]
    if damaged_column is not None:
        rng.shuffle(values)

    features: list[dict[str, float | str]] = []
    for position, row_index in enumerate(trained.test_indices):
        row = rows[row_index]
        if damaged_column is None:
            features.append(phase_twelve_features(row, trained.frequent_cities, trained.frequent_shapes))
            continue

        damaged_row = dict(row)
        if damaged_column == "hour":
            damaged_row["datetime"] = values[position]
        else:
            damaged_row[damaged_column] = values[position]
        features.append(phase_twelve_features(damaged_row, trained.frequent_cities, trained.frequent_shapes))

    matrix = force_sparse_int32(trained.vectorizer.transform(features))
    probabilities = trained.classifier.predict_proba(matrix)[:, 1]
    return float(average_precision_score(trained.labels, probabilities))


def train_phase_sixteen(rows: list[dict[str, Any]]) -> PhaseSixteenResult:
    train_indices, test_indices, _cutoff_date = temporal_split_indices(rows)
    trained = train_inspectable_phase_twelve_model(rows, train_indices, test_indices)
    explanation_threshold = 0.5
    reports = choose_phase_sixteen_reports(rows, trained, explanation_threshold)
    baseline_score = phase_sixteen_score(rows, trained)
    importances = []
    for column in ["city", "shape", "hour"]:
        shuffled_score = phase_sixteen_score(rows, trained, column)
        importances.append(
            ColumnImportance(
                column=column,
                baseline_score=baseline_score,
                shuffled_score=shuffled_score,
                drop=baseline_score - shuffled_score,
            )
        )
    importances.sort(key=lambda item: item.drop, reverse=True)

    top_column = importances[0].column
    if top_column == "hour":
        surprising_note = "l'heure arrive devant la ville, alors que la ville semblait etre la variable riche la plus evidente"
    elif top_column == "shape":
        surprising_note = "la forme pese plus que la ville, malgre le gros travail fait pour encoder les villes"
    else:
        surprising_note = "la ville reste premiere, mais sa chute reste faible au regard de ses 22 018 valeurs brutes"

    return PhaseSixteenResult(
        threshold_used_for_explanations=explanation_threshold,
        threshold_note=(
            "la frontiere metier de la phase 13 vaut 1,0 et ne marque aucun dossier ; "
            "les explications locales utilisent donc le seuil technique 0,5 du modele brut"
        ),
        reports=reports,
        importances=importances,
        surprising_column_note=surprising_note,
    )


def geographic_zone(row: dict[str, Any]) -> str:
    country = normalized_text(row.get("country"))
    if country == "us":
        return "Etats-Unis"
    if country == "ca":
        return "Canada"
    if country == "gb":
        return "Royaume-Uni"
    if country == "au":
        return "Australie"
    if not country:
        return "Pays manquant"
    return "Autres pays"


def best_cost_threshold(labels: list[int], probabilities: list[float]) -> ThresholdCost:
    candidates = sorted({0.0, 0.5, 1.0, *probabilities})
    return min(
        (cost_at_threshold(labels, probabilities, threshold) for threshold in candidates),
        key=lambda item: (item.cost, -item.threshold),
    )


def zone_performance(
    zone: str,
    labels: list[int],
    probabilities: list[float],
    threshold: float,
) -> ZonePerformance:
    from sklearn.metrics import precision_score, recall_score

    predictions = [int(probability >= threshold) for probability in probabilities]
    default_cost = cost_at_threshold(labels, probabilities, threshold)
    best_cost = best_cost_threshold(labels, probabilities)
    return ZonePerformance(
        zone=zone,
        row_count=len(labels),
        hoax_count=sum(labels),
        hoax_proportion=sum(labels) / len(labels) if labels else 0.0,
        predicted_count=sum(predictions),
        recall=recall_score(labels, predictions, zero_division=0),
        precision=precision_score(labels, predictions, zero_division=0),
        default_cost=default_cost.cost,
        best_threshold=best_cost.threshold,
        best_cost=best_cost.cost,
    )


def train_phase_seventeen(rows: list[dict[str, Any]]) -> PhaseSeventeenResult:
    train_indices, test_indices, _cutoff_date = temporal_split_indices(rows)
    trained = train_inspectable_phase_twelve_model(rows, train_indices, test_indices)
    threshold = 0.5
    zones: dict[str, tuple[list[int], list[float]]] = {}

    for position, row_index in enumerate(trained.test_indices):
        zone = geographic_zone(rows[row_index])
        labels, probabilities = zones.setdefault(zone, ([], []))
        labels.append(trained.labels[position])
        probabilities.append(trained.probabilities[position])

    performances = [
        zone_performance("Global", trained.labels, trained.probabilities, threshold)
    ]
    zone_order = ["Etats-Unis", "Canada", "Royaume-Uni", "Australie", "Pays manquant", "Autres pays"]
    for zone in zone_order:
        if zone not in zones:
            continue
        labels, probabilities = zones[zone]
        performances.append(zone_performance(zone, labels, probabilities, threshold))

    decision = (
        "je garde une frontiere unique pour le deploiement : la frontiere cout minimale reste 1,0 "
        "dans le test global, et les zones hors Etats-Unis contiennent trop peu de canulars pour "
        "apprendre une frontiere locale fiable"
    )
    caution = (
        "les zones petites doivent etre lues avec la phase 15 en tete : quelques canulars en plus ou "
        "en moins suffisent a deplacer fortement le rappel"
    )
    return PhaseSeventeenResult(
        threshold_used_for_scores=threshold,
        zones=performances,
        decision=decision,
        caution=caution,
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


def print_phase_eight(result: PhaseEightResult) -> None:
    print()
    print("Phase 8 - L'ordre des choses")
    print(f"Date utilisee pour couper : {result.split_date_column}")
    print(f"Date de coupure : {result.cutoff_date}")
    print(f"Apprentissage : {result.train_size} releves")
    print(f"Test chronologique : {result.test_size} releves")
    print(f"Proportion de canulars apprentissage : {result.train_hoax_proportion * 100:.3f}%")
    print(f"Proportion de canulars test : {result.test_hoax_proportion * 100:.3f}%")
    print("Scores phase 4 apres decoupe temporelle :")
    print(
        f"  - rappel {result.phase_four_temporal.recall * 100:.1f}, "
        f"precision {result.phase_four_temporal.precision * 100:.1f}"
    )
    print("Scores du modele corrige apres decoupe temporelle :")
    print(
        f"  - rappel {result.corrected_temporal.recall * 100:.1f}, "
        f"precision {result.corrected_temporal.precision * 100:.1f}"
    )


def print_phase_nine(result: PhaseNineResult) -> None:
    print()
    print("Phase 9 - Les cases vides")
    for item in result.top_columns:
        print(
            f"{item.column}: {item.missing_count} trous, "
            f"canulars si vide {item.missing_hoax_proportion * 100:.3f}%, "
            f"canulars si rempli {item.filled_hoax_proportion * 100:.3f}%"
        )
    print(f"Traitement retenu : {result.treatment}")


def print_phase_ten(result: PhaseTenResult) -> None:
    print()
    print("Phase 10 - La chaine de traitement du Bureau")
    print(f"Decoupe utilisee : {result.split_name}")
    print(f"Proportion de canulars apprentissage : {result.train_hoax_proportion * 100:.3f}%")
    print(f"Proportion de canulars test : {result.test_hoax_proportion * 100:.3f}%")
    print("Scores apres correction de la chaine :")
    print(
        f"  - rappel {result.corrected_result.recall * 100:.1f}, "
        f"precision {result.corrected_result.precision * 100:.1f}"
    )
    print("Releve manuel donne a la chaine :")
    print(f"  - {result.single_report_text}")
    print(f"Prediction sortie : {result.single_prediction} ({result.single_prediction_label})")


def print_phase_eleven(result: PhaseElevenResult) -> None:
    print()
    print("Phase 11 - Combien de temps ca a dure")
    print(f"Durees inutilisables apres traitement : {result.unusable_count}")
    print(f"Durees contradictoires entre les deux colonnes : {result.conflict_count}")
    print(f"Duree mediane retenue : {result.median_seconds:.1f} secondes")
    print(f"Releves annoncant plus d'une journee : {result.longer_than_day_count}")
    print("Exemples de contradictions :")
    for item in result.conflict_examples:
        print(
            f"  - ligne {item.line_number}: numeric={item.numeric_seconds}, "
            f"texte={item.text_seconds}, brut={item.duration_text!r}"
        )
    print("Trois durees les plus longues :")
    for item in result.longest_examples:
        print(
            f"  - ligne {item.line_number}: {item.duration_seconds:.0f} secondes, "
            f"texte={item.duration_text!r}, commentaire={item.comments}"
        )


def print_phase_twelve(result: PhaseTwelveResult) -> None:
    print()
    print("Phase 12 - La ville et l'heure")
    print(f"Largeur avant traitement : {result.before_width} colonnes")
    print(f"Largeur apres traitement : {result.after_width} colonnes")
    print(f"Regle villes : {result.city_rule}")
    print(f"Villes gardees : {result.kept_city_count}")
    print(f"Villes presentes une seule fois : {result.singleton_city_count}")
    print(f"Regle formes : {result.shape_rule}")
    print(f"Formes brutes non vides : {result.raw_shape_count}")
    print(f"Formes restantes non vides : {result.normalized_shape_count}")
    print(f"Distance 23h-0h : {result.distance_23_to_0:.3f}")
    print(f"Distance 23h-20h : {result.distance_23_to_20:.3f}")
    print(f"Scores avec ville, forme et heure : rappel {result.recall * 100:.1f}, precision {result.precision * 100:.1f}")


def print_phase_thirteen(result: PhaseThirteenResult) -> None:
    print()
    print("Phase 13 - La facture du Bureau")
    print("Facture selon la frontiere :")
    for item in result.cost_table:
        print(
            f"  - seuil {item.threshold:.6f}: "
            f"canulars rates {item.false_negative_count}, "
            f"fausses alertes {item.false_positive_count}, "
            f"cout {item.cost} credits"
        )
    print(
        f"Frontiere retenue : {result.selected.threshold:.6f}, "
        f"cout {result.selected.cost} credits"
    )
    print(f"Facture a 0.5 : {result.default.cost} credits")
    print(f"Credits economises : {result.saved_credits}")


def print_calibration_bins(title: str, bins: list[CalibrationBin]) -> None:
    print(title)
    for item in bins:
        print(
            f"  - {item.label}: {item.count} releves, "
            f"proba moyenne {item.mean_probability * 100:.2f}%, "
            f"canulars observes {item.observed_proportion * 100:.2f}%"
        )


def print_phase_fourteen(result: PhaseFourteenResult) -> None:
    print()
    print("Phase 14 - Une promesse a 80 %")
    print(
        "Decoupe calibration : "
        f"{result.base_train_size} apprentissage modele, "
        f"{result.calibration_size} calibration, "
        f"{result.test_size} test"
    )
    print_calibration_bins("Avant correction :", result.raw_bins)
    print(f"Sens de l'erreur : {result.error_direction}")
    print(f"Correction : {result.correction_method}")
    print_calibration_bins("Apres correction :", result.calibrated_bins)


def format_interval(interval: MetricInterval) -> str:
    return f"{interval.minimum * 100:.1f}% - {interval.maximum * 100:.1f}% (moyenne {interval.mean * 100:.1f}%)"


def print_phase_fifteen(result: PhaseFifteenResult) -> None:
    print()
    print("Phase 15 - Deux analystes, deux chiffres")
    print(f"Decoupes utilisees : {result.split_count}")
    print(
        f"Test temporel actuel : {result.temporal_test_size} releves, "
        f"{result.temporal_test_hoax_count} canulars"
    )
    print(
        f"Chaque test repete : {result.repeated_test_size} releves, "
        f"{result.repeated_test_hoax_count} canulars"
    )
    print(f"Intervalle rappel : {format_interval(result.recall_interval)}")
    print(f"Intervalle precision : {format_interval(result.precision_interval)}")
    print(
        f"Analystes compares : {result.analyst_first:.2f} contre "
        f"{result.analyst_second:.2f}, ecart {result.analyst_gap:.2f}"
    )
    print(f"Reponse : {result.answer}")


def print_contributions(title: str, contributions: list[LocalContribution]) -> None:
    print(title)
    for item in contributions:
        print(f"    - {item.feature}: {item.contribution:+.3f}")


def print_phase_sixteen(result: PhaseSixteenResult) -> None:
    print()
    print("Phase 16 - Trois dossiers sur le bureau")
    print(f"Frontiere utilisee pour expliquer : {result.threshold_used_for_explanations:.1f}")
    print(f"Note : {result.threshold_note}")
    for report in result.reports:
        print(f"  - {report.role}")
        print(f"    ligne {report.line_number}: {report.summary}")
        print(
            f"    proba {report.probability * 100:.2f}%, "
            f"vrai label {report.true_label}, prediction {report.predicted_label}"
        )
        print_contributions("    pousse vers canular :", report.positive_reasons)
        print_contributions("    pousse vers pas canular :", report.negative_reasons)
    print("Classement global par permutation :")
    for item in result.importances:
        print(
            f"  - {item.column}: score base {item.baseline_score:.5f}, "
            f"score melange {item.shuffled_score:.5f}, chute {item.drop:.5f}"
        )
    print(f"Colonne surprenante : {result.surprising_column_note}")


def print_phase_seventeen(result: PhaseSeventeenResult) -> None:
    print()
    print("Phase 17 - L'angle mort du Bureau")
    print(f"Seuil utilise pour les scores : {result.threshold_used_for_scores:.1f}")
    for item in result.zones:
        print(
            f"  - {item.zone}: {item.row_count} releves, {item.hoax_count} canulars, "
            f"proportion {item.hoax_proportion * 100:.3f}%, "
            f"rappel {item.recall * 100:.1f}, precision {item.precision * 100:.1f}, "
            f"predits {item.predicted_count}, cout a 0.5 {item.default_cost}, "
            f"meilleur seuil {item.best_threshold:.6f}, meilleur cout {item.best_cost}"
        )
    print(f"Decision : {result.decision}")
    print(f"Prudence : {result.caution}")


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

    phase_eight = train_phase_eight(phase_two.typed_rows)
    print_phase_eight(phase_eight)

    phase_nine = train_phase_nine(phase_two.typed_rows)
    print_phase_nine(phase_nine)

    phase_ten = train_phase_ten(phase_two.typed_rows)
    print_phase_ten(phase_ten)

    phase_eleven = train_phase_eleven(phase_two.typed_rows)
    print_phase_eleven(phase_eleven)

    phase_twelve_model_data = train_phase_twelve_model_data(phase_two.typed_rows)
    phase_twelve = summarize_phase_twelve(phase_twelve_model_data)
    print_phase_twelve(phase_twelve)

    phase_thirteen = summarize_phase_thirteen(phase_twelve_model_data)
    print_phase_thirteen(phase_thirteen)

    phase_fourteen = train_phase_fourteen(phase_two.typed_rows)
    print_phase_fourteen(phase_fourteen)

    phase_fifteen = train_phase_fifteen(phase_two.typed_rows)
    print_phase_fifteen(phase_fifteen)

    phase_sixteen = train_phase_sixteen(phase_two.typed_rows)
    print_phase_sixteen(phase_sixteen)

    phase_seventeen = train_phase_seventeen(phase_two.typed_rows)
    print_phase_seventeen(phase_seventeen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
