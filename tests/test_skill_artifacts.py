import json
import unittest

from tests.helpers.skill_artifacts import (
    MANIFEST_PATH,
    MARKETPLACE_PATH,
    MARKETPLACE_PLUGIN_PATH,
    REFERENCE_PATH,
    REPO_ROOT,
    SKILL_PATH,
    extract_frontmatter,
    frontmatter_list,
    frontmatter_scalar,
    read_text,
)


WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test.yml"
LIVE_EVAL_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "live-eval.yml"


class SkillArtifactTests(unittest.TestCase):
    def setUp(self):
        self.skill_markdown = read_text(SKILL_PATH)
        self.frontmatter = extract_frontmatter(self.skill_markdown)
        self.manifest = json.loads(read_text(MANIFEST_PATH))
        self.marketplace = json.loads(read_text(MARKETPLACE_PATH))
        self.reference_markdown = read_text(REFERENCE_PATH)

    def test_required_files_exist(self):
        self.assertTrue(MANIFEST_PATH.exists(), MANIFEST_PATH)
        self.assertTrue(MARKETPLACE_PATH.exists(), MARKETPLACE_PATH)
        self.assertTrue(SKILL_PATH.exists(), SKILL_PATH)
        self.assertTrue(REFERENCE_PATH.exists(), REFERENCE_PATH)

    def test_manifest_points_at_skill_directory(self):
        self.assertEqual(self.manifest["skills"], "./skills/")
        self.assertEqual(self.manifest["name"], "humanizer-plugin")
        self.assertEqual(self.manifest["interface"]["displayName"], "Humanizer Plugin")

    def test_manifest_default_prompts_fit_codex_limits(self):
        default_prompts = self.manifest["interface"]["defaultPrompt"]
        self.assertLessEqual(len(default_prompts), 3)
        for default_prompt in default_prompts:
            self.assertLessEqual(len(default_prompt), 128)

    def test_manifest_skill_directory_exists(self):
        plugin_root = MANIFEST_PATH.parents[1]
        skill_directory = plugin_root / self.manifest["skills"]
        self.assertTrue(skill_directory.is_dir(), skill_directory)

    def test_repo_marketplace_points_at_plugin_root(self):
        plugins = self.marketplace["plugins"]
        self.assertEqual(len(plugins), 1)

        plugin_entry = plugins[0]
        source = plugin_entry["source"]
        self.assertEqual(plugin_entry["name"], "humanizer-plugin")
        self.assertEqual(source["source"], "local")
        self.assertTrue(source["path"].startswith("./"))
        self.assertTrue(source["path"][2:])
        self.assertEqual(REPO_ROOT / source["path"], MARKETPLACE_PLUGIN_PATH)
        self.assertTrue(MARKETPLACE_PLUGIN_PATH.joinpath(".codex-plugin", "plugin.json").exists())

    def test_marketplace_plugin_copy_stays_in_sync(self):
        copied_manifest_path = MARKETPLACE_PLUGIN_PATH / ".codex-plugin" / "plugin.json"
        copied_skill_path = MARKETPLACE_PLUGIN_PATH / "skills" / "humanizer" / "SKILL.md"
        copied_reference_path = (
            MARKETPLACE_PLUGIN_PATH
            / "skills"
            / "humanizer"
            / "references"
            / "banned-list.md"
        )

        self.assertEqual(read_text(MANIFEST_PATH), read_text(copied_manifest_path))
        self.assertEqual(read_text(SKILL_PATH), read_text(copied_skill_path))
        self.assertEqual(read_text(REFERENCE_PATH), read_text(copied_reference_path))

    def test_manifest_and_skill_versions_match(self):
        self.assertEqual(
            self.manifest["version"],
            frontmatter_scalar(self.frontmatter, "version"),
        )
        self.assertRegex(self.manifest["version"], r"^\d+\.\d+\.\d+$")

    def test_frontmatter_defines_trigger_contract(self):
        self.assertEqual(frontmatter_scalar(self.frontmatter, "name"), "humanizer")
        description = self.frontmatter.lower()
        required_trigger_terms = [
            "remove signs of ai-generated writing",
            "editing or reviewing",
            "fact-safe checklist",
            "scoring gate",
            "user says text sounds padded",
            "asks to make it read like a person wrote it",
        ]
        for required_trigger_term in required_trigger_terms:
            self.assertIn(required_trigger_term, description)
        self.assertNotIn("or reads like a person wrote it", description)

    def test_allowed_tools_are_intentional(self):
        self.assertEqual(
            frontmatter_list(self.frontmatter, "allowed-tools"),
            ["Read", "Write", "Edit", "Grep", "Glob", "AskUserQuestion"],
        )

    def test_hard_rules_cover_high_risk_failures(self):
        required_rules = [
            "Do not invent details",
            "No em dashes",
            "No forced rule-of-three lists",
            "No contrast framing",
            "No `not just` phrasing",
            "No dramatic staccato bursts",
            "No rhetorical transition hooks",
            "No fake naming",
            "No self-narration",
            "No chatbot wrapper",
            "No vague attribution",
            "Preserve supplied concrete nouns",
        ]
        for required_rule in required_rules:
            self.assertIn(required_rule, self.skill_markdown)

    def test_concrete_noun_rule_preserves_exact_number(self):
        expected_patterns = [
            r"Keep the user's exact noun where possible",
            r"including singular or plural form",
            r"teams` to `people`",
            r"platform",
            r"scope qualifiers",
            r"cross-functional teams",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_mechanical_checklist_catches_flattened_scope_qualifiers(self):
        expected_patterns = [
            r"Changed, dropped, or generalized supplied noun phrases or scope qualifiers",
            r"`platform`, `configuration`, and `cross-functional teams`",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_final_verification_pass_preserves_anchor_terms_and_blocks_triads(self):
        expected_patterns = [
            r"Final Verification Pass",
            r"Preserve every supplied anchor noun",
            r"`configuration`, `scalable workflows`, `platform`, and `cross-functional teams`",
            r"Preserve adjective-noun domain phrases exactly",
            r"parallel gerund triads",
            r"`writing documentation, improving tests, and keeping work aligned`",
            r"Do not replace vague source benefits with new benefit claims",
            r"`routine code`, `rough edges`, `by hand`, `the actual problem`, or `bigger value`",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_rule_of_three_guidance_drops_generic_filler_items(self):
        expected_patterns = [
            r"Do not preserve a three-item list just because the source used one",
            r"generic filler item",
            r"do not invent a third work category",
            r"alignment",
            r"fostering alignment",
            r"keeping teams aligned",
            r"writing documentation, improving tests, and helping developers keep momentum",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_scoring_gate_thresholds_are_present(self):
        required_thresholds = [
            "Total must be at least 56/80",
            "Mechanics must be at least 35/50",
            "Substance must be at least 21/30",
            "Factual integrity must be at least 9/10",
        ]
        for required_threshold in required_thresholds:
            self.assertIn(required_threshold, self.skill_markdown)

    def test_reference_file_is_named_and_contains_expected_catalogs(self):
        self.assertIn("references/banned-list.md", self.skill_markdown)
        required_reference_sections = [
            "## Transition words to avoid",
            "## Adjectives AI overuses",
            "## Plain-word swaps",
            "## Contrast framing (all variants)",
            "## Rule-of-three (all variants)",
            "## Fake naming",
        ]
        for required_reference_section in required_reference_sections:
            self.assertIn(required_reference_section, self.reference_markdown)

    def test_output_format_contract_is_explicit(self):
        expected_patterns = [
            r"If the user only asks for a rewrite, provide only the rewritten text",
            r"If the user asks for an audit, comparison, score, or explanation",
            r"Score: NN/80",
            r"ask a short question or keep the sentence general instead of inventing details",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_missing_fact_questions_preserve_entity_metric_and_timeframe(self):
        expected_patterns = [
            r"include the supplied entity, metric, and timeframe",
            r"Which reports support Atlas Note's 43% adoption increase last quarter\?",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_audit_scores_are_not_ten_point_output_scores(self):
        expected_patterns = [
            r"never output `Score: 8/10`",
            r"example audit score is `Score: 64/80`",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(self.skill_markdown, expected_pattern)

    def test_high_risk_output_rules_precede_long_pattern_catalog(self):
        catalog_index = self.skill_markdown.index("## CONTENT PATTERNS")
        high_risk_rules = [
            "## Output Format",
            "include the supplied entity, metric, and timeframe",
            "never output `Score: 8/10`",
        ]

        for high_risk_rule in high_risk_rules:
            with self.subTest(rule=high_risk_rule):
                self.assertLess(self.skill_markdown.index(high_risk_rule), catalog_index)

    def test_skill_has_all_31_pattern_headings(self):
        for pattern_number in range(1, 32):
            self.assertRegex(self.skill_markdown, rf"### {pattern_number}\. ")

    def test_readme_references_current_repository_layout(self):
        readme_markdown = read_text(REPO_ROOT / "README.md")
        self.assertIn(".codex-plugin/plugin.json", readme_markdown)
        self.assertIn("scripts/run_humanizer_evals.py", readme_markdown)
        self.assertIn("--timeout-seconds", readme_markdown)
        self.assertIn("--rubric-grade", readme_markdown)
        self.assertIn("https://github.com/CoveMB/humanizer-plugin.git", readme_markdown)
        self.assertNotIn("--branch humanizer-plugin", readme_markdown)
        self.assertNotIn("github.com/CoveMB/humanizer.git", readme_markdown)
        self.assertNotIn("plugins/humanizer/", readme_markdown)
        self.assertNotIn("scripts/sync-plugin.sh", readme_markdown)

    def test_readme_documents_trigger_behavior_and_limits(self):
        readme_markdown = read_text(REPO_ROOT / "README.md")
        expected_patterns = [
            r"### Trigger behavior",
            r"can auto-select Humanizer",
            r"This release note sounds padded",
            r"reads like a person wrote it",
            r"Use Humanizer",
            r"not treat auto-selection as guaranteed",
            r"codex exec",
            r"does not expose a separate skill-invocation event",
        ]
        for expected_pattern in expected_patterns:
            self.assertRegex(readme_markdown, expected_pattern)

    def test_ci_runs_deterministic_quality_gates(self):
        workflow = read_text(WORKFLOW_PATH)
        required_commands = [
            "fetch-depth: 0",
            "github.event_name",
            "github.base_ref",
            "github.event.before",
            "git diff --check",
            "make test",
            "make eval-humanizer-dry-run",
        ]
        for required_command in required_commands:
            self.assertIn(required_command, workflow)

    def test_live_eval_workflow_is_manual_and_authenticates_codex(self):
        workflow = read_text(LIVE_EVAL_WORKFLOW_PATH)
        required_snippets = [
            "workflow_dispatch:",
            "npm i -g @openai/codex@latest",
            "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}",
            "credentials_store = \"file\"",
            "codex login --with-api-key",
            "make test",
            "make eval-humanizer-dry-run",
            "rubric_grade:",
            "EVAL_RUBRIC_GRADE: ${{ inputs.rubric_grade }}",
            "eval_args+=(--rubric-grade)",
            "scripts/run_humanizer_evals.py",
            "actions/upload-artifact@v4",
        ]
        forbidden_snippets = [
            "push:",
            "pull_request:",
        ]

        for required_snippet in required_snippets:
            self.assertIn(required_snippet, workflow)

        for forbidden_snippet in forbidden_snippets:
            self.assertNotIn(forbidden_snippet, workflow)


if __name__ == "__main__":
    unittest.main()
