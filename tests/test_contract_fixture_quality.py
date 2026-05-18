import unittest

from tests.helpers.output_contracts import SUPPORTED_CONSTRAINT_KEYS
from tests.helpers.skill_artifacts import load_fixture_cases


REQUIRED_TAGS = {
    "rewrite_only_output",
    "audit_output",
    "factual_integrity",
    "missing_source_handling",
    "no_em_dash",
    "no_chatbot_wrapper",
    "no_contrast_frame",
    "no_rule_of_three",
    "no_fake_naming",
    "no_self_narration",
    "dense_banned_list",
    "voice_calibration",
    "preserve_supplied_facts",
}

SOURCE_AWARE_CONSTRAINT_KEYS = {
    "no_new_named_entities",
    "no_new_numbers",
}


class ContractFixtureQualityTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_fixture_cases()

    def test_case_ids_are_unique(self):
        case_ids = [case["id"] for case in self.cases]
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_required_tags_are_covered(self):
        covered_tags = {tag for case in self.cases for tag in case["tags"]}
        self.assertTrue(REQUIRED_TAGS.issubset(covered_tags), REQUIRED_TAGS - covered_tags)

    def test_each_case_has_prompt_source_and_constraints(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertGreater(len(case["prompt"].strip()), 20)
                self.assertGreater(len(case["source"].strip()), 20)
                self.assertIn(
                    case["mode"],
                    {"rewrite", "audit", "answer", "translate", "summary", "spellcheck"},
                )
                self.assertIsInstance(case["constraints"], dict)

    def test_constraints_use_supported_keys(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(
                    set(case["constraints"]).issubset(SUPPORTED_CONSTRAINT_KEYS)
                )

    def test_fact_preservation_cases_use_source_aware_constraints(self):
        for case in self.cases:
            tags = set(case["tags"])
            if "factual_integrity" not in tags and "preserve_supplied_facts" not in tags:
                continue

            with self.subTest(case=case["id"]):
                self.assertTrue(
                    set(case["constraints"]) & SOURCE_AWARE_CONSTRAINT_KEYS,
                    case["id"],
                )

    def test_docs_cleanup_contract_preserves_supplied_team_scope(self):
        docs_cleanup_case = next(
            case for case in self.cases if case["id"] == "contextual_docs_cleanup"
        )
        constraints = docs_cleanup_case["constraints"]

        self.assertIn("cross-functional teams", constraints["must_include"])
        self.assertNotIn("cross-functional", constraints["must_not_include"])

    def test_rule_of_three_tag_uses_matching_constraint(self):
        for case in self.cases:
            if "no_rule_of_three" not in set(case["tags"]):
                continue

            with self.subTest(case=case["id"]):
                self.assertTrue(case["constraints"].get("no_rule_of_three", False))


if __name__ == "__main__":
    unittest.main()
