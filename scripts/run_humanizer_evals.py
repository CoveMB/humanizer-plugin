#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.helpers.output_contracts import validate_case_output  # noqa: E402
from tests.helpers.skill_artifacts import load_fixture_cases  # noqa: E402


DEFAULT_CASES_PATH = REPO_ROOT / "evals" / "humanizer_eval_cases.json"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "evals" / "artifacts" / "latest"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_TIMEOUT_SECONDS = 300
LOCAL_MARKETPLACE_NAME = "humanizer-plugin-local"
LOCAL_PLUGIN_NAME = "humanizer-plugin"
VALID_CATEGORIES = {"explicit", "implicit", "contextual", "negative"}
REQUIRED_CASE_KEYS = {"id", "category", "should_trigger", "prompt", "source"}
DEFAULT_FORBIDDEN_STDERR_TERMS = (
    'plugin="humanizer-plugin" error=invalid marketplace',
    'plugin="humanizer@humanizer-local"',
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def positive_integer(value):
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return number


def require_string(case, key):
    value = case.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{case.get('id', '<unknown>')}: {key} must be a non-empty string")
    return value


def require_string_list(case, key):
    value = case.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{case['id']}: {key} must be a list of strings")
    return value


def require_optional_boolean(case, key):
    value = case.get(key, False)
    if not isinstance(value, bool):
        raise ValueError(f"{case['id']}: {key} must be a boolean")
    return value


def validate_eval_case(case):
    missing_keys = REQUIRED_CASE_KEYS - set(case)
    if missing_keys:
        raise ValueError(f"{case.get('id', '<unknown>')}: missing keys {sorted(missing_keys)}")

    require_string(case, "id")
    require_string(case, "prompt")
    require_string(case, "source")

    if case["category"] not in VALID_CATEGORIES:
        raise ValueError(f"{case['id']}: unsupported category {case['category']!r}")

    if not isinstance(case["should_trigger"], bool):
        raise ValueError(f"{case['id']}: should_trigger must be a boolean")

    require_optional_boolean(case, "force_skill_file_read")
    require_string_list(case, "expected_trace_terms")
    require_string_list(case, "forbidden_trace_terms")
    require_string_list(case, "expected_stderr_terms")
    require_string_list(case, "forbidden_stderr_terms")

    output_contract_case_id = case.get("output_contract_case_id")
    if output_contract_case_id is not None and not isinstance(output_contract_case_id, str):
        raise ValueError(f"{case['id']}: output_contract_case_id must be a string")

    return case


def unique_strings(strings):
    return list(dict.fromkeys(strings))


def with_default_forbidden_stderr_terms(case):
    return {
        **case,
        "forbidden_stderr_terms": unique_strings(
            [
                *DEFAULT_FORBIDDEN_STDERR_TERMS,
                *case.get("forbidden_stderr_terms", []),
            ]
        ),
    }


def validate_output_contract_references(cases, output_contract_cases):
    unknown_contract_ids = sorted(
        {
            case["output_contract_case_id"]
            for case in cases
            if case.get("output_contract_case_id")
            and case["output_contract_case_id"] not in output_contract_cases
        }
    )
    if unknown_contract_ids:
        raise ValueError(
            "unknown output contract case id(s): " + ", ".join(unknown_contract_ids)
        )


def load_eval_cases(path=DEFAULT_CASES_PATH, output_contract_cases=None):
    data = read_json(Path(path))
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("eval case file must contain a cases list")

    seen_case_ids = set()
    validated_cases = []
    for case in cases:
        validate_eval_case(case)
        case = with_default_forbidden_stderr_terms(case)
        case_id = case["id"]
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate eval case id: {case_id}")
        seen_case_ids.add(case_id)
        validated_cases.append(case)

    contracts = (
        load_output_contract_cases()
        if output_contract_cases is None
        else output_contract_cases
    )
    validate_output_contract_references(validated_cases, contracts)
    return validated_cases


def load_output_contract_cases():
    return {case["id"]: case for case in load_fixture_cases()}


def build_codex_prompt(case):
    prompt_lines = []
    if case.get("force_skill_file_read", False):
        prompt_lines.extend(
            [
                "Read `skills/humanizer/SKILL.md` before answering.",
                "Reading the skill file is essential for this eval.",
                "",
            ]
        )

    prompt_lines.extend(
        [
            case["prompt"].strip(),
            "",
            "<source>",
            case["source"].strip(),
            "</source>",
            "",
            "Do not edit repository files.",
            "Do not run shell commands unless they are essential to answer this prompt.",
        ]
    )

    if case["should_trigger"]:
        prompt_lines.append("Return only the final Humanizer output, with no eval commentary.")
    else:
        prompt_lines.append("Return only the final answer, with no eval commentary.")

    return "\n".join(prompt_lines)


def parse_jsonl_events(jsonl_text):
    events = []
    for line_number, line in enumerate(jsonl_text.splitlines(), start=1):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        try:
            events.append(json.loads(stripped_line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL on line {line_number}: {error}") from error
    if not events:
        raise ValueError("no JSONL events found in Codex trace")
    return events


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, nested_value in value.items():
            yield str(key)
            yield from iter_strings(nested_value)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def trace_contains_term(events, term):
    lowered_term = term.lower()
    return any(lowered_term in text.lower() for event in events for text in iter_strings(event))


def local_marketplace_config_key():
    return f"marketplaces.{LOCAL_MARKETPLACE_NAME}"


def check_trace_expectations(case, events):
    for expected_term in case.get("expected_trace_terms", []):
        if not trace_contains_term(events, expected_term):
            raise AssertionError(f"{case['id']}: missing trace term {expected_term!r}")

    for forbidden_term in case.get("forbidden_trace_terms", []):
        if trace_contains_term(events, forbidden_term):
            raise AssertionError(f"{case['id']}: forbidden trace term present {forbidden_term!r}")


def check_stderr_expectations(case, stderr_text):
    lowered_stderr = stderr_text.lower()

    for expected_term in case.get("expected_stderr_terms", []):
        expanded_expected_term = expected_term.format(repo_root=REPO_ROOT)
        if expanded_expected_term.lower() not in lowered_stderr:
            raise AssertionError(f"{case['id']}: missing stderr term {expected_term!r}")

    for forbidden_term in case.get("forbidden_stderr_terms", []):
        expanded_forbidden_term = forbidden_term.format(repo_root=REPO_ROOT)
        if expanded_forbidden_term.lower() in lowered_stderr:
            raise AssertionError(f"{case['id']}: forbidden stderr term present {forbidden_term!r}")


def build_codex_command(codex_bin, repo_root, output_path, prompt, model=None):
    command = [
        codex_bin,
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--json",
        "--sandbox",
        "read-only",
        "--cd",
        str(repo_root),
        "--output-last-message",
        str(output_path),
        "-c",
        f'{local_marketplace_config_key()}.source_type="local"',
        "-c",
        f'{local_marketplace_config_key()}.source="{repo_root}"',
        "-c",
        f'plugins."{LOCAL_PLUGIN_NAME}@{LOCAL_MARKETPLACE_NAME}".enabled=true',
    ]

    if model:
        command.extend(["--model", model])

    command.append(prompt)
    return command


def process_output_text(output):
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


def ensure_artifact_dirs(artifacts_dir):
    traces_dir = artifacts_dir / "traces"
    outputs_dir = artifacts_dir / "outputs"
    stderr_dir = artifacts_dir / "stderr"
    prompts_dir = artifacts_dir / "prompts"
    for directory in (traces_dir, outputs_dir, stderr_dir, prompts_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "traces": traces_dir,
        "outputs": outputs_dir,
        "stderr": stderr_dir,
        "prompts": prompts_dir,
    }


def validate_case_output_contract(eval_case, output_text, output_contract_cases):
    contract_case_id = eval_case.get("output_contract_case_id")
    if not contract_case_id:
        return

    if contract_case_id not in output_contract_cases:
        raise AssertionError(
            f"{eval_case['id']}: unknown output contract case {contract_case_id!r}"
        )

    validate_case_output(output_contract_cases[contract_case_id], output_text)


def remove_file_if_exists(path):
    try:
        path.unlink()
    except FileNotFoundError:
        return


def read_final_output(case, output_path):
    if not output_path.exists():
        raise AssertionError(f"{case['id']}: missing final output file {output_path}")
    return output_path.read_text(encoding="utf-8")


def run_eval_case(
    case,
    artifact_dirs,
    codex_bin,
    output_contract_cases,
    model=None,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
):
    prompt = build_codex_prompt(case)
    output_path = artifact_dirs["outputs"] / f"{case['id']}.txt"
    trace_path = artifact_dirs["traces"] / f"{case['id']}.jsonl"
    stderr_path = artifact_dirs["stderr"] / f"{case['id']}.stderr"
    prompt_path = artifact_dirs["prompts"] / f"{case['id']}.txt"

    summary = {
        "id": case["id"],
        "category": case["category"],
        "returncode": None,
        "trace_path": str(trace_path),
        "output_path": str(output_path),
        "stderr_path": str(stderr_path),
        "prompt_path": str(prompt_path),
        "passed": False,
        "error": None,
    }

    prompt_path.write_text(prompt, encoding="utf-8")
    remove_file_if_exists(output_path)
    command = build_codex_command(codex_bin, REPO_ROOT, output_path, prompt, model=model)
    try:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        trace_path.write_text(
            process_output_text(getattr(error, "stdout", None) or error.output),
            encoding="utf-8",
        )
        stderr_path.write_text(process_output_text(error.stderr), encoding="utf-8")
        summary["error"] = f"{case['id']}: codex timed out after {timeout_seconds} seconds"
        return summary
    except OSError as error:
        trace_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(error), encoding="utf-8")
        summary["error"] = f"{case['id']}: failed to start codex: {error}"
        return summary

    summary["returncode"] = result.returncode
    trace_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    try:
        if result.returncode != 0:
            raise AssertionError(f"{case['id']}: codex exited with {result.returncode}")

        events = parse_jsonl_events(result.stdout)
        check_trace_expectations(case, events)
        check_stderr_expectations(case, result.stderr)

        output_text = read_final_output(case, output_path)
        validate_case_output_contract(case, output_text, output_contract_cases)
    except (AssertionError, OSError, ValueError) as error:
        summary["error"] = str(error)
        return summary

    summary["passed"] = True
    return summary


def select_cases(cases, filters):
    if not filters:
        return cases

    selected_ids = set(filters)
    selected_cases = [case for case in cases if case["id"] in selected_ids]
    missing_ids = selected_ids - {case["id"] for case in selected_cases}
    if missing_ids:
        raise ValueError(f"unknown eval case id(s): {', '.join(sorted(missing_ids))}")
    return selected_cases


def write_summary(artifacts_dir, summaries):
    summary_path = artifacts_dir / "summary.json"
    summary_path.write_text(json.dumps({"results": summaries}, indent=2), encoding="utf-8")
    return summary_path


def run_eval_suite(
    cases,
    artifacts_dir,
    codex_bin,
    model=None,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
):
    artifact_dirs = ensure_artifact_dirs(artifacts_dir)
    output_contract_cases = load_output_contract_cases()
    summaries = [
        run_eval_case(
            case,
            artifact_dirs,
            codex_bin=codex_bin,
            output_contract_cases=output_contract_cases,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        for case in cases
    ]
    summary_path = write_summary(artifacts_dir, summaries)
    return summaries, summary_path


def print_dry_run(cases):
    print(f"would run {len(cases)} Humanizer eval case(s)")
    for case in cases:
        trigger_label = "trigger" if case["should_trigger"] else "no-trigger"
        print(f"- {case['id']} [{case['category']}, {trigger_label}]")


def print_summary(summaries, summary_path):
    passed_count = sum(1 for summary in summaries if summary["passed"])
    print(f"passed {passed_count}/{len(summaries)} Humanizer eval case(s)")
    print(f"summary: {summary_path}")

    for summary in summaries:
        if not summary["passed"]:
            print(f"- {summary['id']}: {summary['error']}", file=sys.stderr)


def build_parser():
    parser = argparse.ArgumentParser(description="Run live Codex evals for the Humanizer skill.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--timeout-seconds",
        type=positive_integer,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--filter", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    try:
        cases = select_cases(load_eval_cases(args.cases), args.filter)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.dry_run:
        print_dry_run(cases)
        return 0

    summaries, summary_path = run_eval_suite(
        cases,
        artifacts_dir=args.artifacts_dir,
        codex_bin=args.codex_bin,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
    )
    print_summary(summaries, summary_path)
    return 0 if all(summary["passed"] for summary in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
