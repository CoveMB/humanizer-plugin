# Humanizer

Humanizer is a fact-safe anti-slop writing skill with a Codex plugin wrapper. It rewrites AI-drafted or AI-sounding prose so it reads more naturally while preserving the facts, claims, tone, and level of certainty supplied by the user.

It works as a plain skill in Claude Code, OpenCode, and Codex. This repository root is also a Codex plugin package.

## What Humanizer does

Humanizer is an editing workflow for prose. It is useful for essays, release notes, documentation, posts, emails, reports, and other drafts where AI-writing patterns make the text sound padded, overconfident, promotional, or generic.

It does five main things:

- Detects 31 AI-writing patterns, including significance inflation, vague attribution, promotional language, superficial `-ing` analysis, forced three-item lists, em dash overuse, fake naming, self-narration, and chatbot wrappers.
- Rewrites the draft in a more natural voice while keeping the meaning intact.
- Protects factual integrity by refusing to invent names, numbers, dates, studies, citations, quotes, prices, examples, or claims.
- Matches a supplied writing sample when the user wants voice calibration.
- Runs a private checklist and scoring gate before returning the final rewrite.

For dense drafts, the skill can also load `skills/humanizer/references/banned-list.md`, which contains a longer list of phrases, structures, emojis, fake names, and style patterns to remove.

## What Humanizer does not do

Humanizer is not a fact checker by default. It can flag unsupported claims in the text you provide, but it does not research missing facts unless the user separately asks the agent to research.

It does not make vague text specific by inventing details. If the draft says "industry reports show adoption is rising" without naming the reports, Humanizer should keep the statement general, remove it, or ask for the missing source.

It does not guarantee that a detector will classify the result as human-written. The goal is better writing, not detector evasion.

It does not preserve every sentence, heading, punctuation mark, or list shape. It preserves meaning and factual content, then rewrites the structure when the structure itself is part of the problem.

It does not turn every draft casual. The target voice depends on the request and the source text. A technical note should stay technical. A formal report should stay formal.

## How it works

Humanizer runs this workflow internally:

1. Map the facts supplied by the user.
2. Calibrate to a writing sample if the user provides one.
3. Scan for the 31-pattern catalog.
4. Rewrite the text without adding unsupported specifics.
5. Add human texture only where the source allows it.
6. Run the mechanical checklist.
7. Score the rewrite privately.
8. Self-audit for remaining AI tells.
9. Return the rewrite.

By default, Humanizer returns only the rewritten text. If the user asks for an audit, score, comparison, or explanation, it can include brief notes after the rewrite.

## Quality gate

Version 2.7.0 adds a private quality gate inspired by stop-slop and Tagore. The gate keeps the skill from passing a rewrite that is technically clean but still flat, generic, or factually risky.

### Mechanics

| Dimension | Question |
|---|---|
| Directness | Does the prose state the point instead of announcing it? |
| Rhythm | Do sentence lengths and paragraph endings vary naturally? |
| Trust | Does it respect the reader without over-explaining? |
| Authenticity | Does it sound like a person instead of a generated explainer? |
| Density | Can anything be cut without losing meaning? |

### Substance

| Dimension | Question | Protects against |
|---|---|---|
| Factual integrity | Does every concrete detail come from the user or provided source? | Plausible but fabricated specifics |
| Restraint | Does the text state things at their actual size? | Puffery, significance inflation, notability padding |
| Voice | Is there a point of view suited to the context? | Clean but soulless prose |

The rewrite must score at least 56/80 overall, with mechanics at least 35/50 and substance at least 21/30. Factual integrity must score at least 9/10. If factual integrity fails, the skill should revise, ask for missing facts, or keep the line general.

## Pattern catalog

The full catalog lives in `skills/humanizer/SKILL.md`. This table summarizes what Humanizer looks for and how it usually fixes it.

### Content patterns

| # | Pattern | What changes |
|---|---|---|
| 1 | Significance inflation | Removes claims that ordinary facts are pivotal, vital, enduring, or symbolic without evidence. |
| 2 | Notability padding | Replaces broad media name-dropping with a specific sourced claim, or removes it. |
| 3 | Superficial `-ing` analysis | Cuts clauses like "highlighting" and "showcasing" when they add fake depth. |
| 4 | Promotional language | Replaces press-release phrasing with neutral description. |
| 5 | Vague attribution | Replaces "experts say" with named sources when supplied, or keeps the claim general. |
| 6 | Formulaic challenges sections | Removes stock "despite challenges" endings unless the draft includes real facts. |

