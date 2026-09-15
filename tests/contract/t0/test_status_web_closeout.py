"""Existing metadata/presentation contracts; no language gate exemptions."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from t0_helpers import iot_schema

from grepbit.adapters.datasource_registry import load_registry, overlay_path
from grepbit.adapters.litellm.grounding_client import GroundingModelSettings
from grepbit.adapters.litellm.plan_client import (
    ChatCompletionsPlanClient,
    schema_payload,
)
from grepbit.adapters.overlay_store import load_semantic_overlay
from grepbit.application.overlay import overlay_problems

ROOT = Path(__file__).resolve().parents[3]


def test_web_adoption_uses_only_status_overlay_and_keeps_sampling_zero():
    path = ROOT / "evals/fixtures/dev_web_rows_datasources.json"
    registration = next(
        r for r in load_registry(path).datasources if r.id == "iot_spike"
    )
    assert registration.enum_distinct_limit == 0 and registration.allow_rows
    assert registration.business_timezone == "Asia/Taipei"
    assert (
        overlay_path(path, registration)
        == ROOT / "evals/fixtures/iot_v1/status_overlay.json"
    )


@pytest.mark.parametrize("mode", ["default", "rows"])
def test_status_aliases_reach_actual_propose_completion_boundary(monkeypatch, mode):
    overlay = load_semantic_overlay(ROOT / "evals/fixtures/iot_v1/status_overlay.json")
    schema = iot_schema().model_copy(update={"datasource_id": "iot_spike"})
    captured = []

    def complete(self, client, messages, **kwargs):
        captured.append(messages)
        return json.dumps(
            {
                "decision": "none",
                "reason": "semantic_gap",
                "clarification": "Offline transport sentinel, not a model answer.",
            }
        )

    monkeypatch.setattr(ChatCompletionsPlanClient, "_complete", complete)
    planner = ChatCompletionsPlanClient(
        GroundingModelSettings(base_url="http://unused.invalid", model="offline"),
        client=object(),
        allow_rows=True,
        query_kind=mode,
    )
    planner.propose(
        "離線裝置有幾台？", schema, as_of="2026-08-15T12:00:00+08:00", overlay=overlay
    )
    assert len(captured) == 1
    payload = json.loads(captured[0][-1]["content"])
    assert payload["prompt_revision"] == (
        "plan-classify-json-v15"
        if mode == "default"
        else "details-schema-only-v21-study"
    )
    status = next(
        c
        for t in payload["schema"]["tables"]
        if t["name"] == "devices"
        for c in t["columns"]
        if c["name"] == "status"
    )
    assert {v["value"] for v in status["value_aliases"]} == {
        "online",
        "offline",
        "maintenance",
    }


def test_status_overlay_only_supplies_reviewed_values():
    overlay = load_semantic_overlay(ROOT / "evals/fixtures/iot_v1/status_overlay.json")
    schema = iot_schema().model_copy(update={"datasource_id": "iot_spike"})
    assert not overlay_problems(overlay, schema)
    assert not overlay.metrics and not overlay.segments and not overlay.absent_concepts
    assert not overlay.column_policies and not overlay.table_policies
    assert not overlay.time_defaults and not overlay.groundable_columns()
    before, after = schema_payload(schema), schema_payload(schema, overlay)
    status = next(
        c
        for t in after["tables"]
        if t["name"] == "devices"
        for c in t["columns"]
        if c["name"] == "status"
    )
    assert status.pop("value_aliases") == [
        {"value": "online", "names": ["在線", "線上", "online"]},
        {"value": "offline", "names": ["離線", "offline"]},
        {"value": "maintenance", "names": ["維護中", "maintenance"]},
    ]
    # No visible column, scope or sample setting changes.
    assert after["tables"] == before["tables"]


@pytest.mark.parametrize(
    "status", ["answered", "clarify", "semantic_gap", "unsupported", "failed"]
)
@pytest.mark.parametrize(
    "mode,enabled", [("default", True), ("default", False), ("rows", True)]
)
def test_browser_guidance_preserves_result_and_never_resubmits(status, mode, enabled):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for actual JavaScript render checks")
    probe = r"""
const fs = require("fs"), vm = require("vm"), assert = require("assert");
const elements = new Map();
const element = () => ({textContent:"", hidden:false, disabled:false,
  replaceChildren(){}, append(){}, addEventListener(){}});
let requests = 0;
const context = {document:{getElementById(id){
  if (!elements.has(id)) elements.set(id, element()); return elements.get(id);
},createElement:element},fetch(){requests++;return new Promise(()=>{});}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), context);
const p = JSON.parse(process.argv[2]), enabled = JSON.parse(process.argv[3]);
elements.get("rows-mode") || elements.set("rows-mode",element());
elements.get("rows-mode").disabled = !enabled;
const frozen = JSON.stringify(p);
context.render(p);
assert.equal(JSON.stringify(p), frozen);
assert.equal(elements.get("evidence").textContent, JSON.stringify(p,null,2));
assert.equal(elements.get("refusal").textContent, p.reason+"\n"+p.clarification);
assert.equal(requests,2); // Only initial config/example reads, never /query.
const g = elements.get("mode-guidance");
assert.equal(g.hidden, !["clarify","semantic_gap","unsupported"].includes(p.status));
if (!g.hidden) {
  assert(g.textContent.includes("not a diagnosis"));
  assert(g.textContent.includes("does not supply missing business definitions"));
  if (p.query_kind === "rows") assert(g.textContent.includes("select Default"));
  else if (enabled) assert(g.textContent.includes("select Details"));
  else assert(g.textContent.includes("not enabled"));
} else assert.equal(g.textContent, "");
context.render({...p,status:"answered"});
assert.equal(elements.get("mode-guidance").hidden,true);
assert.equal(elements.get("mode-guidance").textContent,"");
"""
    payload = {
        "status": status,
        "query_kind": mode,
        "request_id": "test",
        "rows": [],
        "reason": "concept_not_mapped",
        "clarification": "<script>Return the return rate</script>",
    }
    subprocess.run(
        [
            node,
            "-e",
            probe,
            str(ROOT / "tools/dev_web/app.js"),
            json.dumps(payload),
            json.dumps(enabled),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
