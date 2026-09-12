"""Research analysis is inside the existing source-drift evidence boundary."""

import pytest

from evals import metric_factor_study, metric_selection_study, metric_wire_study


@pytest.mark.parametrize(
    "study", [metric_selection_study, metric_wire_study, metric_factor_study]
)
def test_analysis_time_drift_invalidates_report(tmp_path, monkeypatch, study):
    state = {"digest": "before"}
    original = study.analyze

    def analyze(*args):
        result = original(*args)
        state["digest"] = "after"
        return result

    monkeypatch.setattr(study, "analyze", analyze)
    monkeypatch.setattr(
        study,
        "_source_snapshot",
        lambda: {"available": True, "tracked_source_digest": state["digest"]},
    )
    report = study.run(tmp_path / "dry.json")
    assert not report["calls"]
    assert not report["source_unchanged"]
    assert report["source_end"]["tracked_source_digest"] == "after"
