"""The pre-policy-A statement rule (v16 to v21): an Overview states the owner's count assumption only for an
unresolved count reading. Rulers of the annex mechanics pin it, so they do not depend on the current candidate's
policy; policy A (#169, v22) states it on every executed Overview, and its ruler covers that."""
from unittest.mock import patch

from grepbit import recipe_model
from tools import candidate_registry as registry

POLICY_A = "p3-overview-basis-v22"


def narrow(proposal):
    return dict(recipe_model.ASSUMPTION) if proposal.count_request == "unresolved" else None


def use(test):
    """Serve the narrow rule for the rest of ``test``."""
    patcher = patch.object(recipe_model.RecipeProposal, "assumption", property(narrow))
    patcher.start()
    test.addCleanup(patcher.stop)


def policy_a_registered():
    """True once candidate v22 is registered. From then on policy A is the owner's rule for every candidate, so a
    ruler takes the expected rule from the registry, never from the runtime it tests. A candidate that drops
    policy A, a restoration included, needs the owner's recorded decision and amends this helper and its rulers
    in that PR."""
    return POLICY_A in [entry["candidate_id"] for entry in registry.load_index()["entries"]]
