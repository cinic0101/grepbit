"""The pre-policy-A statement rule (v16 to v21): an Overview states the owner's count assumption only for an
unresolved count reading. Rulers of the annex mechanics pin it, so they do not depend on the current candidate's
policy; policy A (#169, v22) states it on every executed Overview, and its ruler covers that."""
from unittest.mock import patch

from grepbit import recipe_model


def narrow(proposal):
    return dict(recipe_model.ASSUMPTION) if proposal.count_request == "unresolved" else None


def use(test):
    """Serve the narrow rule for the rest of ``test``."""
    patcher = patch.object(recipe_model.RecipeProposal, "assumption", property(narrow))
    patcher.start()
    test.addCleanup(patcher.stop)


def live_rule_is_narrow():
    """True while the live runtime still states the assumption only for an unresolved reading."""
    probe = recipe_model._proposal({"outcome": "request", "recipe_id": "overview", "recipe_version": "0.1",
                                    "request": {"start": "2026-03-01T00:00:00+08:00",
                                                "end": "2026-04-01T00:00:00+08:00", "timezone": "Asia/Taipei",
                                                "center_code": "CTR-A01"}, "count_request": "none"})
    return probe.assumption is None
