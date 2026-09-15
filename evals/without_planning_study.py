"""Single generic capability intervention; research only, no runtime imports."""

import json

from evals.query_kind_study import StudyPlanner

REVISION = "query-kind-without-composition-v1"
ORIGINAL = (
    "Existing latest-per-group and without\n"
    "entity selection use the legacy constructs, not rows+without."
)
COMPOSITION = (
    "Existing latest-per-group uses the legacy latest construct. "
    "without restricts the base population to entities with no matching child "
    "records; ordinary aggregates (including COUNT, SUM and AVG) and supported "
    "grouping operate on that surviving base population. without is a population "
    "restriction, not a row-projection mode. Do not combine rows with without."
)


class CompositionPlanner(StudyPlanner):
    def __init__(self, settings, **kwargs):
        super().__init__(settings, arm="joint", **kwargs)

    def build_messages(self, *args, **kwargs):
        messages = super().build_messages(*args, **kwargs)
        assert messages[0]["content"].count(ORIGINAL) == 1
        messages[0]["content"] = messages[0]["content"].replace(ORIGINAL, COMPOSITION)
        context = json.loads(messages[2]["content"])
        context["prompt_revision"] = REVISION
        messages[2]["content"] = json.dumps(context, ensure_ascii=False)
        return messages
