"""P3.1 design_seen/exposed synthetic presentation checks, without execution."""
from collections import UserString
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from grepbit.clarification import (
    Center, Clarification, ComparisonRoles, CountBasis, MetricMeaning, SemanticChoice,
)
from grepbit.compare import CompareRequest
from grepbit.contracts import FactRequest, KernelError
from grepbit.overview import OverviewRequest
from grepbit.presentation import (
    ChoiceOption, ChoicesBlock, ClarificationPresentation, render_clarification,
)


def clarification(kind="count_basis", size=2):
    february, march, april = (
        datetime.fromisoformat(value) for value in
        ("2026-02-01T00:00:00+08:00", "2026-03-01T00:00:00+08:00", "2026-04-01T00:00:00+08:00")
    )
    scope = OverviewRequest("DEV-A", march, april, "Asia/Taipei")
    if kind == "count_basis":
        values = tuple(CountBasis(scope, value) for value in (
            "booked_seats", "known_booking_accounts", "attendance_visits", "distinct_people",
        )[:size])
    elif kind == "metric_meaning":
        values = tuple(MetricMeaning(scope, value) for value in (
            "confirmed_booked_amount", "cash_received", "posted_refunds", "profit",
        )[:size])
    elif kind == "center":
        values = tuple(Center(OverviewRequest(code, march, april, "Asia/Taipei"))
                       for code in ("DEV-A", "DEV-B", "DEV-C", "DEV-D")[:size])
    else:
        current = FactRequest(("confirmed_booked_amount",), march, april, "Asia/Taipei")
        baseline = FactRequest(("confirmed_booked_amount",), february, march, "Asia/Taipei")
        values = (ComparisonRoles(CompareRequest(current, baseline)),
                  ComparisonRoles(CompareRequest(baseline, current)))
    return Clarification(kind, tuple(
        SemanticChoice(f"option_{index}", value) for index, value in enumerate(values, 1)
    ))


def options(value):
    return tuple(ChoiceOption(choice.id, f"Choice {index}") for index, choice in enumerate(value.choices, 1))


def presentation(value, text="Choose one meaning."):
    return ClarificationPresentation(text, (ChoicesBlock(options(value)),), value)


