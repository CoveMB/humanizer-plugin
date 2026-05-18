import unittest

from tests.helpers.output_contracts import validate_case_output
from tests.helpers.skill_artifacts import load_fixture_cases


BASE_CASE = {
    "id": "example",
    "constraints": {
        "must_include": ["Atlas Note", "43%"],
        "must_not_include": ["Gartner", "Let me know"],
        "must_match": ["Atlas Note"],
        "must_not_match": ["(?i)game[- ]changer"],
        "no_em_dash": True,
        "no_chatbot_wrapper": True,
        "no_contrast_frame": True,
        "no_markdown_fence": True,
        "rewrite_only": True,
        "max_question_marks": 0,
    },
}


class OutputContractTests(unittest.TestCase):
    def test_dense_ai_rewrite_rejects_live_rubric_failure(self):
        cases = {case["id"]: case for case in load_fixture_cases()}

        with self.assertRaisesRegex(AssertionError, "forbidden fragment"):
            validate_case_output(
                cases["dense_ai_rewrite"],
                (
                    "AI coding assistants are useful because they take some of the grind "
                    "out of software work. They can help draft documentation, improve "
                    "tests, and fill in routine code faster than a developer would want "
                    "to do by hand. Autocomplete is part of it, but the bigger value is "
                    "having a tool that can work through rough edges while the developer "
                    "stays focused on the actual problem."
                ),
            )

    def test_dense_ai_rewrite_rejects_invented_third_work_category(self):
        cases = {case["id"]: case for case in load_fixture_cases()}

        with self.assertRaisesRegex(AssertionError, "forbidden pattern"):
            validate_case_output(
                cases["dense_ai_rewrite"],
                "AI coding assistants can help with documentation, tests, and refactors.",
            )

    def test_accepts_output_that_satisfies_constraints(self):
        output = "Atlas Note adoption rose 43%. The source is unnamed, so the claim should stay general."
        validate_case_output(BASE_CASE, output)

    def test_rejects_missing_required_fact(self):
        with self.assertRaises(AssertionError):
            validate_case_output(BASE_CASE, "Adoption rose last quarter.")

    def test_required_fragments_are_case_insensitive(self):
        validate_case_output(
            {"id": "required", "constraints": {"must_include": ["Atlas Note"]}},
            "atlas note adoption rose 43%. The source is unnamed, so the claim should stay general.",
        )

    def test_rejects_unsupported_constraint_keys(self):
        case = {"id": "unsupported", "constraints": {"must_includ": ["Atlas Note"]}}

        with self.assertRaisesRegex(AssertionError, "unsupported constraint"):
            validate_case_output(case, "Atlas Note adoption rose 43%.")

    def test_rejects_forbidden_fragment(self):
        with self.assertRaises(AssertionError):
            validate_case_output(BASE_CASE, "Atlas Note rose 43%, according to Gartner.")

    def test_rejects_forbidden_pattern(self):
        with self.assertRaises(AssertionError):
            validate_case_output(BASE_CASE, "Atlas Note rose 43%. This is a game-changer.")

    def test_rejects_missing_required_pattern(self):
        case = {"id": "score", "constraints": {"must_match": [r"Score:\s+\d+/80"]}}
        with self.assertRaises(AssertionError):
            validate_case_output(case, "Score unavailable.")

    def test_rejects_em_dash(self):
        with self.assertRaises(AssertionError):
            validate_case_output(BASE_CASE, "Atlas Note rose 43% \u2014 source unnamed.")

    def test_rejects_chatbot_wrapper_start(self):
        with self.assertRaises(AssertionError):
            validate_case_output(BASE_CASE, "Here is the rewritten version: Atlas Note rose 43%.")

    def test_rejects_too_many_question_marks(self):
        case = {"id": "questions", "constraints": {"max_question_marks": 1}}
        with self.assertRaises(AssertionError):
            validate_case_output(case, "What changed? Who reported it?")

    def test_rejects_markdown_fence_when_disallowed(self):
        case = {"id": "fence", "constraints": {"no_markdown_fence": True}}
        with self.assertRaises(AssertionError):
            validate_case_output(case, "```text\nAtlas Note rose 43%.\n```")

    def test_rejects_contrast_frame_when_disallowed(self):
        case = {"id": "contrast", "constraints": {"no_contrast_frame": True}}
        with self.assertRaises(AssertionError):
            validate_case_output(
                case,
                "AI coding assistants are not a replacement for engineers, but they help.",
            )

    def test_rejects_forced_rule_of_three_when_disallowed(self):
        case = {"id": "rule_of_three", "constraints": {"no_rule_of_three": True}}
        with self.assertRaisesRegex(AssertionError, "rule-of-three"):
            validate_case_output(
                case,
                "NovaBuild gives teams a robust, scalable, and innovative dashboard.",
            )

    def test_allows_concrete_source_backed_three_item_list(self):
        case = {
            "id": "concrete_list",
            "source": "The release includes documentation, tests, and refactors.",
            "constraints": {"no_rule_of_three": True},
        }

        validate_case_output(
            case,
            "The release includes documentation, tests, and refactors.",
        )

    def test_rejects_alignment_filler_in_three_item_list(self):
        case = {"id": "alignment_list", "constraints": {"no_rule_of_three": True}}
        with self.assertRaisesRegex(AssertionError, "rule-of-three"):
            validate_case_output(
                case,
                "AI coding assistants help with documentation, tests, and keeping teams aligned.",
            )

    def test_rejects_rewrite_only_meta_commentary(self):
        case = {"id": "rewrite", "constraints": {"rewrite_only": True}}
        with self.assertRaises(AssertionError):
            validate_case_output(case, "Atlas Note rose 43%.\n\nNotes: Removed AI phrasing.")

    def test_rejects_numbers_not_present_in_source_when_source_aware(self):
        case = {
            "id": "numbers",
            "source": "Atlas Note adoption rose 43% last quarter.",
            "constraints": {"no_new_numbers": True},
        }

        with self.assertRaisesRegex(AssertionError, "introduced number"):
            validate_case_output(case, "Atlas Note adoption rose 43% in 2026.")

    def test_rejects_named_entities_not_present_in_source_when_source_aware(self):
        case = {
            "id": "entities",
            "source": "Atlas Note adoption rose 43% last quarter.",
            "constraints": {"no_new_named_entities": True},
        }

        with self.assertRaisesRegex(AssertionError, "introduced named entity"):
            validate_case_output(
                case,
                "Atlas Note adoption rose 43%, according to Acme Research.",
            )

    def test_rejects_single_word_attribution_source_not_present_in_source(self):
        case = {
            "id": "single_word_entity",
            "source": "Atlas Note adoption rose 43% last quarter.",
            "constraints": {"no_new_named_entities": True},
        }

        with self.assertRaisesRegex(AssertionError, "introduced named entity"):
            validate_case_output(
                case,
                "Atlas Note adoption rose 43%, according to Gartner.",
            )

    def test_rejects_single_word_reporting_source_not_present_in_source(self):
        case = {
            "id": "single_word_reporting_source",
            "source": "The release includes offline comments and faster issue search.",
            "constraints": {"no_new_named_entities": True},
        }

        with self.assertRaisesRegex(AssertionError, "introduced named entity"):
            validate_case_output(
                case,
                "Gartner says the release includes offline comments and faster issue search.",
            )

    def test_allows_source_backed_single_word_reporting_source(self):
        case = {
            "id": "source_backed_reporting_source",
            "source": "Gartner says Atlas Note adoption rose 43% last quarter.",
            "constraints": {"no_new_named_entities": True},
        }

        validate_case_output(
            case,
            "Gartner says Atlas Note adoption rose 43% last quarter.",
        )

    def test_allows_question_word_before_reports_when_asking_for_missing_source(self):
        case = {
            "id": "missing_source_question",
            "source": "Industry reports show that Atlas Note adoption increased by 43% last quarter.",
            "constraints": {"no_new_named_entities": True},
        }

        validate_case_output(
            case,
            "Which reports support Atlas Note's 43% adoption increase last quarter?",
        )

    def test_rewrite_scoped_forbidden_fragments_allow_audit_notes(self):
        case = {
            "id": "audit",
            "constraints": {"rewrite_must_not_include": ["unlock collaboration"]},
        }

        validate_case_output(
            case,
            "Teams collaborate better when they are aligned.\n\n"
            "Notes: Removed vague “unlock collaboration” phrasing.",
        )

    def test_rewrite_scoped_forbidden_fragments_reject_rewrite_body(self):
        case = {
            "id": "audit",
            "constraints": {"rewrite_must_not_include": ["unlock collaboration"]},
        }

        with self.assertRaisesRegex(AssertionError, "rewrite contains forbidden fragment"):
            validate_case_output(
                case,
                "Teams can unlock collaboration when they align.\n\nNotes: Revised.",
            )

    def test_reports_all_contract_violations(self):
        case = {
            "id": "aggregate",
            "constraints": {
                "must_include": ["Atlas Note", "43%"],
                "must_not_include": ["Gartner"],
                "must_match": [r"Score:\s+\d+/80"],
                "no_em_dash": True,
            },
        }

        with self.assertRaises(AssertionError) as assertion:
            validate_case_output(case, "Gartner says adoption rose - Score: 8/10.")

        message = str(assertion.exception)
        self.assertIn("missing required fragment 'Atlas Note'", message)
        self.assertIn("missing required fragment '43%'", message)
        self.assertIn("required pattern missing", message)
        self.assertIn("forbidden fragment present 'Gartner'", message)


if __name__ == "__main__":
    unittest.main()
