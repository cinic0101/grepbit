"""Research-only factorial combination of frozen prompt passages."""

import json
from pathlib import Path

from evals.query_kind_study import StudyPlanner, load_cases
from evals.temporal_repair_study import GUIDANCE
from evals.without_planning_study import COMPOSITION, ORIGINAL

ARMS = ("baseline", "time", "composition", "combined")
PANELS = ("query_kind_study", "without_capability_study", "temporal_repair_study")


def load_panel():
    cases = {}
    for name in PANELS:
        for case in load_cases(Path(f"evals/cases/{name}.yaml")):
            prior = cases.get(case["case_id"])
            if prior is not None:
                for key in (
                    "question",
                    "datasource_id",
                    "as_of",
                    "reference_sql",
                    "expected_route",
                    "ordered",
                ):
                    if prior.get(key, False if key == "ordered" else None) != case.get(
                        key, False if key == "ordered" else None
                    ):
                        raise ValueError(
                            f"conflicting_panel_contract:{case['case_id']}:{key}"
                        )
            else:
                cases[case["case_id"]] = case
    return list(cases.values())


class CombinationPlanner(StudyPlanner):
    def __init__(self, settings, *, treatment, **kwargs):
        if treatment not in ARMS:
            raise ValueError("unknown_treatment")
        super().__init__(settings, arm="joint", **kwargs)
        self.treatment = treatment

    def build_messages(self, *args, **kwargs):
        messages = super().build_messages(*args, **kwargs)
        if self.treatment in {"composition", "combined"}:
            assert messages[0]["content"].count(ORIGINAL) == 1
            messages[0]["content"] = messages[0]["content"].replace(
                ORIGINAL, COMPOSITION
            )
        if self.treatment in {"time", "combined"}:
            messages[0]["content"] += "\n" + GUIDANCE
        if self.treatment != "baseline":
            context = json.loads(messages[2]["content"])
            context["prompt_revision"] = f"joint-factor-{self.treatment}-v1"
            messages[2]["content"] = json.dumps(context, ensure_ascii=False)
        return messages
