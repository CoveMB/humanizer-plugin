#!/usr/bin/env python3
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.helpers.output_contracts import validate_case_output  # noqa: E402
from tests.helpers.skill_artifacts import load_fixture_cases  # noqa: E402


def read_output(output_directory, case_id):
    output_path = output_directory / f"{case_id}.txt"
    if not output_path.exists():
        raise FileNotFoundError(f"missing output file: {output_path}")
    return output_path.read_text(encoding="utf-8")


def validate_outputs(output_directory):
    cases = load_fixture_cases()
    for case in cases:
        output = read_output(output_directory, case["id"])
        validate_case_output(case, output)
    return len(cases)


def main(argv):
    if len(argv) != 2:
        print("usage: validate_humanizer_outputs.py OUTPUT_DIR", file=sys.stderr)
        return 2

    output_directory = Path(argv[1])
    if not output_directory.is_dir():
        print(f"output directory does not exist: {output_directory}", file=sys.stderr)
        return 2

    try:
        validated_count = validate_outputs(output_directory)
    except (AssertionError, FileNotFoundError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"validated {validated_count} Humanizer output files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
