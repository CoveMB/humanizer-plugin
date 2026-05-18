import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers.skill_artifacts import FIXTURE_PATH, REPO_ROOT


SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_humanizer_outputs.py"


class ValidateHumanizerOutputsScriptTests(unittest.TestCase):
    def test_script_passes_when_all_outputs_satisfy_constraints(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as output_directory:
            output_path = Path(output_directory)
            for case in fixture["cases"]:
                output_path.joinpath(f"{case['id']}.txt").write_text(
                    self._passing_output_for(case),
                    encoding="utf-8",
                )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(output_path)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("validated", result.stdout)

    def test_script_fails_when_output_file_is_missing(self):
        with tempfile.TemporaryDirectory() as output_directory:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), output_directory],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing output file", result.stderr)

    def test_script_fails_when_output_violates_contract(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as output_directory:
            output_path = Path(output_directory)
            for case in fixture["cases"]:
                output_path.joinpath(f"{case['id']}.txt").write_text(
                    self._passing_output_for(case),
                    encoding="utf-8",
                )
            output_path.joinpath("dense_ai_rewrite.txt").write_text(
                "Great question! Here is a rewrite with a Gartner claim.",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(output_path)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("forbidden fragment present", result.stderr)

    def _passing_output_for(self, case):
        required_fragments = case["constraints"].get("must_include", [])
        base = ". ".join(required_fragments)
        if case["mode"] == "audit":
            return (
                "Teams collaborate better when they stay aligned.\n\n"
                "Notes: removed inflated phrasing and fake naming.\n\n"
                "Score: 72/80."
            )
        if case["mode"] == "translate":
            return "Le produit inclut les commentaires hors ligne et une recherche plus rapide."
        if case["mode"] == "summary":
            return f"- {base}."
        if case["mode"] == "spellcheck":
            return "The release includes offline comments and faster issue search."
        return f"{base}. The source stays general where it does not name evidence."


if __name__ == "__main__":
    unittest.main()
