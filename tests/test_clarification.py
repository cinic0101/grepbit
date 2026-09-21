"""P3.1 design_seen/exposed synthetic admission checks; no evaluation assets."""
from collections import UserString
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
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


MONTHS = {
    "february": ("2026-02-01T00:00:00+08:00", "2026-03-01T00:00:00+08:00"),
    "march": ("2026-03-01T00:00:00+08:00", "2026-04-01T00:00:00+08:00"),
    "april": ("2026-04-01T00:00:00+08:00", "2026-05-01T00:00:00+08:00"),
}
COUNT_VALUES = ("booked_seats", "known_booking_accounts", "attendance_visits", "distinct_people")
METRIC_VALUES = ("confirmed_booked_amount", "cash_received", "posted_refunds", "profit")
KINDS = ("count_basis", "metric_meaning", "center", "comparison_roles")


def period(month="march", utc=False):
    values = tuple(datetime.fromisoformat(value) for value in MONTHS[month])
    return tuple(value.astimezone(timezone.utc) for value in values) if utc else values


def overview(code="DEV-A", month="march", utc=False):
    return OverviewRequest(code, *period(month, utc), "Asia/Taipei")


def comparison(current="march", baseline="february", utc=False):
    return CompareRequest(*(
        FactRequest(("confirmed_booked_amount",), *period(month, utc), "Asia/Taipei")
        for month in (current, baseline)
    ))


def clarification(kind="count_basis", size=2):
    if kind in ("count_basis", "metric_meaning"):
        cls, values = ((CountBasis, COUNT_VALUES) if kind == "count_basis"
                       else (MetricMeaning, METRIC_VALUES))
        scope = overview()
        semantics = tuple(cls(scope, value) for value in values[:size])
    elif kind == "center":
        semantics = tuple(Center(overview(code)) for code in ("DEV-A", "DEV-B", "DEV-C", "DEV-D")[:size])
    else:
        semantics = (ComparisonRoles(comparison()), ComparisonRoles(comparison("february", "march")))
    return Clarification(kind, tuple(
        SemanticChoice(f"option_{index}", value) for index, value in enumerate(semantics, 1)
    ))