### Language and grammar patterns

| # | Pattern | What changes |
|---|---|---|
| 7 | AI vocabulary | Cuts overused words such as "delve," "showcase," "testament," and abstract "landscape." |
| 8 | Copula avoidance | Replaces "serves as," "boasts," and "features" with simpler verbs when appropriate. |
| 9 | Negative parallelisms | Rewrites "not just X, but Y" and tailing fragments like "no guessing." |
| 10 | Rule of three | Removes forced triplets and keeps only the items the content needs. |
| 11 | Synonym cycling | Repeats the clearest noun instead of rotating through near-synonyms. |
| 12 | False ranges | Rewrites "from X to Y" constructions that do not describe a real scale. |
| 13 | Passive voice and subjectless fragments | Names the actor when doing so improves clarity. |

### Style patterns

| # | Pattern | What changes |
|---|---|---|
| 14 | Em dash overuse | Uses commas, periods, semicolons, or parentheses instead. |
| 15 | Boldface overuse | Removes mechanical emphasis. |
| 16 | Inline-header lists | Converts repeated bold-label bullets into prose when the list shape is filler. |
| 17 | Title Case headings | Uses sentence case unless the style guide says otherwise. |
| 18 | Emoji decoration | Removes decorative emoji from headings and bullets. |
| 19 | Curly quotation marks | Converts smart quotes to straight quotes for plain text contexts. |
| 26 | Hyphenated word pair overuse | Removes unnecessary hyphens from common word pairs. |
| 27 | Persuasive authority tropes | Removes phrases like "at its core" and "what really matters." |
| 28 | Signposting announcements | Removes "let's dive in" and similar setup lines. |
| 29 | Fragmented headers | Deletes one-line warmups that restate the heading. |
| 30 | Fake naming | Removes invented frameworks, methods, paradoxes, and flywheels. |
| 31 | Self-narration and rhetorical hooks | Replaces "this highlights" and "the key takeaway is" with the actual point. |

### Communication patterns

| # | Pattern | What changes |
|---|---|---|
| 20 | Chatbot artifacts | Removes preambles, praise, "I hope this helps," and "let me know" closers. |
| 21 | Knowledge-cutoff disclaimers | Removes model-limit disclaimers or asks for current facts. |
| 22 | Sycophantic tone | Replaces excessive agreement with direct response. |

### Filler and hedging

| # | Pattern | What changes |
|---|---|---|
| 23 | Filler phrases | Replaces "in order to," "due to the fact that," and similar padding. |
| 24 | Excessive hedging | Reduces stacked uncertainty to the actual level of certainty. |
| 25 | Generic positive conclusions | Replaces vague upbeat endings with supplied facts or removes them. |

## Installation

### Claude Code

