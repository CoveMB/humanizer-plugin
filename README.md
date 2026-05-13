# Humanizer Plugin

A standalone Codex plugin for rewriting AI-drafted prose so it sounds more natural without inventing facts.

It combines three useful ideas:

- Humanizer's 31-pattern catalog for removing common AI-writing tells.
- Humanizer 2.6.0's hard factual-integrity rules.
- A Tagore and stop-slop inspired checklist and scoring gate for catching clean but soulless rewrites.

## What it does

Humanizer Plugin removes patterns such as significance inflation, promotional phrasing, vague attribution, em dash overuse, forced three-item lists, fake naming, self-narration, and chatbot wrappers.

It also checks the rewrite privately across directness, rhythm, trust, authenticity, density, factual integrity, restraint, and voice. The factual-integrity score has a stricter floor, so the plugin should ask for missing facts or keep language general instead of making vague text sound specific with invented details.

## Repository layout

```text
.codex-plugin/plugin.json
skills/humanizer/SKILL.md
skills/humanizer/references/banned-list.md
README.md
NOTICE
LICENSE
```

The Codex plugin manifest lives at `.codex-plugin/plugin.json`. The skill itself lives at `skills/humanizer/SKILL.md`.

## Install

Clone this repository into a local plugin directory and install it from Codex:

```bash
git clone git@github.com:CoveMB/humanizer-plugin.git ~/.codex/plugins/humanizer-plugin
```

For a repo-local plugin install, clone or copy this repository wherever your plugin marketplace points and use the repository root as the plugin source path.

## Usage

In Codex, invoke the skill by asking for Humanizer:

```text
Humanize this text:
[paste draft]
```

Useful prompts:

```text
Edit this to sound more natural.
```

```text
Match my writing sample and rewrite this.
```

```text
Audit and score this draft for AI-writing patterns.
```

By default, the plugin returns only the rewrite. If you ask for an audit, comparison, or score, it can include notes and the score summary after the rewritten text.

## Design principles

- Preserve meaning and voice.
- Do not invent names, numbers, sources, quotes, examples, prices, dates, or claims.
- Add specificity only when the user supplied it.
- Use natural rhythm without forced staccato or slogan-like closers.
- Keep the output concise unless the user asks for analysis.

## Sources and credits

This plugin is a standalone package derived from and inspired by:

- [humanizer](https://github.com/blader/humanizer) by blader, based on Wikipedia's "Signs of AI writing".
- [Tagore](https://github.com/apurvrdx1/tagore) by Apurv Ray.
- [stop-slop](https://github.com/hardikpandya/stop-slop) by Hardik Pandya.
- [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup.

See [NOTICE](NOTICE) for attribution details.

## License

MIT. See [LICENSE](LICENSE).
