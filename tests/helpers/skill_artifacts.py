import re
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
MARKETPLACE_PLUGIN_PATH = REPO_ROOT / "plugins" / "humanizer-plugin"
SKILL_PATH = REPO_ROOT / "skills" / "humanizer" / "SKILL.md"
REFERENCE_PATH = REPO_ROOT / "skills" / "humanizer" / "references" / "banned-list.md"
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "humanizer_contract_cases.json"


def read_text(path):
    return path.read_text(encoding="utf-8")


def load_fixture_cases():
    return json.loads(read_text(FIXTURE_PATH))["cases"]


def extract_frontmatter(markdown):
    if not markdown.startswith("---\n"):
        raise ValueError("Markdown document does not start with YAML frontmatter")

    closing_marker = "\n---\n"
    closing_index = markdown.find(closing_marker, len("---\n"))
    if closing_index == -1:
        raise ValueError("Markdown document does not close YAML frontmatter")

    return markdown[len("---\n") : closing_index]


def frontmatter_scalar(frontmatter, key):
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, re.MULTILINE)
    if match is None:
        raise KeyError(key)
    return match.group(1).strip()


def frontmatter_list(frontmatter, key):
    match = re.search(
        rf"^{re.escape(key)}:\n((?:\s+- .+\n?)+)",
        frontmatter,
        re.MULTILINE,
    )
    if match is None:
        raise KeyError(key)

    return [
        line.strip()[2:]
        for line in match.group(1).splitlines()
        if line.strip().startswith("- ")
    ]