class PresentationTests(unittest.TestCase):
    def setUp(self):
        for target in (
            "sqlite3.connect", "grepbit.execute_facts", "grepbit.execute_grouped_amount",
            "grepbit.execute_overview", "grepbit.execute_compare", "grepbit.execute_breakdown",
            "grepbit.kernel.execute_facts", "grepbit.grouped.execute_grouped_amount",
            "grepbit.overview.execute_overview", "grepbit.compare.execute_compare",
            "grepbit.breakdown.execute_breakdown",
        ):
            poison = patch(target, side_effect=AssertionError("Presentation must remain pure."))
            mocked = poison.start()
            self.addCleanup(poison.stop)
            self.addCleanup(mocked.assert_not_called)

    def invalid(self, function, *args, **kwargs):
        with self.assertRaises(KernelError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, "invalid_request")
        self.assertTrue(str(raised.exception))
        self.assertNotIn("RAW_PRIVATE_", str(raised.exception))
        return str(raised.exception)

    def test_exact_wire_shapes_fixed_block_fields_and_semantic_initvar(self):
        semantic = clarification()
        first = ChoiceOption("option_1", "First meaning")
        second = ChoiceOption("option_2", "Second meaning")
        block = ChoicesBlock((first, second))
        value = ClarificationPresentation("Choose a meaning.", (block,), semantic)
        expected_options = [
            {"choice_id": "option_1", "label": "First meaning"},
            {"choice_id": "option_2", "label": "Second meaning"},
        ]
        expected_block = {"type": "choices", "selection": "single", "options": expected_options}
        self.assertEqual(first.to_dict(), expected_options[0])
        self.assertEqual(block.to_dict(), expected_block)
        self.assertEqual((block.type, block.selection), ("choices", "single"))
        block_fields = {field.name: field for field in fields(ChoicesBlock)}
        for name in ("type", "selection"):
            self.assertFalse(block_fields[name].init)
        self.assertNotIn("clarification", {field.name for field in fields(ClarificationPresentation)})
        expected = {"text": "Choose a meaning.", "blocks": [expected_block]}
        self.assertEqual(value.to_dict(), expected)
        parsed = ClarificationPresentation.from_mapping(json.loads(json.dumps(expected)), semantic)
        self.assertEqual(parsed, value)
        self.assertIsInstance(parsed.blocks, tuple)
        self.assertIsInstance(parsed.blocks[0], ChoicesBlock)
        self.assertIsInstance(parsed.blocks[0].options, tuple)
        self.assertTrue(all(isinstance(option, ChoiceOption) for option in parsed.blocks[0].options))

    def test_two_to_four_options_allow_reordering_and_localized_relabeling_only(self):
        for size in (2, 3, 4):
            semantic = clarification("count_basis", size)
            before = semantic.to_dict()
            block = ChoicesBlock(tuple(
                ChoiceOption(choice.id, f"\u9078\u9805 {index}")
                for index, choice in enumerate(reversed(semantic.choices), 1)
            ))
            rendered = ClarificationPresentation("\u8acb\u9078\u64c7\u4e00\u9805", (block,), semantic)
            with self.subTest(size=size):
                parsed = ClarificationPresentation.from_mapping(rendered.to_dict(), semantic)
                self.assertEqual(parsed, rendered)
                self.assertEqual([option.choice_id for option in parsed.blocks[0].options],
                                 [choice.id for choice in reversed(semantic.choices)])
                self.assertEqual(semantic.to_dict(), before)

    def test_text_and_labels_enforce_utf8_bytes_without_normalizing_valid_unicode(self):
        semantic = clarification()
        valid = ("x", " ", "x" * 256, "\u00e9" * 128, "\u4e2d" * 85 + "x",
                 "\U0001f642" * 64, "e\u0301" * 85 + "x")
        for index, text in enumerate(valid):
            with self.subTest(valid=index):
                option = ChoiceOption("option_1", text)
                self.assertEqual(option.label, text)
                direct = presentation(semantic, text)
                self.assertEqual(direct.text, text)
                data = direct.to_dict()
                data["blocks"][0]["options"][0]["label"] = text
                parsed = ClarificationPresentation.from_mapping(data, semantic)
                self.assertEqual(parsed.text, text)
                self.assertEqual(parsed.blocks[0].options[0].label, text)
        invalid = (
            None, True, 1, 1.5, [], {}, (), b"text", "", "\ud800", "\udfff",
            "x" * 257, "\u00e9" * 128 + "x", "\u4e2d" * 86, "\U0001f642" * 65, "x" * 100_000,
        )
        for index, text in enumerate(invalid):
            with self.subTest(invalid=index):
                self.invalid(ChoiceOption, "option_1", text)
                self.invalid(ClarificationPresentation, text, (ChoicesBlock(options(semantic)),), semantic)
                for field in ("text", "label"):
                    data = presentation(semantic).to_dict()
                    target = data if field == "text" else data["blocks"][0]["options"][0]
                    target[field] = text
                    self.invalid(ClarificationPresentation.from_mapping, data, semantic)

    def test_option_ids_reject_invalid_values_and_use_exact_case_sensitive_references(self):
        semantic = clarification()
        for identifier in ("A", "a", "A0_-", "Z" + "0" * 31):
            with self.subTest(valid=identifier):
                self.assertEqual(ChoiceOption(identifier, "Label").choice_id, identifier)
        for index, identifier in enumerate((
            None, True, 1, [], {}, (), b"option_1", "", "1option", "_option", "option 1",
            "option/1", "option\n", "\u00e9", "\ud800", "x" * 33, "x" * 100_000,
        )):
            with self.subTest(case=index):
                self.invalid(ChoiceOption, identifier, "Label")
                data = presentation(semantic).to_dict()
                data["blocks"][0]["options"][0]["choice_id"] = identifier
                self.invalid(ClarificationPresentation.from_mapping, data, semantic)
        for identifier in ("unknown", "OPTION_1"):
            block = ChoicesBlock((ChoiceOption(identifier, "Label"), ChoiceOption("option_2", "Other")))
            with self.subTest(unknown=identifier):
                self.invalid(ClarificationPresentation, "Choose.", (block,), semantic)
                self.invalid(ClarificationPresentation.from_mapping, {
                    "text": "Choose.", "blocks": [block.to_dict()],
                }, semantic)
        choices = tuple(SemanticChoice(identifier, choice.semantic_value)
                        for identifier, choice in zip(("A", "a"), semantic.choices))
        case_sensitive = Clarification(semantic.kind, choices)
        self.assertEqual(presentation(case_sensitive).to_dict()["blocks"][0]["options"],
                         [{"choice_id": "A", "label": "Choice 1"}, {"choice_id": "a", "label": "Choice 2"}])

    def test_blocks_options_and_constructor_context_reject_untyped_values(self):
        semantic = clarification()
        valid_options = options(semantic)
        block = ChoicesBlock(valid_options)
        for index, value in enumerate((
            None, True, 1, "", {}, [], list(valid_options), (),
            (valid_options[0], None), (valid_options[0], valid_options[1].to_dict()),
        )):
            with self.subTest(options=index):
                self.invalid(ChoicesBlock, value)
        for index, value in enumerate((
            None, True, 1, "", {}, [], [block], (), (None,), (block.to_dict(),), (block, block),
        )):
            with self.subTest(blocks=index):
                self.invalid(ClarificationPresentation, "Choose.", value, semantic)
        for index, value in enumerate((None, True, 1, "", [], {}, semantic.to_dict(), semantic.choices)):
            with self.subTest(context=index):
                self.invalid(ClarificationPresentation, "Choose.", (block,), value)
                self.invalid(ClarificationPresentation.from_mapping, presentation(semantic).to_dict(), value)
                self.invalid(render_clarification, value)

    def test_option_counts_duplicates_missing_and_unknown_references_fail_closed(self):
        semantic = clarification("center", 4)
        all_options = options(semantic)
        for size in (0, 1, 5):
            candidate = (all_options + (ChoiceOption("fifth", "Fifth"),))[:size]
            with self.subTest(option_count=size):
                self.invalid(ChoicesBlock, candidate)
                self.invalid(ClarificationPresentation.from_mapping, {
                    "text": "Choose.", "blocks": [{
                        "type": "choices", "selection": "single",
                        "options": [option.to_dict() for option in candidate],
                    }],
                }, semantic)
        for size in (2, 3):
            block = ChoicesBlock(all_options[:size])
            with self.subTest(missing=4 - size):
                self.invalid(ClarificationPresentation, "Choose.", (block,), semantic)
                self.invalid(ClarificationPresentation.from_mapping, {
                    "text": "Choose.", "blocks": [block.to_dict()],
                }, semantic)
        duplicate = (all_options[0], ChoiceOption(all_options[0].choice_id, "Different label"))
        self.invalid(ChoicesBlock, duplicate)
        data = presentation(clarification()).to_dict()
        data["blocks"][0]["options"] = [option.to_dict() for option in duplicate]
        self.invalid(ClarificationPresentation.from_mapping, data, clarification())
        data = presentation(clarification()).to_dict()
        data["blocks"][0]["options"].append({"choice_id": "extra", "label": "Extra meaning"})
        self.invalid(ClarificationPresentation.from_mapping, data, clarification())

    def test_mapping_is_exact_at_root_block_and_option_with_no_ui_or_execution_fields(self):
        semantic = clarification()
        valid = presentation(semantic).to_dict()
        extras = {
            "rank": 1, "recommended": True, "default": "option_1", "selected": ["option_1"],
            "formula": "RAW_PRIVATE_FORMULA", "sql": "RAW_PRIVATE_SQL", "ui": {},
            "data": [], "on_select": "RAW_PRIVATE_CALLBACK", "children": [], "columns": [],
            "rows": [], "semantic_value": semantic.choices[0].semantic_value.to_dict(),
            "clarification": semantic.to_dict(), "outcome": "clarify", "request": {},
        }
        for layer in ("root", "block", "option"):
            for key, value in extras.items():
                data = deepcopy(valid)
                target = (data if layer == "root" else data["blocks"][0] if layer == "block"
                          else data["blocks"][0]["options"][0])
                target[key] = value
                with self.subTest(layer=layer, extra=key):
                    self.invalid(ClarificationPresentation.from_mapping, data, semantic)
            template = (valid if layer == "root" else valid["blocks"][0] if layer == "block"
                        else valid["blocks"][0]["options"][0])
            for key in template:
                data = deepcopy(valid)
                target = (data if layer == "root" else data["blocks"][0] if layer == "block"
                          else data["blocks"][0]["options"][0])
                del target[key]
                with self.subTest(layer=layer, missing=key):
                    self.invalid(ClarificationPresentation.from_mapping, data, semantic)

    def test_mapping_rejects_nonobjects_nonarrays_and_nested_shape_confusion(self):
        semantic = clarification()
        for index, value in enumerate((None, True, 1, 1.5, "", b"{}", [], (), set(), {})):
            with self.subTest(root=index):
                self.invalid(ClarificationPresentation.from_mapping, value, semantic)
        for layer in ("blocks", "block", "options", "option"):
            for index, value in enumerate((None, True, 1, "", {}, [], (), b"[]")):
                data = presentation(semantic).to_dict()
                if layer == "blocks":
                    data["blocks"] = value
                elif layer == "block":
                    data["blocks"][0] = value
                elif layer == "options":
                    data["blocks"][0]["options"] = value
                else:
                    data["blocks"][0]["options"][0] = value
                with self.subTest(layer=layer, case=index):
                    self.invalid(ClarificationPresentation.from_mapping, data, semantic)
        data = presentation(semantic).to_dict()
        data["blocks"].append(deepcopy(data["blocks"][0]))
        self.invalid(ClarificationPresentation.from_mapping, data, semantic)

    def test_only_choices_single_selection_is_admitted_not_table_chart_or_multiselect(self):
        semantic = clarification()
        for field, values in (
            ("type", ("table", "chart", "text", "ui", "Choices", "", None, True, [], {}, UserString("choices"))),
            ("selection", ("multiple", "multi", "multi-select", "Single", "", None, True, [], {},
                           UserString("single"))),
        ):
            for index, value in enumerate(values):
                data = presentation(semantic).to_dict()
                data["blocks"][0][field] = value
                with self.subTest(field=field, case=index):
                    self.invalid(ClarificationPresentation.from_mapping, data, semantic)

    def test_rendering_is_deterministic_complete_and_semantic_not_id_or_position_driven(self):
        for kind in ("count_basis", "metric_meaning", "center", "comparison_roles"):
            semantic = clarification(kind, 4)
            before = semantic.to_dict()
            rendered = render_clarification(semantic)
            with self.subTest(kind=kind):
                self.assertIsInstance(rendered, ClarificationPresentation)
                self.assertEqual(render_clarification(Clarification.from_mapping(before)), rendered)
                self.assertEqual(ClarificationPresentation.from_mapping(rendered.to_dict(), semantic), rendered)
                self.assertEqual(len(rendered.blocks), 1)
                labels = {option.choice_id: option.label for option in rendered.blocks[0].options}
                self.assertEqual(set(labels), {choice.id for choice in semantic.choices})
                self.assertEqual(len(set(labels.values())), len(semantic.choices))
                reversed_semantic = Clarification(kind, tuple(reversed(semantic.choices)))
                reversed_rendering = render_clarification(reversed_semantic)
                self.assertEqual({option.choice_id: option.label
                                  for option in reversed_rendering.blocks[0].options}, labels)
                renamed = Clarification(kind, tuple(
                    SemanticChoice(f"renamed_{index}", choice.semantic_value)
                    for index, choice in enumerate(semantic.choices)
                ))
                renamed_rendering = render_clarification(renamed)
                renamed_labels = {option.choice_id: option.label
                                  for option in renamed_rendering.blocks[0].options}
                for index, choice in enumerate(semantic.choices):
                    self.assertEqual(renamed_labels[f"renamed_{index}"], labels[choice.id])
                self.assertEqual(renamed_rendering.text, rendered.text)
                self.assertEqual(semantic.to_dict(), before)

    def test_equivalent_native_timestamp_offsets_render_identical_semantic_options(self):
        def in_utc(scope):
            return replace(scope, start=scope.start.astimezone(timezone.utc),
                           end=scope.end.astimezone(timezone.utc))

        for kind in ("count_basis", "metric_meaning", "center", "comparison_roles"):
            semantic = clarification(kind, 4)
            choices = []
            for choice in semantic.choices:
                value = choice.semantic_value
                if isinstance(value, (CountBasis, MetricMeaning)):
                    value = replace(value, scope=in_utc(value.scope))
                elif isinstance(value, Center):
                    value = replace(value, request=in_utc(value.request))
                else:
                    value = ComparisonRoles(CompareRequest(
                        in_utc(value.request.current), in_utc(value.request.baseline),
                    ))
                choices.append(SemanticChoice(choice.id, value))
            equivalent = Clarification(kind, tuple(choices))
            with self.subTest(kind=kind):
                self.assertEqual(equivalent, semantic)
                self.assertEqual(render_clarification(equivalent).to_dict(),
                                 render_clarification(semantic).to_dict())

    def test_rendered_count_and_amount_meanings_name_recipe_scoped_unavailability(self):
        for kind in ("count_basis", "metric_meaning"):
            semantic = clarification(kind, 4)
            rendered = render_clarification(semantic)
            labels = {option.choice_id: option.label.lower() for option in rendered.blocks[0].options}
            supported = "booked_seats" if kind == "count_basis" else "confirmed_booked_amount"
            for choice in semantic.choices:
                meaning, label = choice.semantic_value.value, labels[choice.id]
                with self.subTest(kind=kind, meaning=meaning):
                    for term in meaning.split("_"):
                        self.assertIn(term, label)
                    if meaning == "known_booking_accounts":
                        for term in ("distinct", "exclud", "anonymous"):
                            self.assertIn(term, label)
                    if meaning == supported:
                        self.assertNotIn("not available", label)
                    else:
                        self.assertIn("not available", label)
                        self.assertIn("recipe entry", label)
                        self.assertNotIn("globally unsupported", label)
                        self.assertNotIn("unsupported by grepbit", label)

    def test_rendered_center_labels_echo_their_own_literal_codes(self):
        semantic = clarification("center", 4)
        labels = {option.choice_id: option.label for option in render_clarification(semantic).blocks[0].options}
        for choice in semantic.choices:
            with self.subTest(choice=choice.id):
                self.assertIn(choice.semantic_value.request.center_code, labels[choice.id])

    def test_presentation_and_semantic_objects_remain_immutable_after_rendering(self):
        semantic = clarification()
        rendered = render_clarification(semantic)
        block, = rendered.blocks
        first = block.options[0]
        for obj, field in (
            (rendered, "text"), (rendered, "blocks"), (block, "options"),
            (block, "type"), (block, "selection"), (first, "choice_id"), (first, "label"),
            (semantic, "choices"), (semantic.choices[0], "semantic_value"),
            (semantic.choices[0].semantic_value, "value"),
            (semantic.choices[0].semantic_value.scope, "center_code"),
        ):
            with self.subTest(cls=type(obj).__name__, field=field):
                self.assertTrue(obj.__dataclass_params__.frozen)
                with self.assertRaises(FrozenInstanceError):
                    setattr(obj, field, None)

    def test_mapping_and_export_mutations_cannot_change_presentation_or_semantics(self):
        semantic_data = clarification().to_dict()
        semantic_before = deepcopy(semantic_data)
        semantic = Clarification.from_mapping(semantic_data)
        data = presentation(semantic).to_dict()
        expected = deepcopy(data)
        parsed = ClarificationPresentation.from_mapping(data, semantic)
        data["text"] = "RAW_PRIVATE_TEXT"
        data["blocks"][0]["options"][0].update(choice_id="other", label="RAW_PRIVATE_LABEL")
        data["blocks"][0]["options"].clear()
        data["blocks"][0]["selection"] = "multiple"
        data["blocks"].clear()
        semantic_data["choices"][0]["semantic_value"]["value"] = "distinct_people"
        semantic_data["choices"].clear()
        self.assertEqual(parsed.to_dict(), expected)
        self.assertEqual(semantic.to_dict(), semantic_before)
        exported = parsed.to_dict()
        exported["blocks"][0]["options"][0]["label"] = "RAW_PRIVATE_EXPORT"
        exported["blocks"][0]["options"].clear()
        self.assertEqual(parsed.to_dict(), expected)

    def test_invalid_fields_use_fixed_safe_messages_without_echoing_content(self):
        semantic = clarification()
        messages = []
        for marker in ("RAW_PRIVATE_ALPHA", "RAW_PRIVATE_BETA"):
            data = presentation(semantic).to_dict()
            data["blocks"][0]["options"][0]["choice_id"] = marker
            unknown = self.invalid(ClarificationPresentation.from_mapping, data, semantic)
            data = presentation(semantic).to_dict()
            data["blocks"][0]["type"] = marker
            wrong_type = self.invalid(ClarificationPresentation.from_mapping, data, semantic)
            data = presentation(semantic).to_dict()
            data["blocks"][0]["selection"] = marker
            selection = self.invalid(ClarificationPresentation.from_mapping, data, semantic)
            label = self.invalid(ChoiceOption, "option_1", marker * 32)
            text = self.invalid(ClarificationPresentation, marker * 32, (ChoicesBlock(options(semantic)),), semantic)
            messages.append((unknown, wrong_type, selection, label, text))
        self.assertEqual(messages[0], messages[1])


if __name__ == "__main__":
    unittest.main()