Clone this repository into Claude Code's skills directory:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/CoveMB/humanizer-plugin.git ~/.claude/skills/humanizer
```

If you already have this repository locally, copy the skill and reference files:

```bash
mkdir -p ~/.claude/skills/humanizer
cp skills/humanizer/SKILL.md ~/.claude/skills/humanizer/
cp -R skills/humanizer/references ~/.claude/skills/humanizer/
```

### OpenCode

Clone this repository into OpenCode's skills directory:

```bash
mkdir -p ~/.config/opencode/skills
git clone https://github.com/CoveMB/humanizer-plugin.git ~/.config/opencode/skills/humanizer
```

Or copy the skill and references:

```bash
mkdir -p ~/.config/opencode/skills/humanizer
cp skills/humanizer/SKILL.md ~/.config/opencode/skills/humanizer/
cp -R skills/humanizer/references ~/.config/opencode/skills/humanizer/
```

OpenCode also scans `~/.claude/skills/` for compatibility, so a single clone into `~/.claude/skills/humanizer/` can cover both tools.

### Codex as a skill

Install Humanizer as a plain Codex skill:

```bash
mkdir -p ~/.codex/skills/humanizer
cp skills/humanizer/SKILL.md ~/.codex/skills/humanizer/
cp -R skills/humanizer/references ~/.codex/skills/humanizer/
```

Codex also supports shared agent skill directories in many setups:

```bash
mkdir -p ~/.agents/skills/humanizer
cp skills/humanizer/SKILL.md ~/.agents/skills/humanizer/
cp -R skills/humanizer/references ~/.agents/skills/humanizer/
```

Restart Codex or reload skills if your client requires it.

### Codex as a plugin

This repository root is the local Codex plugin package.

The plugin manifest is:

```text
.codex-plugin/plugin.json
```

The plugin loads this skill file:

```text
skills/humanizer/SKILL.md
```

For a local plugin install, copy the plugin package into your Codex plugins directory:

```bash
mkdir -p ~/.codex/plugins/humanizer-plugin
cp -R .codex-plugin skills README.md NOTICE LICENSE ~/.codex/plugins/humanizer-plugin/
```

If your Codex setup uses a repository-local plugin marketplace, add an entry that points at the installable package inside this repository:

```json
{
  "name": "humanizer-plugin",
  "source": {
    "source": "local",
    "path": "./."
  },
  "policy": {
    "installation": "INSTALLED_BY_DEFAULT",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

This repository also includes `.agents/plugins/marketplace.json` with that local entry for testing. Current Codex local marketplace entries must use a non-empty `source.path` that starts with `./`, and the plugin package must stay inside the marketplace root. Absolute paths are rejected by the loader.

After installing or updating the plugin, reload the Codex plugin catalog from the Codex app or CLI flow you use.

## Usage

### Basic rewrite

```text
Humanize this text:
[paste draft]
```

### Claude Code

```text
/humanizer

[paste draft]
```

### OpenCode

```text
/humanizer

[paste draft]
```

### Codex

Ask for the installed Humanizer skill or plugin by name:

```text
Use Humanizer to rewrite this:
[paste draft]
```

If your Codex client supports explicit skill mentions, select the Humanizer skill and provide the draft.

### Trigger behavior

After Humanizer is installed and the skill/plugin catalog is reloaded, clients that support automatic skill selection can auto-select Humanizer when the prompt clearly asks for anti-AI writing cleanup. Typical trigger phrasing includes:

```text
This release note sounds padded. Tighten it without adding facts.
```

```text
Edit this documentation paragraph so it reads like a person wrote it, but keep the technical meaning intact.
```

```text
Clean up this dense AI-sounding draft. Return only the rewritten text.
```

Do not treat auto-selection as guaranteed in workflows where activation matters. For deterministic runs, reviews, CI, or support instructions, use an explicit prompt such as `Use Humanizer to rewrite this:` or select the Humanizer skill/plugin in the client UI.

The repository live evals include contextual trigger prompts, but `codex exec` currently does not expose a separate skill-invocation event. For that reason, positive live cases force a `skills/humanizer/SKILL.md` read so the trace proves the current skill instructions were used; they validate prompt coverage and output behavior, not an end-to-end guarantee of automatic client-side selection.

### Voice calibration

Provide a sample when you want the rewrite to sound like a specific person:

```text
Humanize this text. Match my style from this sample:

[paste 2 or 3 paragraphs of sample writing]

Draft:
[paste draft]
```

Humanizer will inspect sentence length, word choice, paragraph starts, punctuation habits, transitions, and recurring phrasing before rewriting.

### Audit and scoring

Ask for an audit when you want notes instead of a rewrite-only response:

```text
Audit and score this draft for AI-writing patterns:
[paste draft]
```

The response should put the rewritten text first, followed by concise notes and a score summary.

### Missing facts

If the text needs details that were not supplied, use a prompt that gives Humanizer permission to ask:

```text
Humanize this. If a sentence needs missing facts to become specific, ask instead of inventing:
[paste draft]
```

## Output behavior

For a normal rewrite request, Humanizer should return only the revised text. It should not add "here is," "I hope this helps," a change log, or a closing invitation.

For an audit, score, comparison, or explanation request, Humanizer should include the rewrite first, then short notes.

If the draft contains claims that cannot be made specific without new information, Humanizer should keep the language general, remove the claim, or ask for the missing detail.

## Example

Before:

```text
Great question! AI-assisted coding serves as an enduring testament to the transformative potential of large language models, marking a pivotal moment in the evolution of software development. At its core, the value proposition is clear: streamlining processes, enhancing collaboration, and fostering alignment. It is not just about autocomplete, it is about unlocking creativity at scale. Industry observers have noted that adoption continues to grow. In conclusion, the future looks bright. Let me know if you would like me to expand on this.
```

After:

```text
AI coding assistants can help with drafts, tests, and routine edits. The useful part is speed, but the output still needs review.

The adoption claim is too vague as written. "Industry observers" does not identify a source or provide data, so the safer version is simple: these tools may speed up parts of software work, but teams still need human review and tests.
```

## Repository layout

```text
.codex-plugin/plugin.json
.agents/plugins/marketplace.json
skills/humanizer/SKILL.md
skills/humanizer/references/banned-list.md
evals/humanizer_eval_cases.json
scripts/run_humanizer_evals.py
scripts/validate_humanizer_outputs.py
tests/
README.md
NOTICE
LICENSE
```

`skills/humanizer/SKILL.md` and `skills/humanizer/references/banned-list.md` are the source files for the bundled skill. The repository root is also the installable local marketplace package.

## Maintenance checklist

Before releasing a change:

- Update the version in `skills/humanizer/SKILL.md`.
- Update `.codex-plugin/plugin.json` if the plugin metadata changed.
- Keep the README pattern summary consistent with `skills/humanizer/SKILL.md`.
- Keep `NOTICE` current when adding or changing source material.

## Testing

Run the deterministic test suite:

```bash
make test
```

The tests check the skill manifest, YAML frontmatter, hard rules, scoring gate, reference catalog, fixture coverage, and output validators.

To validate saved Humanizer outputs from a manual or agent run, create one text file per fixture case using the case id as the file name:

```text
output-dir/
  dense_ai_rewrite.txt
  missing_source_handling.txt
  voice_calibration.txt
  audit_mode.txt
  dense_banned_list_scrub.txt
  contextual_release_notes.txt
  contextual_docs_cleanup.txt
  negative_fact_check_only.txt
  negative_translate_only.txt
  negative_summary_only.txt
  negative_spellcheck_only.txt
```

Then run:

```bash
make validate-humanizer-output OUTPUT_DIR=output-dir
```

To run live Codex skill evals, start with a dry run:

```bash
make eval-humanizer-dry-run
```

Then run the live suite when the local Codex CLI is authenticated and the model is available:

```bash
make eval-humanizer
```

The live runner executes the prompts in `evals/humanizer_eval_cases.json` through `codex exec --json` in a read-only sandbox, writes JSONL traces and final outputs under `evals/artifacts/latest/`, checks trigger-related trace terms, records token and command counts in the summary, and reuses the saved-output contracts for cases that map to `tests/fixtures/humanizer_contract_cases.json`.

Some live cases also define rubric IDs for semantic review. Add `EVAL_ARGS='--rubric-grade'` to run the optional second-pass grader, which writes rubric prompts, traces, stderr, and JSON grades under `evals/artifacts/latest/`.

For reproducibility, the runner ignores user config and project rules, points Codex at this repository as `humanizer-plugin-local`, enables `humanizer-plugin@humanizer-plugin-local`, uses ephemeral sessions, and pins the default eval model to `gpt-5.5`. Positive skill cases set `force_skill_file_read` so the trace proves the current `skills/humanizer/SKILL.md` file was used; dense catalog cases can also set `force_reference_file_read` to prove `skills/humanizer/references/banned-list.md` was loaded. The runner does not treat output-only direct `$humanizer` prompts as skill activation proof, because current `codex exec` traces do not expose a separate skill-invocation event for that path. Use `EVAL_ARGS='--model <model>'` to test another model, or `EVAL_ARGS='--timeout-seconds 600'` for slower environments.

Useful eval flags:

```bash
make eval-humanizer-dry-run EVAL_ARGS='--filter explicit_dense_rewrite'
make eval-humanizer EVAL_ARGS='--filter explicit_dense_rewrite --rubric-grade'
make eval-humanizer EVAL_ARGS='--model gpt-5.5 --timeout-seconds 600'
make eval-humanizer-dry-run EVAL_ARGS='--cases evals/humanizer_eval_cases.json --artifacts-dir evals/artifacts/latest --codex-bin codex'
```

Repeat `--filter` locally to run more than one focused case. Use `--cases` only when testing an alternate eval matrix, `--artifacts-dir` only when keeping artifacts separate from `evals/artifacts/latest/`, and `--codex-bin` only when testing a non-default Codex executable.

### Manual live eval workflow

Normal push and pull-request CI runs only deterministic checks. It runs the eval matrix dry-run and a representative dry-run with `--filter`, `--rubric-grade`, `--model`, `--timeout-seconds`, `--cases`, `--artifacts-dir`, and `--codex-bin` so flag wiring is covered without invoking Codex. The live eval is available as a separate GitHub Actions workflow named `Live Eval` and must be started manually from the Actions tab.

To enable it:

1. Create an OpenAI Platform API key with access to the eval model.
2. Add a repository Actions secret named `OPENAI_API_KEY`.
3. Confirm the API project has billing and rate limits for the selected model.
4. Open GitHub Actions, choose `Live Eval`, click `Run workflow`, select the branch, and optionally set:
   - `model`, default `gpt-5.5`
   - `timeout_seconds`, default `300`
   - `filter`, a single eval case id for a focused run
   - `rubric_grade`, default `false`, to run the optional rubric grading pass

The workflow installs the Codex CLI, stores auth in the temporary runner `CODEX_HOME`, runs `make test`, runs `make eval-humanizer-dry-run`, then runs the live eval. It uploads `evals/artifacts/latest/` even when the eval fails, so traces, prompts, stderr, and outputs are available for debugging.

## Sources and credits

Humanizer 2.7.3 is derived from and inspired by these sources:

- [humanizer](https://github.com/blader/humanizer) by blader, based on Wikipedia's "Signs of AI writing" guide.
- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup.
- [stop-slop](https://github.com/hardikpandya/stop-slop) by Hardik Pandya, used as inspiration for the mechanical checklist and scoring gate.
- [Tagore](https://github.com/apurvrdx1/tagore) by Apurv Ray, used as inspiration for the combined catalog-plus-scoring workflow and substance scoring.

See `NOTICE` for attribution and license details.

## Version history

- **2.7.3**: Tightened dense rewrite guidance so removed filler items are not replaced with new broad work categories such as smaller coding tasks.
- **2.7.2**: Tightened fact preservation for scoped noun phrases and made rule-of-three cleanup drop generic filler items instead of preserving source triplets mechanically.
- **2.7.1**: Tightened Codex skill activation metadata for padded prose and requests to make text read like a person wrote it.
- **2.7.0**: Added the fact-safe quality gate, including stop-slop-inspired mechanical checks, scoring thresholds, and Tagore-inspired substance scoring while keeping Humanizer's factual-integrity rules.
- **2.6.0**: Ported stricter guardrails for factual integrity, fake naming, self-narration, rhetorical hooks, no-preamble output, and safer examples.
- **2.5.1**: Added passive voice and subjectless fragments, raising the catalog to 29 patterns.
- **2.5.0**: Added persuasive framing, signposting, fragmented headers, expanded negative parallelisms, and tighter wording around em dash overuse.
- **2.4.0**: Added voice calibration from writing samples.
- **2.3.0**: Added hyphenated word pair overuse.
- **2.2.0**: Added a final "obviously AI generated" audit and second-pass rewrite.
- **2.1.1**: Fixed the quotation-mark example.
- **2.1.0**: Added before and after examples for all 24 patterns.
- **2.0.0**: Rebuilt the skill from the Wikipedia "Signs of AI writing" guide.
- **1.0.0**: Initial release.

## License

Humanizer Plugin uses mixed licensing:

- Original repository code, tests, scripts, plugin metadata, and CoveMB-authored additions are MIT. See `LICENSE`.
- MIT-licensed upstream material from blader's humanizer, stop-slop, and Tagore is credited in `NOTICE`.
- Text and pattern guidance adapted from Wikipedia's "Signs of AI writing" remain under CC BY-SA 4.0. Those portions are attributed in `NOTICE`; downstream adaptations should preserve the CC BY-SA 4.0 attribution, license, and change notices.
