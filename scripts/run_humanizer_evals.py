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
TRACE_METRIC_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
RUBRIC_MAX_DIMENSION_SCORE = 10


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


def is_strict_integer(value):
    return type(value) is int


def is_positive_integer(value):
    return is_strict_integer(value) and value > 0


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
    require_optional_boolean(case, "force_reference_file_read")
    require_string_list(case, "expected_trace_terms")
    require_string_list(case, "forbidden_trace_terms")
    require_string_list(case, "expected_stderr_terms")
    require_string_list(case, "forbidden_stderr_terms")

    output_contract_case_id = case.get("output_contract_case_id")
    if output_contract_case_id is not None and not isinstance(output_contract_case_id, str):
        raise ValueError(f"{case['id']}: output_contract_case_id must be a string")

    rubric_id = case.get("rubric_id")
    if rubric_id is not None and not isinstance(rubric_id, str):
        raise ValueError(f"{case['id']}: rubric_id must be a string")

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


def normalize_contract_source(source):
    return " ".join(str(source).strip().split())


def validate_output_contract_sources(cases, output_contract_cases):
    mismatches = []
    for case in cases:
        output_contract_case_id = case.get("output_contract_case_id")
        if not output_contract_case_id:
            continue

        contract_case = output_contract_cases[output_contract_case_id]
        if normalize_contract_source(case["source"]) != normalize_contract_source(
            contract_case.get("source", "")
        ):
            mismatches.append(f"{case['id']} -> {output_contract_case_id}")

    if mismatches:
        raise ValueError("output contract source mismatch: " + ", ".join(mismatches))


def require_rubric_score_threshold(rubric_id, rubric, key):
    value = rubric.get(key)
    if not is_positive_integer(value):
        raise ValueError(f"{rubric_id}: rubric {key} must be a positive integer")
    return value


def validate_rubric_definition(rubric_id, rubric):
    if not isinstance(rubric, dict):
        raise ValueError(f"{rubric_id}: rubric must be an object")

    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError(f"{rubric_id}: rubric dimensions must be a non-empty list")

    dimension_names = []
    normalized_dimensions = []
    for index, dimension in enumerate(dimensions):
        if not isinstance(dimension, dict):
            raise ValueError(f"{rubric_id}: rubric dimension {index} must be an object")

        name = dimension.get("name")
        question = dimension.get("question")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{rubric_id}: rubric dimension {index} missing name")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"{rubric_id}: rubric dimension {name} missing question")

        dimension_names.append(name)
        normalized_dimensions.append({"name": name, "question": question})

    if len(dimension_names) != len(set(dimension_names)):
        raise ValueError(f"{rubric_id}: rubric dimension names must be unique")

    minimum_total_score = require_rubric_score_threshold(
        rubric_id,
        rubric,
        "minimum_total_score",
    )
    minimum_dimension_score = require_rubric_score_threshold(
        rubric_id,
        rubric,
        "minimum_dimension_score",
    )
    if minimum_dimension_score > RUBRIC_MAX_DIMENSION_SCORE:
        raise ValueError(f"{rubric_id}: rubric minimum_dimension_score is too high")

    maximum_total_score = len(normalized_dimensions) * RUBRIC_MAX_DIMENSION_SCORE
    if minimum_total_score > maximum_total_score:
        raise ValueError(f"{rubric_id}: rubric minimum_total_score is too high")

    return {
        "minimum_total_score": minimum_total_score,
        "minimum_dimension_score": minimum_dimension_score,
        "dimensions": normalized_dimensions,
    }


def validate_rubrics(rubrics):
    if rubrics is None:
        return {}
    if not isinstance(rubrics, dict):
        raise ValueError("rubrics must be an object")
    return {
        rubric_id: validate_rubric_definition(rubric_id, rubric)
        for rubric_id, rubric in rubrics.items()
    }


