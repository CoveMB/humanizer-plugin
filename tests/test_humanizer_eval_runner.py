import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers.skill_artifacts import REPO_ROOT


RUNNER_PATH = REPO_ROOT / "scripts" / "run_humanizer_evals.py"
EVAL_CASES_PATH = REPO_ROOT / "evals" / "humanizer_eval_cases.json"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_humanizer_evals", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HumanizerEvalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = load_runner_module()

    def test_eval_cases_cover_trigger_modes_and_output_contracts(self):
        cases = self.runner.load_eval_cases(EVAL_CASES_PATH)
        categories = {case["category"] for case in cases}
        contract_ids = {
            case["output_contract_case_id"]
            for case in cases
            if case.get("output_contract_case_id")
        }
        forced_read_case_ids = {
            case["id"] for case in cases if case.get("force_skill_file_read")
        }
        positive_case_ids = {case["id"] for case in cases if case["should_trigger"]}

        self.assertGreaterEqual(len(cases), 10)
        self.assertTrue({"explicit", "implicit", "contextual", "negative"}.issubset(categories))
        self.assertTrue(
            {
                "dense_ai_rewrite",
                "missing_source_handling",
                "voice_calibration",
                "audit_mode",
                "dense_banned_list_scrub",
                "contextual_release_notes",
                "contextual_docs_cleanup",
            }.issubset(contract_ids)
        )
        self.assertTrue(positive_case_ids)
        self.assertTrue(forced_read_case_ids)
        self.assertTrue(forced_read_case_ids.issubset(positive_case_ids))

    def test_all_cases_reject_humanizer_plugin_loader_warnings(self):
        cases = self.runner.load_eval_cases(EVAL_CASES_PATH)

        for case in cases:
            with self.subTest(case=case["id"]):
                forbidden_stderr_terms = case.get("forbidden_stderr_terms", [])
                self.assertIn(
                    'plugin="humanizer-plugin" error=invalid marketplace',
                    forbidden_stderr_terms,
                )
                self.assertIn(
                    'plugin="humanizer@humanizer-local"',
                    forbidden_stderr_terms,
                )

    def test_load_eval_cases_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cases_path = Path(temporary_directory) / "cases.json"
            cases_path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "duplicate",
                                "category": "explicit",
                                "should_trigger": True,
                                "prompt": "Use Humanizer.",
                                "source": "Here is a draft.",
                                "expected_trace_terms": ["skills/humanizer/SKILL.md"],
                            },
                            {
                                "id": "duplicate",
                                "category": "implicit",
                                "should_trigger": True,
                                "prompt": "Make this sound natural.",
                                "source": "Here is another draft.",
                                "expected_trace_terms": ["skills/humanizer/SKILL.md"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.runner.load_eval_cases(cases_path)

    def test_load_eval_cases_rejects_unknown_output_contract_case_id(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cases_path = Path(temporary_directory) / "cases.json"
            cases_path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "unknown_contract",
                                "category": "explicit",
                                "should_trigger": True,
                                "prompt": "Use Humanizer.",
                                "source": "Here is a draft.",
                                "output_contract_case_id": "missing_contract",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown output contract"):
                self.runner.load_eval_cases(cases_path)

    def test_build_codex_prompt_includes_source_and_output_rules(self):
        case = {
            "id": "sample",
            "category": "explicit",
            "should_trigger": True,
            "force_skill_file_read": True,
            "prompt": "Use $humanizer to rewrite this.",
            "source": "Great question! This is a pivotal moment.",
            "output_contract_case_id": "dense_ai_rewrite",
        }

        prompt = self.runner.build_codex_prompt(case)

        self.assertIn("Use $humanizer to rewrite this.", prompt)
        self.assertIn("Read `skills/humanizer/SKILL.md` before answering.", prompt)
        self.assertIn("Great question! This is a pivotal moment.", prompt)
        self.assertIn("Return only the final Humanizer output", prompt)
        self.assertIn("Do not edit repository files", prompt)

    def test_build_codex_prompt_supports_unforced_activation_probes(self):
        case = {
            "id": "activation",
            "category": "contextual",
            "should_trigger": True,
            "force_skill_file_read": False,
            "prompt": "This sounds padded. Tighten it.",
            "source": "This release represents a pivotal step.",
        }

        prompt = self.runner.build_codex_prompt(case)

        self.assertNotIn("Read `skills/humanizer/SKILL.md` before answering.", prompt)
        self.assertIn("Return only the final Humanizer output", prompt)

    def test_build_codex_prompt_does_not_force_skill_for_no_trigger_cases(self):
        case = {
            "id": "negative",
            "category": "negative",
            "should_trigger": False,
            "prompt": "Translate this.",
            "source": "The release includes offline comments.",
        }

        prompt = self.runner.build_codex_prompt(case)

        self.assertNotIn("skills/humanizer/SKILL.md", prompt)

    def test_parse_jsonl_events_reports_invalid_lines(self):
        jsonl_text = '{"type":"session.started"}\nnot json\n'

        with self.assertRaisesRegex(ValueError, "line 2"):
            self.runner.parse_jsonl_events(jsonl_text)

    def test_parse_jsonl_events_rejects_empty_trace(self):
        with self.assertRaisesRegex(ValueError, "no JSONL events"):
            self.runner.parse_jsonl_events("\n\n")

    def test_check_trace_expectations_uses_recursive_event_search(self):
        events = [
            {"type": "item.started", "item": {"path": "skills/humanizer/SKILL.md"}},
            {"type": "turn.completed", "usage": {"input_tokens": 1234}},
        ]
        case = {
            "id": "trace",
            "expected_trace_terms": ["skills/humanizer/SKILL.md"],
            "forbidden_trace_terms": ["dangerously-bypass-approvals"],
        }

        self.runner.check_trace_expectations(case, events)

    def test_check_trace_expectations_fails_for_missing_required_term(self):
        with self.assertRaisesRegex(AssertionError, "missing trace term"):
            self.runner.check_trace_expectations(
                {"id": "trace", "expected_trace_terms": ["skills/humanizer/SKILL.md"]},
                [{"type": "turn.completed"}],
            )

    def test_check_stderr_expectations_fails_for_forbidden_loader_warning(self):
        case = {
            "id": "stderr",
            "forbidden_stderr_terms": [
                "path={repo_root}/.agents/plugins/marketplace.json plugin=\"humanizer-plugin\" error=invalid marketplace"
            ],
        }

        with self.assertRaisesRegex(AssertionError, "forbidden stderr term"):
            self.runner.check_stderr_expectations(
                case,
                f'WARN path={REPO_ROOT}/.agents/plugins/marketplace.json '
                'plugin="humanizer-plugin" error=invalid marketplace',
            )

    def test_check_stderr_expectations_fails_for_user_marketplace_warning(self):
        case = {
            "id": "stderr",
            "forbidden_stderr_terms": [
                'plugin="humanizer-plugin" error=invalid marketplace'
            ],
        }

        with self.assertRaisesRegex(AssertionError, "forbidden stderr term"):
            self.runner.check_stderr_expectations(
                case,
                'WARN path=/Users/example/.agents/plugins/marketplace.json '
                'plugin="humanizer-plugin" error=invalid marketplace file',
            )

    def test_build_codex_command_uses_read_only_json_trace_and_output_file(self):
        command = self.runner.build_codex_command(
            codex_bin="codex",
            repo_root=REPO_ROOT,
            output_path=Path("/tmp/final.txt"),
            prompt="Humanize this.",
            model="gpt-5.4",
        )

        self.assertEqual(command[:2], ["codex", "exec"])
        self.assertIn("--json", command)
        self.assertIn("--sandbox", command)
        self.assertIn("read-only", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("/tmp/final.txt", command)
        self.assertIn("--model", command)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)

    def test_build_codex_command_isolates_current_repo_plugin(self):
        command = self.runner.build_codex_command(
            codex_bin="codex",
            repo_root=REPO_ROOT,
            output_path=Path("/tmp/final.txt"),
            prompt="Humanize this.",
            model=None,
        )

        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("marketplaces.humanizer-plugin-local.source_type=\"local\"", command)
        self.assertIn(
            f"marketplaces.humanizer-plugin-local.source=\"{REPO_ROOT}\"",
            command,
        )
        self.assertIn(
            'plugins."humanizer-plugin@humanizer-plugin-local".enabled=true',
            command,
        )

    def test_dry_run_lists_cases_without_invoking_codex(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER_PATH),
                    "--cases",
                    str(EVAL_CASES_PATH),
                    "--artifacts-dir",
                    temporary_directory,
                    "--dry-run",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("would run", result.stdout)
        self.assertIn("explicit_dense_rewrite", result.stdout)

    def test_parser_pins_default_eval_model(self):
        args = self.runner.build_parser().parse_args([])

        self.assertEqual(args.model, "gpt-5.5")

    def test_parser_sets_default_case_timeout(self):
        args = self.runner.build_parser().parse_args([])

        self.assertEqual(args.timeout_seconds, 300)

    def test_parser_rejects_non_positive_timeout(self):
        with mock.patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
            self.runner.build_parser().parse_args(["--timeout-seconds", "0"])

    def test_run_eval_case_reports_timeout(self):
        case = {
            "id": "timeout_case",
            "category": "explicit",
            "should_trigger": True,
            "prompt": "Use $humanizer.",
            "source": "Here is a draft.",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            artifact_dirs = self.runner.ensure_artifact_dirs(Path(temporary_directory))
            timeout_error = subprocess.TimeoutExpired(
                cmd=["codex"],
                timeout=1,
                output="partial trace",
                stderr="partial stderr",
            )

            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=timeout_error,
            ):
                summary = self.runner.run_eval_case(
                    case,
                    artifact_dirs,
                    codex_bin="codex",
                    output_contract_cases={},
                    model="gpt-5.5",
                    timeout_seconds=1,
                )

            self.assertFalse(summary["passed"])
            self.assertIn("timed out after 1 seconds", summary["error"])
            self.assertEqual(Path(summary["trace_path"]).read_text(), "partial trace")
            self.assertEqual(Path(summary["stderr_path"]).read_text(), "partial stderr")

    def test_run_eval_case_reports_startup_failure(self):
        case = {
            "id": "startup_failure",
            "category": "explicit",
            "should_trigger": True,
            "prompt": "Use $humanizer.",
            "source": "Here is a draft.",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            artifact_dirs = self.runner.ensure_artifact_dirs(Path(temporary_directory))

            with mock.patch.object(
                self.runner.subprocess,
                "run",
                side_effect=FileNotFoundError("missing codex"),
            ):
                summary = self.runner.run_eval_case(
                    case,
                    artifact_dirs,
                    codex_bin="missing-codex",
                    output_contract_cases={},
                    model="gpt-5.5",
                )

            self.assertFalse(summary["passed"])
            self.assertIn("failed to start codex", summary["error"])
            self.assertIn("missing codex", summary["error"])

    def test_run_eval_case_does_not_reuse_stale_output_file(self):
        case = {
            "id": "stale_output",
            "category": "explicit",
            "should_trigger": True,
            "prompt": "Use $humanizer.",
            "source": "Here is a draft.",
            "output_contract_case_id": "dense_ai_rewrite",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            artifact_dirs = self.runner.ensure_artifact_dirs(Path(temporary_directory))
            output_path = artifact_dirs["outputs"] / "stale_output.txt"
            output_path.write_text(
                "AI coding assistants can help with docs and tests.",
                encoding="utf-8",
            )
            result = subprocess.CompletedProcess(
                args=["codex"],
                returncode=0,
                stdout='{"type":"turn.completed"}\n',
                stderr="",
            )

            with mock.patch.object(self.runner.subprocess, "run", return_value=result):
                summary = self.runner.run_eval_case(
                    case,
                    artifact_dirs,
                    codex_bin="codex",
                    output_contract_cases=self.runner.load_output_contract_cases(),
                    model="gpt-5.5",
                )

            self.assertFalse(summary["passed"])
            self.assertIn("missing final output file", summary["error"])


if __name__ == "__main__":
    unittest.main()
