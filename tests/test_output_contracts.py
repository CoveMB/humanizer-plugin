import unittest

from tests.helpers.output_contracts import validate_case_output


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

    def test_rejects_rewrite_only_meta_commentary(self):
        case = {"id": "rewrite", "constraints": {"rewrite_only": True}}
        with self.assertRaises(AssertionError):
            validate_case_output(case, "Atlas Note rose 43%.\n\nNotes: Removed AI phrasing.")

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