def attach_case_rubric(case, rubrics):
    rubric_id = case.get("rubric_id")
    if not rubric_id:
        return case
    if rubric_id not in rubrics:
        raise ValueError(f"{case['id']}: unknown rubric id {rubric_id!r}")
    return {**case, "rubric": rubrics[rubric_id]}


def load_eval_cases(path=DEFAULT_CASES_PATH, output_contract_cases=None):
    data = read_json(Path(path))
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("eval case file must contain a cases list")
    rubrics = validate_rubrics(data.get("rubrics", {}))

    seen_case_ids = set()
    validated_cases = []
    for case in cases:
        validate_eval_case(case)
        case = with_default_forbidden_stderr_terms(case)
        case = attach_case_rubric(case, rubrics)
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
    validate_output_contract_sources(validated_cases, contracts)
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
    if case.get("force_reference_file_read", False):
        prompt_lines.extend(
            [
                "Read `skills/humanizer/references/banned-list.md` before answering.",
                "Reading the banned-list reference is essential for this dense-draft eval.",
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


def build_rubric_prompt(case, output_text):
    rubric = case["rubric"]
    expected_schema = {
        "case_id": case["id"],
        "scores": {
            dimension["name"]: {
                "score": f"integer 1-{RUBRIC_MAX_DIMENSION_SCORE}",
                "rationale": "short reason",
            }
            for dimension in rubric["dimensions"]
        },
        "total_score": "sum of dimension scores",
        "passed": "boolean",
        "issues": ["short issue strings, empty if none"],
    }
    return "\n".join(
        [
            "Grade this Humanizer eval output against the rubric.",
            "Use only the source and output below. Do not infer outside facts.",
            f"Minimum total score: {rubric['minimum_total_score']}",
            f"Minimum dimension score: {rubric['minimum_dimension_score']}",
            "",
            "<rubric>",
            json.dumps(rubric["dimensions"], indent=2),
            "</rubric>",
            "",
            "<source>",
            case["source"].strip(),
            "</source>",
            "",
            "<output>",
            output_text.strip(),
            "</output>",
            "",
            "Return only JSON matching this schema:",
            json.dumps(expected_schema, indent=2),
        ]
    )


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


def iter_trace_observation_strings(event):
    item = event.get("item") if isinstance(event, dict) else None
    if not isinstance(item, dict):
        return

    path = item.get("path")
    if isinstance(path, str):
        yield path

    if item.get("type") == "command_execution":
        for key in ("command", "aggregated_output"):
            value = item.get(key)
            if isinstance(value, str):
                yield value


def trace_contains_term(events, term):
    lowered_term = term.lower()
    return any(
        lowered_term in text.lower()
        for event in events
        for text in iter_trace_observation_strings(event)
    )


def empty_trace_metrics():
    return {
        "command_count": 0,
        **{metric_key: 0 for metric_key in TRACE_METRIC_KEYS},
    }


def collect_trace_metrics(events):
    metrics = empty_trace_metrics()
    for event in events:
        item = event.get("item") if isinstance(event, dict) else None
        if (
            isinstance(event, dict)
            and event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "command_execution"
        ):
            metrics["command_count"] += 1

        usage = event.get("usage") if isinstance(event, dict) else None
        if isinstance(usage, dict):
            for metric_key in TRACE_METRIC_KEYS:
                value = usage.get(metric_key, 0)
                if is_strict_integer(value):
                    metrics[metric_key] += value
    return metrics


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


def build_codex_command(
    codex_bin,
    repo_root,
    output_path,
    prompt,
    model=None,
    enable_local_plugin=True,
):
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
    ]

    if enable_local_plugin:
        command.extend(
            [
                "-c",
                f'{local_marketplace_config_key()}.source_type="local"',
                "-c",
                f'{local_marketplace_config_key()}.source="{repo_root}"',
                "-c",
                f'plugins."{LOCAL_PLUGIN_NAME}@{LOCAL_MARKETPLACE_NAME}".enabled=true',
            ]
        )

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


def run_codex_process(command, trace_path, stderr_path, timeout_seconds, case_id, label):
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
        raise AssertionError(
            f"{case_id}: {label} timed out after {timeout_seconds} seconds"
        ) from error
    except OSError as error:
        trace_path.write_text("", encoding="utf-8")
        stderr_path.write_text(str(error), encoding="utf-8")
        raise AssertionError(f"{case_id}: failed to start {label}: {error}") from error

    trace_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    return result


def ensure_artifact_dirs(artifacts_dir):
    traces_dir = artifacts_dir / "traces"
    outputs_dir = artifacts_dir / "outputs"
    stderr_dir = artifacts_dir / "stderr"
    prompts_dir = artifacts_dir / "prompts"
    rubric_traces_dir = artifacts_dir / "rubric-traces"
    rubric_outputs_dir = artifacts_dir / "rubric-outputs"
    rubric_stderr_dir = artifacts_dir / "rubric-stderr"
    rubric_prompts_dir = artifacts_dir / "rubric-prompts"
    for directory in (
        traces_dir,
        outputs_dir,
        stderr_dir,
        prompts_dir,
        rubric_traces_dir,
        rubric_outputs_dir,
        rubric_stderr_dir,
        rubric_prompts_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "traces": traces_dir,
        "outputs": outputs_dir,
        "stderr": stderr_dir,
        "prompts": prompts_dir,
        "rubric_traces": rubric_traces_dir,
        "rubric_outputs": rubric_outputs_dir,
        "rubric_stderr": rubric_stderr_dir,
        "rubric_prompts": rubric_prompts_dir,
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


def require_rubric_grade_score(case_id, dimension_name, score_entry):
    if not isinstance(score_entry, dict):
        raise AssertionError(f"{case_id}: rubric score {dimension_name} must be an object")

    score = score_entry.get("score")
    if (
        not is_strict_integer(score)
        or score < 1
        or score > RUBRIC_MAX_DIMENSION_SCORE
    ):
        raise AssertionError(f"{case_id}: rubric score {dimension_name} is invalid")

    rationale = score_entry.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise AssertionError(f"{case_id}: rubric score {dimension_name} missing rationale")
    return score


def validate_rubric_grade(case, grade):
    case_id = case["id"]
    rubric = case["rubric"]
    if not isinstance(grade, dict):
        raise AssertionError(f"{case_id}: rubric grade must be an object")
    if grade.get("case_id") != case_id:
        raise AssertionError(f"{case_id}: rubric grade has wrong case_id")

    scores = grade.get("scores")
    if not isinstance(scores, dict):
        raise AssertionError(f"{case_id}: rubric grade scores must be an object")

    expected_names = [dimension["name"] for dimension in rubric["dimensions"]]
    if set(scores) != set(expected_names):
        raise AssertionError(f"{case_id}: rubric grade dimensions do not match rubric")

    dimension_scores = {
        name: require_rubric_grade_score(case_id, name, scores[name])
        for name in expected_names
    }
    total_score = sum(dimension_scores.values())
    if grade.get("total_score") != total_score:
        raise AssertionError(f"{case_id}: rubric total_score does not match scores")

    violations = [
        f"{case_id}: {name} score {score} below minimum {rubric['minimum_dimension_score']}"
        for name, score in dimension_scores.items()
        if score < rubric["minimum_dimension_score"]
    ]
    if total_score < rubric["minimum_total_score"]:
        violations.append(
            f"{case_id}: total_score {total_score} below minimum {rubric['minimum_total_score']}"
        )

    computed_passed = not violations
    if grade.get("passed") is not computed_passed:
        violations.append(f"{case_id}: rubric passed flag does not match scores")

    issues = grade.get("issues")
    if not isinstance(issues, list) or not all(isinstance(issue, str) for issue in issues):
        violations.append(f"{case_id}: rubric issues must be a list of strings")

    if violations:
        raise AssertionError("\n".join(violations))
    return {
        "rubric_passed": True,
        "rubric_total_score": total_score,
        "rubric_dimension_scores": dimension_scores,
    }


def read_rubric_grade(case, rubric_output_path):
    if not rubric_output_path.exists():
        raise AssertionError(f"{case['id']}: missing rubric output file {rubric_output_path}")
    try:
        return json.loads(rubric_output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise AssertionError(f"{case['id']}: invalid rubric JSON: {error}") from error


def run_rubric_grade(
    case,
    output_text,
    artifact_dirs,
    codex_bin,
    model=None,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
):
    rubric_prompt_path = artifact_dirs["rubric_prompts"] / f"{case['id']}.txt"
    rubric_output_path = artifact_dirs["rubric_outputs"] / f"{case['id']}.json"
    rubric_trace_path = artifact_dirs["rubric_traces"] / f"{case['id']}.jsonl"
    rubric_stderr_path = artifact_dirs["rubric_stderr"] / f"{case['id']}.stderr"
    prompt = build_rubric_prompt(case, output_text)

    rubric_prompt_path.write_text(prompt, encoding="utf-8")
    remove_file_if_exists(rubric_output_path)
    command = build_codex_command(
        codex_bin,
        REPO_ROOT,
        rubric_output_path,
        prompt,
        model=model,
        enable_local_plugin=False,
    )
    result = run_codex_process(
        command,
        rubric_trace_path,
        rubric_stderr_path,
        timeout_seconds,
        case["id"],
        "rubric grader",
    )
    if result.returncode != 0:
        raise AssertionError(f"{case['id']}: rubric grader exited with {result.returncode}")

    grade = read_rubric_grade(case, rubric_output_path)
    return {
        "rubric_prompt_path": str(rubric_prompt_path),
        "rubric_output_path": str(rubric_output_path),
        "rubric_trace_path": str(rubric_trace_path),
        "rubric_stderr_path": str(rubric_stderr_path),
        **validate_rubric_grade(case, grade),
    }


def run_eval_case(
    case,
    artifact_dirs,
    codex_bin,
    output_contract_cases,
    model=None,
    timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    grade_rubric=False,
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
        "rubric_passed": None,
        "rubric_error": None,
        "rubric_total_score": None,
        **empty_trace_metrics(),
    }

    prompt_path.write_text(prompt, encoding="utf-8")
    remove_file_if_exists(output_path)
    command = build_codex_command(codex_bin, REPO_ROOT, output_path, prompt, model=model)
    try:
        result = run_codex_process(
            command,
            trace_path,
            stderr_path,
            timeout_seconds,
            case["id"],
            "codex",
        )
    except AssertionError as error:
        summary["error"] = str(error)
        return summary

    summary["returncode"] = result.returncode

    try:
        if result.returncode != 0:
            raise AssertionError(f"{case['id']}: codex exited with {result.returncode}")

        events = parse_jsonl_events(result.stdout)
        metrics = collect_trace_metrics(events)
        summary.update(metrics)
        check_trace_expectations(case, events)
        check_stderr_expectations(case, result.stderr)

        output_text = read_final_output(case, output_path)
        validate_case_output_contract(case, output_text, output_contract_cases)
        if grade_rubric and case.get("rubric"):
            try:
                summary.update(
                    run_rubric_grade(
                        case,
                        output_text,
                        artifact_dirs,
                        codex_bin=codex_bin,
                        model=model,
                        timeout_seconds=timeout_seconds,
                    )
                )
            except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired) as error:
                summary["rubric_error"] = str(error)
                raise
    except (AssertionError, OSError, ValueError, subprocess.TimeoutExpired) as error:
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
    grade_rubric=False,
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
            grade_rubric=grade_rubric,
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
    parser.add_argument("--rubric-grade", action="store_true")
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
        grade_rubric=args.rubric_grade,
    )
    print_summary(summaries, summary_path)
    return 0 if all(summary["passed"] for summary in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
