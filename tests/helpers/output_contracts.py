import re


CHATBOT_WRAPPER_STARTS = (
    "here is",
    "here's",
    "certainly",
    "of course",
    "sure",
    "great question",
)

SUPPORTED_CONSTRAINT_KEYS = {
    "must_include",
    "must_match",
    "must_not_include",
    "must_not_match",
    "no_em_dash",
    "no_chatbot_wrapper",
    "no_contrast_frame",
    "no_markdown_fence",
    "rewrite_must_not_include",
    "rewrite_only",
    "max_question_marks",
}

REWRITE_SECTION_BOUNDARY_PATTERN = re.compile(
    r"(?im)^\s*(?:brief\s+notes|notes|score)\s*:"
)

CONTRAST_FRAME_PATTERNS = (
    r"(?i)\bnot\s+only\b[^.?!]{0,120}\bbut\b",
    r"(?i)\bnot\s+just\b[^.?!]{0,120}\bbut\b",
    r"(?i)\bnot\s+merely\b[^.?!]{0,120}\bbut\b",
    r"(?i)\bnot\s+(?:a|an|the)\b[^.?!]{0,120}\bbut\b",
    r"(?i)\bmore\s+than\s+just\b",
)

REWRITE_ONLY_META_FRAGMENTS = (
    "notes:",
    "score:",
    "changes made:",
    "rewrite:",
    "rewritten text:",
)


def normalize_text(text):
    return " ".join(text.strip().split())


def raise_if_violations(violations):
    violation_list = list(violations)
    if violation_list:
        raise AssertionError("\n".join(violation_list))


def require_fragments(case_id, output, fragments):
    lowered_output = output.lower()
    missing_fragments = [
        fragment for fragment in fragments if fragment.lower() not in lowered_output
    ]
    raise_if_violations(
        f"{case_id}: missing required fragment {fragment!r}"
        for fragment in missing_fragments
    )


def reject_fragments(case_id, output, fragments):
    lowered_output = output.lower()
    present_fragments = [
        fragment for fragment in fragments if fragment.lower() in lowered_output
    ]
    raise_if_violations(
        f"{case_id}: forbidden fragment present {fragment!r}"
        for fragment in present_fragments
    )


def reject_rewrite_fragments(case_id, output, fragments):
    rewrite_text = extract_rewrite_section(output)
    lowered_rewrite_text = rewrite_text.lower()
    present_fragments = [
        fragment for fragment in fragments if fragment.lower() in lowered_rewrite_text
    ]
    raise_if_violations(
        f"{case_id}: rewrite contains forbidden fragment {fragment!r}"
        for fragment in present_fragments
    )


def reject_patterns(case_id, output, patterns):
    matched_patterns = [pattern for pattern in patterns if re.search(pattern, output)]
    raise_if_violations(
        f"{case_id}: forbidden pattern matched {pattern!r}"
        for pattern in matched_patterns
    )


def require_patterns(case_id, output, patterns):
    missing_patterns = [
        pattern for pattern in patterns if re.search(pattern, output) is None
    ]
    raise_if_violations(
        f"{case_id}: required pattern missing {pattern!r}"
        for pattern in missing_patterns
    )


def reject_em_dash(case_id, output):
    if "\u2014" in output:
        raise AssertionError(f"{case_id}: output contains an em dash")


def reject_markdown_fence(case_id, output):
    if "```" in output:
        raise AssertionError(f"{case_id}: output contains a markdown fence")


def reject_contrast_frames(case_id, output):
    matched_patterns = [
        pattern for pattern in CONTRAST_FRAME_PATTERNS if re.search(pattern, output)
    ]
    raise_if_violations(
        f"{case_id}: contrast frame matched {pattern!r}"
        for pattern in matched_patterns
    )


def reject_rewrite_only_meta_commentary(case_id, output):
    lowered_output = output.lower()
    present_fragments = [
        fragment for fragment in REWRITE_ONLY_META_FRAGMENTS if fragment in lowered_output
    ]
    raise_if_violations(
        f"{case_id}: rewrite-only output contains meta fragment {fragment!r}"
        for fragment in present_fragments
    )


def reject_chatbot_wrapper(case_id, output):
    stripped_output = output.strip().lower()
    start_violations = (
        f"{case_id}: output starts with chatbot wrapper {wrapper_start!r}"
        for wrapper_start in CHATBOT_WRAPPER_STARTS
        if stripped_output.startswith(wrapper_start)
    )

    lowered_output = output.lower()
    wrapper_closers = ("i hope this helps", "let me know", "would you like me to")
    closer_violations = (
        f"{case_id}: output contains chatbot closer {wrapper_closer!r}"
        for wrapper_closer in wrapper_closers
        if wrapper_closer in lowered_output
    )
    raise_if_violations([*start_violations, *closer_violations])


def extract_rewrite_section(output):
    section_boundary = REWRITE_SECTION_BOUNDARY_PATTERN.search(output)
    if section_boundary is None:
        return output
    return output[: section_boundary.start()].strip()


def enforce_question_limit(case_id, output, maximum_question_marks):
    question_mark_count = output.count("?")
    if question_mark_count > maximum_question_marks:
        raise AssertionError(
            f"{case_id}: expected at most {maximum_question_marks} question marks, "
            f"found {question_mark_count}"
        )


def collect_violation(violations, check_function, *args):
    try:
        check_function(*args)
    except AssertionError as error:
        violations.append(str(error))


def validate_case_output(case, output):
    case_id = case["id"]
    constraints = case.get("constraints", {})
    normalized_output = normalize_text(output)
    violations = []

    collect_violation(
        violations,
        require_fragments,
        case_id,
        normalized_output,
        constraints.get("must_include", []),
    )
    collect_violation(
        violations,
        require_patterns,
        case_id,
        normalized_output,
        constraints.get("must_match", []),
    )
    collect_violation(
        violations,
        reject_fragments,
        case_id,
        normalized_output,
        constraints.get("must_not_include", []),
    )
    collect_violation(
        violations,
        reject_rewrite_fragments,
        case_id,
        output,
        constraints.get("rewrite_must_not_include", []),
    )
    collect_violation(
        violations,
        reject_patterns,
        case_id,
        normalized_output,
        constraints.get("must_not_match", []),
    )

    if constraints.get("no_em_dash", False):
        collect_violation(violations, reject_em_dash, case_id, normalized_output)

    if constraints.get("no_markdown_fence", False):
        collect_violation(violations, reject_markdown_fence, case_id, output)

    if constraints.get("no_chatbot_wrapper", False):
        collect_violation(violations, reject_chatbot_wrapper, case_id, normalized_output)

    if constraints.get("no_contrast_frame", False):
        collect_violation(violations, reject_contrast_frames, case_id, normalized_output)

    if constraints.get("rewrite_only", False):
        collect_violation(
            violations,
            reject_rewrite_only_meta_commentary,
            case_id,
            normalized_output,
        )

    if "max_question_marks" in constraints:
        collect_violation(
            violations,
            enforce_question_limit,
            case_id,
            normalized_output,
            constraints["max_question_marks"],
        )

    if violations:
        raise AssertionError("\n".join(violations))
