"""Scripted v12-era actions in v15's shape (docs/compare-orientation-v15.md, ADR #142).

v15 requires a typed ``orientation`` on every Compare request and no longer admits a model-emitted
``comparison_roles`` clarification. The offline fake scripts are therefore derived, never hand-edited:
a Compare request gains ``orientation: "stated"``, and a ``comparison_roles`` clarification becomes the
Compare request of its first choice with ``orientation: "unresolved"``, from which the server rebuilds the
same two reversed choices. Every other action is unchanged. The v1 scripts stay immutable.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIBLINGS = {
    "evals/p3/development-responses-v1.json": "evals/p3/development-oriented-responses-v1.json",
    "evals/dev/dev-responses-v1.json": "evals/dev/dev-oriented-responses-v1.json",
    "evals/dev/bound-meaning-responses-v1.json": "evals/dev/bound-meaning-oriented-responses-v1.json",
    "evals/dev/mechanism-probe-responses-v1.json": "evals/dev/mechanism-probe-oriented-responses-v1.json",
}


def orient(action: dict) -> dict:
    action = copy.deepcopy(action)
    if action.get("outcome") == "request" and action.get("recipe_id") == "compare" and "orientation" not in action:
        return {**action, "orientation": "stated"}
    if action.get("outcome") == "clarify" and action.get("clarification", {}).get("kind") == "comparison_roles":
        first = action["clarification"]["choices"][0]["semantic_value"]["request"]
        return {"outcome": "request", "recipe_id": "compare", "recipe_version": "0.1", "request": first,
                "orientation": "unresolved"}
    return action


def oriented_script(source: str) -> dict:
    data = json.loads((ROOT / source).read_text(encoding="utf-8"))
    return {"version": data["version"],
            "responses": [{"case_id": row["case_id"], "action": orient(row["action"])} for row in data["responses"]]}


def render(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