class ClarificationTests(unittest.TestCase):
    def setUp(self):
        for target in (
            "sqlite3.connect", "grepbit.execute_facts", "grepbit.execute_grouped_amount",
            "grepbit.execute_overview", "grepbit.execute_compare", "grepbit.execute_breakdown",
            "grepbit.kernel.execute_facts", "grepbit.grouped.execute_grouped_amount",
            "grepbit.overview.execute_overview", "grepbit.compare.execute_compare",
            "grepbit.breakdown.execute_breakdown",
        ):
            poison = patch(target, side_effect=AssertionError("Clarification must remain pure."))
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

    def test_typed_semantics_have_exact_wire_shapes_and_retain_native_requests(self):
        scope, request = overview(), comparison()
        examples = (
            (CountBasis(scope, "booked_seats"),
             {"type": "count_basis", "scope": scope.to_dict(), "value": "booked_seats"}, "scope", scope),
            (MetricMeaning(scope, "confirmed_booked_amount"),
             {"type": "metric_meaning", "scope": scope.to_dict(), "value": "confirmed_booked_amount"},
             "scope", scope),
            (Center(scope), {"type": "center", "request": scope.to_dict()}, "request", scope),
            (ComparisonRoles(request), {"type": "comparison_roles", "request": request.to_dict()},
             "request", request),
        )
        for semantic, expected, field, native in examples:
            with self.subTest(type=expected["type"]):
                self.assertIs(getattr(semantic, field), native)
                self.assertEqual(semantic.to_dict(), expected)
                choice = SemanticChoice("Choice_1", semantic)
                wire = {"id": "Choice_1", "semantic_value": expected}
                self.assertIs(choice.semantic_value, semantic)
                self.assertEqual(choice.to_dict(), wire)
                parsed = SemanticChoice.from_mapping(json.loads(json.dumps(wire)))
                self.assertEqual(parsed, choice)
                self.assertIs(type(parsed.semantic_value), type(semantic))
                self.assertIs(type(getattr(parsed.semantic_value, field)), type(native))

    def test_inner_round_trips_admit_two_to_four_choices_without_default_or_ranking(self):
        for kind in KINDS:
            for size in ((2,) if kind == "comparison_roles" else (2, 3, 4)):
                with self.subTest(kind=kind, size=size):
                    original = clarification(kind, size)
                    expected = {"kind": kind, "choices": [choice.to_dict() for choice in original.choices]}
                    self.assertEqual(original.to_dict(), expected)
                    parsed = Clarification.from_mapping(json.loads(json.dumps(expected)))
                    self.assertEqual(parsed, original)
                    self.assertIsInstance(parsed.choices, tuple)
                    reversed_choices = tuple(reversed(original.choices))
                    reordered = Clarification(kind, reversed_choices)
                    self.assertEqual(reordered.choices, reversed_choices)
                    self.assertEqual(Clarification.from_mapping(reordered.to_dict()), reordered)

    def test_choice_ids_are_ascii_bounded_and_case_sensitive(self):
        semantic = CountBasis(overview(), "booked_seats")
        for identifier in ("A", "a", "A0_-", "Z" + "0" * 31):
            with self.subTest(valid=identifier):
                choice = SemanticChoice(identifier, semantic)
                self.assertEqual(SemanticChoice.from_mapping(choice.to_dict()), choice)
        invalid = (
            None, True, 1, 1.5, [], {}, (), b"A", "", "1a", "_a", "-a", "a b",
            "a.b", "a/b", "a:b", "a\n", " a", "a ", "\u00e9", "A\u00e9", "\ud800",
            "A" * 33, "A" * 100_000,
        )
        for index, identifier in enumerate(invalid):
            with self.subTest(case=index):
                self.invalid(SemanticChoice, identifier, semantic)
                self.invalid(SemanticChoice.from_mapping, {
                    "id": identifier, "semantic_value": semantic.to_dict(),
                })
        choices = (SemanticChoice("A", semantic),
                   SemanticChoice("a", CountBasis(overview(), "distinct_people")))
        self.assertEqual(Clarification("count_basis", choices).choices, choices)

    def test_semantic_constructors_reject_untyped_scopes_and_closed_enum_violations(self):
        scope, request = overview(), comparison()
        for cls, value in ((CountBasis, "booked_seats"), (MetricMeaning, "confirmed_booked_amount")):
            for index, bad in enumerate((None, True, 1, [], {}, scope.to_dict(), request)):
                with self.subTest(cls=cls.__name__, scope=index):
                    self.invalid(cls, bad, value)
            other_enum = METRIC_VALUES if cls is CountBasis else COUNT_VALUES
            for index, bad in enumerate((
                None, True, 1, [], {}, (), "", "\ud800", "RAW_PRIVATE_ENUM", "x" * 100_000,
                "confirmed_booking_count", "BOOKED_SEATS", "booked_seats ", "cash",
            ) + other_enum):
                with self.subTest(cls=cls.__name__, value=index):
                    self.invalid(cls, scope, bad)
                    data = SemanticChoice("choice", cls(scope, value)).to_dict()
                    data["semantic_value"]["value"] = bad
                    self.invalid(SemanticChoice.from_mapping, data)
        for cls, wrong in ((Center, request), (ComparisonRoles, scope)):
            for index, bad in enumerate((None, True, 1, [], {}, wrong, wrong.to_dict())):
                with self.subTest(cls=cls.__name__, request=index):
                    self.invalid(cls, bad)
        for index, bad in enumerate((None, True, 1, [], {}, scope, request, "count_basis")):
            with self.subTest(semantic=index):
                self.invalid(SemanticChoice, "choice", bad)

    def test_mapping_rejects_nonobjects_missing_fields_and_outer_action_envelopes(self):
        action = clarification().to_dict()
        choice = action["choices"][0]
        for function, valid in ((Clarification.from_mapping, action), (SemanticChoice.from_mapping, choice)):
            invalid = [None, True, 1, 1.5, "", b"{}", [], (), set(), {}]
            invalid += [{key: value for key, value in valid.items() if key != missing} for missing in valid]
            for index, data in enumerate(invalid):
                with self.subTest(parser=function.__qualname__, case=index):
                    self.invalid(function, data)
        self.invalid(Clarification.from_mapping, {"outcome": "clarify", "clarification": action})
        self.invalid(Clarification.from_mapping, {"kind": "count_basis", "choices": tuple(action["choices"])})
        for index, value in enumerate((None, True, 1, "", [], (), {}, {"value": "booked_seats"})):
            with self.subTest(semantic_shape=index):
                self.invalid(SemanticChoice.from_mapping, dict(choice, semantic_value=value))

    def test_unknown_fields_fail_closed_at_every_semantic_layer(self):
        extras = {
            "rank": 1, "recommended": True, "default": "option_1", "selected": True,
            "formula": "RAW_PRIVATE_FORMULA", "sql": "RAW_PRIVATE_SQL", "task": {},
            "ui": {}, "data": [], "label": "RAW_PRIVATE_LABEL", "request": {},
        }
        for kind in KINDS:
            valid = clarification(kind).to_dict()
            for layer in ("root", "choice", "semantic"):
                for key, value in extras.items():
                    data = deepcopy(valid)
                    target = (data if layer == "root" else data["choices"][0] if layer == "choice"
                              else data["choices"][0]["semantic_value"])
                    if key in target:
                        continue
                    target[key] = value
                    with self.subTest(kind=kind, layer=layer, field=key):
                        self.invalid(Clarification.from_mapping, data)
            semantic = valid["choices"][0]["semantic_value"]
            for missing in semantic:
                data = deepcopy(valid)
                del data["choices"][0]["semantic_value"][missing]
                with self.subTest(kind=kind, missing=missing):
                    self.invalid(Clarification.from_mapping, data)

    def test_unknown_kinds_semantic_tags_and_mismatched_types_are_invalid_requests(self):
        original = clarification()
        for index, value in enumerate((
            None, True, 1, [], {}, (), "", "time_scope", "multiple", "COUNT_BASIS",
            "RAW_PRIVATE_KIND", "\ud800", "x" * 100_000,
        )):
            with self.subTest(kind=index):
                self.invalid(Clarification, value, original.choices)
                self.invalid(Clarification.from_mapping, dict(original.to_dict(), kind=value))
            data = original.choices[0].to_dict()
            data["semantic_value"]["type"] = value
            with self.subTest(tag=index):
                self.invalid(SemanticChoice.from_mapping, data)
        for kind in KINDS:
            original = clarification(kind)
            for other_kind in KINDS:
                if other_kind == kind:
                    continue
                wrong = SemanticChoice("other", clarification(other_kind).choices[0].semantic_value)
                choices = (original.choices[0], wrong)
                with self.subTest(kind=kind, other=other_kind):
                    self.invalid(Clarification, kind, choices)
                    self.invalid(Clarification.from_mapping, {
                        "kind": kind, "choices": [choice.to_dict() for choice in choices],
                    })

    def test_mutable_string_like_values_cannot_bypass_enum_kind_or_tag_type_guards(self):
        for cls, kind, value in (
            (CountBasis, "count_basis", "booked_seats"),
            (MetricMeaning, "metric_meaning", "confirmed_booked_amount"),
        ):
            with self.subTest(kind=kind, field="value", path="constructor"):
                self.invalid(cls, overview(), UserString(value))
            data = SemanticChoice("choice", cls(overview(), value)).to_dict()
            data["semantic_value"]["value"] = UserString(value)
            with self.subTest(kind=kind, field="value", path="mapping"):
                self.invalid(SemanticChoice.from_mapping, data)
        for kind in KINDS:
            original = clarification(kind)
            with self.subTest(kind=kind, field="kind", path="constructor"):
                self.invalid(Clarification, UserString(kind), original.choices)
            data = original.to_dict()
            data["kind"] = UserString(kind)
            with self.subTest(kind=kind, field="kind", path="mapping"):
                self.invalid(Clarification.from_mapping, data)
            data = original.choices[0].to_dict()
            data["semantic_value"]["type"] = UserString(kind)
            with self.subTest(kind=kind, field="type", path="mapping"):
                self.invalid(SemanticChoice.from_mapping, data)

    def test_choice_collection_bounds_types_and_duplicate_ids(self):
        valid = clarification("center", 4)
        fifth = SemanticChoice("fifth", Center(overview("DEV-E")))
        for index, value in enumerate((
            None, True, 1, "", {}, [], list(valid.choices), (), valid.choices[:1],
            valid.choices + (fifth,), (valid.choices[0], None),
            (valid.choices[0], valid.choices[1].to_dict()),
        )):
            with self.subTest(constructor=index):
                self.invalid(Clarification, "center", value)
        for index, value in enumerate((
            None, True, 1, "", {}, (), [], valid.to_dict()["choices"][:1],
            valid.to_dict()["choices"] + [fifth.to_dict()], [valid.choices[0].to_dict(), True],
        )):
            with self.subTest(mapping=index):
                self.invalid(Clarification.from_mapping, {"kind": "center", "choices": value})
        duplicate_id = replace(valid.choices[1], id=valid.choices[0].id)
        self.invalid(Clarification, "center", (valid.choices[0], duplicate_id))
        self.invalid(Clarification.from_mapping, {
            "kind": "center", "choices": [valid.choices[0].to_dict(), duplicate_id.to_dict()],
        })

    def test_count_and_metric_meanings_require_supported_alternative_and_same_scope(self):
        for kind, cls, values in (
            ("count_basis", CountBasis, COUNT_VALUES), ("metric_meaning", MetricMeaning, METRIC_VALUES),
        ):
            for size in (2, 3):
                choices = tuple(SemanticChoice(f"c{index}", cls(overview(), value))
                                for index, value in enumerate(values[1:1 + size]))
                with self.subTest(kind=kind, missing_supported=size):
                    self.invalid(Clarification, kind, choices)
                    self.invalid(Clarification.from_mapping, {
                        "kind": kind, "choices": [choice.to_dict() for choice in choices],
                    })
            for changed in (overview("DEV-B"), overview(month="april")):
                choices = (SemanticChoice("one", cls(overview(), values[0])),
                           SemanticChoice("two", cls(changed, values[1])))
                with self.subTest(kind=kind, scope=changed.to_dict()):
                    self.invalid(Clarification, kind, choices)
                    self.invalid(Clarification.from_mapping, {
                        "kind": kind, "choices": [choice.to_dict() for choice in choices],
                    })
            choices = (SemanticChoice("one", cls(overview(), values[0])),
                       SemanticChoice("two", cls(overview(utc=True), values[-1])))
            self.assertEqual(Clarification(kind, choices).choices, choices)

    def test_equivalent_offsets_do_not_create_distinct_semantic_alternatives(self):
        for kind in KINDS:
            original = clarification(kind)
            first = original.choices[0]
            if kind in ("count_basis", "metric_meaning"):
                equivalent = replace(first.semantic_value, scope=overview(utc=True))
            elif kind == "center":
                equivalent = Center(overview(utc=True))
            else:
                equivalent = ComparisonRoles(comparison(utc=True))
            for semantic in (first.semantic_value, equivalent):
                choices = (first, SemanticChoice("different_id", semantic))
                with self.subTest(kind=kind, equivalent_offset=semantic is equivalent):
                    self.invalid(Clarification, kind, choices)
                    self.invalid(Clarification.from_mapping, {
                        "kind": kind, "choices": [choice.to_dict() for choice in choices],
                    })

    def test_centers_keep_one_period_and_exact_distinct_codes_without_lookup(self):
        for code in ("DEV-B", "dev-a", "\u4e2d\u5fc3"):
            choices = (SemanticChoice("first", Center(overview())),
                       SemanticChoice("second", Center(overview(code, utc=True))))
            with self.subTest(code=code):
                parsed = Clarification.from_mapping(Clarification("center", choices).to_dict())
                self.assertEqual(parsed.choices, choices)
                parsed.validate_question(f"Choose DEV-A or {code}; no entity lookup is authorized.")
        choices = (SemanticChoice("first", Center(overview())),
                   SemanticChoice("second", Center(overview("DEV-B", "april"))))
        self.invalid(Clarification, "center", choices)
        self.invalid(Clarification.from_mapping, {
            "kind": "center", "choices": [choice.to_dict() for choice in choices],
        })

    def test_comparison_roles_are_exact_reversals_not_a_third_month_or_orientation(self):
        forward = SemanticChoice("forward", ComparisonRoles(comparison()))
        reverse = SemanticChoice("reverse", ComparisonRoles(comparison("february", "march", utc=True)))
        valid = Clarification("comparison_roles", (forward, reverse))
        self.assertEqual(Clarification.from_mapping(valid.to_dict()), valid)
        for request in (
            comparison(), comparison("february", "april"), comparison("april", "march"),
            comparison("march", "april"),
        ):
            choices = (forward, SemanticChoice("other", ComparisonRoles(request)))
            with self.subTest(request=request.to_dict()):
                self.invalid(Clarification, "comparison_roles", choices)
                self.invalid(Clarification.from_mapping, {
                    "kind": "comparison_roles", "choices": [choice.to_dict() for choice in choices],
                })
        for count in (3, 4):
            choices = (forward, reverse) + tuple(
                SemanticChoice(f"extra{index}", ComparisonRoles(comparison("april", "february")))
                for index in range(count - 2)
            )
            with self.subTest(count=count):
                self.invalid(Clarification, "comparison_roles", choices)
                self.invalid(Clarification.from_mapping, {
                    "kind": "comparison_roles", "choices": [choice.to_dict() for choice in choices],
                })

    def test_overview_semantic_mappings_keep_native_calendar_code_and_scope_validation(self):
        changes = [
            ("center_code", value) for value in (None, True, [], {}, "", "\ud800", "x" * 65)
        ] + [
            (field, value) for field in ("start", "end")
            for value in (None, True, [], {}, "", "March", "2026-03", "\ud800")
        ] + [
            ("start", "2026-03-01T00:00:00"), ("start", "2026-02-30T00:00:00+08:00"),
            ("start", "2026-03-02T00:00:00+08:00"), ("end", "2026-05-01T00:00:00+08:00"),
            ("end", "2026-03-01T00:00:00+08:00"), ("timezone", "UTC"),
            ("timezone", "Asia/Shanghai"), ("timezone", True), ("timezone", []),
            ("metrics", ["booked_seats"]), ("center_id", "DEV-A"),
            ("filters", {}), ("formula", "RAW_PRIVATE_FORMULA"),
        ]
        for kind in ("count_basis", "metric_meaning", "center"):
            valid = clarification(kind).choices[0].to_dict()
            field = "request" if kind == "center" else "scope"
            for index, value in enumerate((None, True, 1, "", [], (), overview())):
                data = deepcopy(valid)
                data["semantic_value"][field] = value
                with self.subTest(kind=kind, scope_shape=index):
                    self.invalid(SemanticChoice.from_mapping, data)
            for index, (key, value) in enumerate(changes):
                data = deepcopy(valid)
                data["semantic_value"][field][key] = value
                with self.subTest(kind=kind, change=index):
                    self.invalid(SemanticChoice.from_mapping, data)
            for missing in valid["semantic_value"][field]:
                data = deepcopy(valid)
                del data["semantic_value"][field][missing]
                with self.subTest(kind=kind, missing=missing):
                    self.invalid(SemanticChoice.from_mapping, data)

    def test_compare_semantic_mapping_keeps_native_metric_filter_and_month_constraints(self):
        valid = clarification("comparison_roles").choices[0].to_dict()
        for index, value in enumerate((None, True, 1, "", [], (), comparison())):
            data = deepcopy(valid)
            data["semantic_value"]["request"] = value
            with self.subTest(request_shape=index):
                self.invalid(SemanticChoice.from_mapping, data)
        changes = (
            ("metrics", ["booked_seats"]), ("metrics", ["confirmed_booked_amount", "booked_seats"]),
            ("metrics", []), ("metrics", True), ("metrics", [{}]), ("center_id", "DEV-A"),
            ("timezone", "UTC"), ("timezone", []), ("start", "2026-03"),
            ("start", True), ("start", {}), ("end", []), ("end", "\ud800"),
            ("filters", {}), ("formula", "RAW_PRIVATE_FORMULA"), ("periods", []),
        )
        for role in ("current", "baseline"):
            for index, value in enumerate((None, True, 1, "", [], (), comparison().current)):
                data = deepcopy(valid)
                data["semantic_value"]["request"][role] = value
                with self.subTest(role=role, scope_shape=index):
                    self.invalid(SemanticChoice.from_mapping, data)
            data = deepcopy(valid)
            del data["semantic_value"]["request"][role]
            with self.subTest(missing_role=role):
                self.invalid(SemanticChoice.from_mapping, data)
            for index, (key, value) in enumerate(changes):
                data = deepcopy(valid)
                data["semantic_value"]["request"][role][key] = value
                with self.subTest(role=role, change=index):
                    self.invalid(SemanticChoice.from_mapping, data)
            for missing in ("metrics", "start", "end", "timezone"):
                data = deepcopy(valid)
                del data["semantic_value"]["request"][role][missing]
                with self.subTest(role=role, missing=missing):
                    self.invalid(SemanticChoice.from_mapping, data)
        for start, end in (
            ("2026-03-02T00:00:00+08:00", MONTHS["march"][1]),
            (MONTHS["march"][0], MONTHS["april"][1]),
            (MONTHS["march"][0], MONTHS["march"][0]),
            ("2026-03-01T00:00:00Z", "2026-04-01T00:00:00Z"),
        ):
            data = deepcopy(valid)
            data["semantic_value"]["request"]["current"].update(start=start, end=end)
            with self.subTest(period=(start, end)):
                self.invalid(SemanticChoice.from_mapping, data)
        data = deepcopy(valid)
        data["semantic_value"]["request"]["baseline"] = comparison(utc=True).current.to_dict()
        self.invalid(SemanticChoice.from_mapping, data)
        data = deepcopy(valid)
        data["semantic_value"]["request"]["third"] = comparison().baseline.to_dict()
        self.invalid(SemanticChoice.from_mapping, data)
        for role in ("current", "baseline"):
            data = deepcopy(valid)
            del data["semantic_value"]["request"][role]["center_id"]
            self.assertEqual(SemanticChoice.from_mapping(data), SemanticChoice.from_mapping(valid))

    def test_question_literals_use_ascii_code_boundaries_and_allow_multilingual_adjacency(self):
        for kind in ("count_basis", "metric_meaning", "center"):
            value = clarification(kind)
            suffix = " or DEV-B" if kind == "center" else ""
            for text in ("DEV-A", "(DEV-A)", "[DEV-A]", "DEV-A/choice", "\u4e2dDEV-A\u4e2d",
                         "\u00e9DEV-A\u00e9"):
                with self.subTest(kind=kind, accepted=text):
                    value.validate_question(text + suffix)
            for text in (
                "", "DEV", "dev-a", "DEV-A1", "XDEV-A", "_DEV-A", "DEV-A_",
                "DEV-A-extra", "pre-DEV-A", "DEV-Aextra", "DEV-A\nXDEV-B" if kind == "center" else "DEV-B",
            ):
                with self.subTest(kind=kind, rejected=text):
                    self.invalid(value.validate_question, text + suffix if "XDEV-B" not in text else text)
        self.invalid(clarification("center").validate_question, "DEV-A only")
        self.invalid(clarification("center").validate_question, "DEV-B only")

    def test_question_validation_is_literal_not_alias_resolution_or_nlp_date_grounding(self):
        for code in ("DEV.+(A)", " DEV-A ", "DEV-NOT-IN-A-DATABASE", "\u4e2d\u5fc3"):
            value = Clarification("count_basis", (
                SemanticChoice("seats", CountBasis(overview(code), "booked_seats")),
                SemanticChoice("people", CountBasis(overview(code), "distinct_people")),
            ))
            with self.subTest(code=code):
                value.validate_question(f"Choose ({code}) without an inferred date.")
                self.invalid(value.validate_question, "RAW_PRIVATE_QUESTION_WITHOUT_THE_CODE")
        value = clarification()
        value.validate_question("DEV-A, with no date to parse.")
        value.validate_question("DEV-A in an unrelated prose month; calendar grounding is not proved here.")
        for code, nonliteral in (("DEV.+(A)", "DEVzzA"), (" DEV-A ", "DEV-A")):
            choices = (SemanticChoice("seats", CountBasis(overview(code), "booked_seats")),
                       SemanticChoice("people", CountBasis(overview(code), "distinct_people")))
            with self.subTest(code=code, nonliteral=nonliteral):
                self.invalid(Clarification("count_basis", choices).validate_question, nonliteral)
        clarification("comparison_roles").validate_question("No center literal is required.")
        for kind in KINDS:
            for index, question in enumerate((None, True, 1, [], {}, (), b"DEV-A")):
                with self.subTest(kind=kind, question=index):
                    self.invalid(clarification(kind).validate_question, question)

    def test_semantic_objects_and_nested_native_values_are_frozen_and_repr_safe(self):
        for kind in KINDS:
            value = clarification(kind)
            choice = value.choices[0]
            semantic = choice.semantic_value
            native_field = "scope" if kind in ("count_basis", "metric_meaning") else "request"
            native = getattr(semantic, native_field)
            objects = ((value, "kind"), (choice, "id"), (semantic, native_field))
            for obj, field in objects:
                with self.subTest(kind=kind, cls=type(obj).__name__):
                    self.assertTrue(obj.__dataclass_params__.frozen)
                    self.assertFalse(obj.__dataclass_params__.repr)
                    self.assertNotIn("DEV-A", repr(obj))
                    self.assertNotIn("option_1", repr(obj))
                    with self.assertRaises(FrozenInstanceError):
                        setattr(obj, field, None)
            with self.assertRaises(FrozenInstanceError):
                setattr(native, "current" if kind == "comparison_roles" else "center_code", None)
            if kind == "comparison_roles":
                with self.assertRaises(FrozenInstanceError):
                    native.current.metrics = ("booked_seats",)

    def test_parsed_values_and_exports_do_not_alias_mutable_source_mappings(self):
        for kind in KINDS:
            data = clarification(kind).to_dict()
            expected = deepcopy(data)
            parsed = Clarification.from_mapping(data)
            semantic = data["choices"][0]["semantic_value"]
            field = "scope" if kind in ("count_basis", "metric_meaning") else "request"
            native = semantic[field]
            if kind == "comparison_roles":
                native["current"]["metrics"].append("booked_seats")
                native["baseline"]["start"] = "RAW_PRIVATE_DATE"
            else:
                native["center_code"] = "RAW_PRIVATE_CENTER"
            semantic["type"] = "RAW_PRIVATE_TYPE"
            data["choices"][0]["id"] = "RAW_PRIVATE_ID"
            data["choices"].append({})
            data["kind"] = "RAW_PRIVATE_KIND"
            with self.subTest(kind=kind):
                self.assertEqual(parsed.to_dict(), expected)
                exported = parsed.to_dict()
                exported["choices"][0]["semantic_value"][field].clear()
                exported["choices"].clear()
                self.assertEqual(parsed.to_dict(), expected)
                self.assertEqual(Clarification.from_mapping(parsed.to_dict()), parsed)

    def test_invalid_content_has_fixed_safe_messages_not_raw_input(self):
        scope = overview()
        checks = (
            lambda marker: self.invalid(CountBasis, scope, marker),
            lambda marker: self.invalid(MetricMeaning, scope, marker),
            lambda marker: self.invalid(SemanticChoice, "bad/" + marker, CountBasis(scope, "booked_seats")),
            lambda marker: self.invalid(Clarification, marker, clarification().choices),
            lambda marker: self.invalid(clarification().validate_question, marker),
            lambda marker: self.invalid(SemanticChoice.from_mapping, {
                "id": "choice", "semantic_value": {"type": marker, "request": scope.to_dict()},
            }),
        )
        for index, check in enumerate(checks):
            with self.subTest(category=index):
                self.assertEqual(check("RAW_PRIVATE_ALPHA"), check("RAW_PRIVATE_BETA"))


if __name__ == "__main__":
    unittest.main()
