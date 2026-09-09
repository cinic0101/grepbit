"""Value grounding: match what the question says to what a column stores.

Two deterministic steps around the model call, both limited to the columns
the overlay marks groundable:

1. ``ValueIndex.mentions`` finds stored values that occur verbatim (after
   normalization) in the question and hands them to the planner as hints, so a
   name is never cut at a segmentation boundary.
2. ``resolve`` turns a filter literal that matched no row into the stored value
   it most likely means (character-bigram similarity with an edit-distance tie
   break): a single clear candidate is substituted and stated as a candidate
   assumption; several candidates become a clarification that lists them;
   none leaves the clarification as it was.

Only values of groundable columns are ever indexed or shown. The index is a
copy of column values, so it lives in memory for the run.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from grepbit.domain.models import DomainModel
from grepbit.domain.plan import Filter, FilterOp, QueryPlan

GROUNDING_REVISION = "grounding-bigram-v1"
_DROP = re.compile(r"[\s\W_]+", re.UNICODE)
MIN_MENTION_CHARS = 2
UNIQUE_SCORE = 0.6
UNIQUE_MARGIN = 0.15
CANDIDATE_SCORE = 0.4
MAX_CANDIDATES = 5


def normalize_value(text: str) -> str:
    """NFKC, casefold, and drop whitespace and punctuation; CJK stays as is."""

    return _DROP.sub("", unicodedata.normalize("NFKC", text).casefold())


def _bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def _dice(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def edit_distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            )
        previous = current
    return previous[-1]


class Mention(DomainModel):
    column: str
    value: str


class Candidate(DomainModel):
    value: str
    score: float


class Resolution(DomainModel):
    column: str
    literal: str
    kind: str  # exact | unique | ambiguous | none
    candidates: list[Candidate] = []

    @property
    def value(self) -> str | None:
        return self.candidates[0].value if self.kind in {"exact", "unique"} else None


@dataclass
class ValueIndex:
    """Distinct values per groundable column, with their normalized forms."""

    values: dict[str, list[str]]
    _normalized: dict[str, list[tuple[str, str, set[str]]]] = field(
        init=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        for column, items in self.values.items():
            seen: set[str] = set()
            entries = []
            for value in items:
                normalized = normalize_value(value)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                entries.append((value, normalized, _bigrams(normalized)))
            self._normalized[column] = entries

    @property
    def columns(self) -> list[str]:
        return list(self._normalized)

    def size(self) -> int:
        return sum(len(v) for v in self._normalized.values())

    def mentions(self, question: str) -> list[Mention]:
        """Stored values that occur verbatim in the question, longest first.

        A shorter value contained in a longer matched value of the same column
        is dropped (特約永和 inside 特約永和中正).
        """

        haystack = normalize_value(question)
        found: list[Mention] = []
        for column, entries in self._normalized.items():
            hits = [
                (value, normalized)
                for value, normalized, _ in entries
                if len(normalized) >= MIN_MENTION_CHARS and normalized in haystack
            ]
            hits.sort(key=lambda item: len(item[1]), reverse=True)
            kept: list[tuple[str, str]] = []
            for value, normalized in hits:
                if any(normalized in longer for _, longer in kept):
                    continue
                kept.append((value, normalized))
            found.extend(Mention(column=column, value=value) for value, _ in kept)
        return found

    def candidates(self, column: str, literal: str) -> list[Candidate]:
        target = normalize_value(literal)
        if not target or column not in self._normalized:
            return []
        grams = _bigrams(target)
        scored: list[tuple[float, int, str]] = []
        for value, normalized, value_grams in self._normalized[column]:
            score = _dice(grams, value_grams)
            if target in normalized or normalized in target:
                score = max(score, 0.75)
            if score >= CANDIDATE_SCORE:
                scored.append((score, edit_distance(target, normalized), value))
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [
            Candidate(value=value, score=round(score, 3))
            for score, _, value in scored[:MAX_CANDIDATES]
        ]

    def resolve(self, column: str, literal: str) -> Resolution:
        target = normalize_value(literal)
        for value, normalized, _ in self._normalized.get(column, []):
            if normalized == target:
                return Resolution(
                    column=column,
                    literal=literal,
                    kind="exact",
                    candidates=[Candidate(value=value, score=1.0)],
                )
        found = self.candidates(column, literal)
        if not found:
            return Resolution(column=column, literal=literal, kind="none")
        top = found[0].score
        second = found[1].score if len(found) > 1 else 0.0
        if top >= UNIQUE_SCORE and top - second >= UNIQUE_MARGIN:
            return Resolution(
                column=column, literal=literal, kind="unique", candidates=found[:1]
            )
        return Resolution(
            column=column, literal=literal, kind="ambiguous", candidates=found
        )


def resolve_plan_literals(
    plan: QueryPlan,
    misses: list[tuple[str, str]],
    index: ValueIndex,
) -> tuple[QueryPlan, list[Resolution]]:
    """Substitute uniquely resolved literals in the plan's eq/in filters.

    ``misses`` are (column_id, literal) pairs the existence check found
    absent. Only groundable (indexed) columns are resolved; the returned
    resolutions include the ambiguous and none outcomes for the caller to
    report. The plan is otherwise untouched.
    """

    resolutions = [index.resolve(column, literal) for column, literal in misses]
    replacements = {
        (r.column, r.literal): r.value for r in resolutions if r.value is not None
    }
    if not replacements:
        return plan, resolutions
    filters: list[Filter] = []
    for item in plan.filters:
        if item.op in {FilterOp.EQ, FilterOp.IN}:
            values = [
                replacements.get((item.column.id, v), v) if isinstance(v, str) else v
                for v in item.values
            ]
            filters.append(item.model_copy(update={"values": values}))
        else:
            filters.append(item)
    return plan.model_copy(update={"filters": filters}), resolutions
