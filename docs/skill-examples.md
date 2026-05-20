# Skill examples

This repository ships one skill: `humanizer`.

Use this file when you need a prompt that matches a real editing situation. The skill contract still lives in `skills/humanizer/SKILL.md`; keep this guide in sync when that contract changes.

## Humanizer

Humanizer edits prose that sounds generated, padded, promotional, or too generic. It preserves the facts, claims, tone, and certainty the user supplied.

It does not fact check by default. It also should not invent details, names, numbers, dates, sources, quotes, prices, examples, citations, or claims. If a rewrite needs missing facts, Humanizer should ask for them, keep the sentence general, or remove the unsupported claim.

### Good fits

- A draft sounds generated and needs a natural rewrite.
- A paragraph has filler such as "at its core," "this highlights," "unlocking potential," or a forced three-part list.
- Technical documentation needs to keep its meaning but read less mechanically.
- The user provides a writing sample and wants the rewrite to match that voice.
- The user asks for an audit, score, or short explanation of AI-writing patterns.

### Poor fits

- The task is only translation, summarization, or spellcheck.
- The user asks for fact checking, research, sourcing, or citation lookup without asking for prose cleanup.
- The draft needs new facts the user has not supplied.
- Exact legal, medical, financial, or compliance wording matters more than style.

### Basic rewrite

Use this when the user wants cleaner prose with no notes.

```text
Use Humanizer to rewrite this. Return only the rewritten text:

AI-assisted coding serves as a pivotal moment in the evolution of software development, unlocking productivity, creativity, and alignment across cross-functional teams.
```

Humanizer should:

- Remove inflated phrasing such as "pivotal moment" and "unlocking."
- Preserve anchor terms such as "AI-assisted coding" and "cross-functional teams" when they define the subject and scope.
- Avoid adding unsupported claims about speed, quality, adoption, or business value.
- Return only the rewritten text.

### Documentation cleanup

Use this when the documentation is accurate but padded.

```text
Use Humanizer on this documentation paragraph. Keep the technical meaning intact:

This configuration serves as a robust foundation for scalable workflows, ensuring developers can seamlessly optimize productivity and foster alignment across teams.
```

Humanizer should:

- Keep concrete terms such as "configuration" and "scalable workflows."
- Cut filler such as "serves as," "robust foundation," "seamlessly," and "foster alignment."
- Keep the rewrite technical and restrained.
- Avoid adding implementation details.

### Voice calibration

Use this when the rewrite needs to sound like a specific person or team.

```text
Use Humanizer to rewrite the draft. Match the style of this writing sample.

Writing sample:
I prefer short release notes. Name the change, explain the risk, and stop. If there is uncertainty, say exactly what is still unknown.

Draft:
This release introduces a comprehensive enhancement to the validation pipeline, highlighting our commitment to robust developer experiences and setting the stage for future improvements.
```

Humanizer should:

- Read the sample before rewriting.
- Match the sample's sentence length, directness, punctuation habits, and tolerance for uncertainty.
- Keep only supplied facts.
- Avoid turning the release note into a marketing paragraph.

### Audit and score

Use this when the user wants feedback along with the rewrite.

```text
Use Humanizer to audit and score this draft for AI-writing patterns:

Our platform is more than just a tool; it is a testament to innovation, empowering teams to collaborate, create, and scale like never before.
```

Humanizer should:

- Put the rewrite first.
- Add concise notes after the rewrite.
- Use the `Score: NN/80` format when scoring is requested.
- Avoid `8/10`, percentages, or scores out of 100.

### Missing facts

Use this when a vague claim may need evidence before it can be rewritten safely.

```text
Use Humanizer on this. If a sentence needs missing facts to become specific, ask instead of inventing:

Industry reports show that Atlas Note adoption increased significantly last quarter, proving the product is transforming team knowledge management.
```

Humanizer should:

- Avoid inventing a report name, percentage, source, or citation.
- Ask for the missing source or keep the claim general.
- Preserve supplied details in any question, such as "Atlas Note," "adoption," and "last quarter."
- Remove unsupported certainty such as "proving" and "transforming."

### Deterministic activation

Use explicit activation when the workflow needs predictable skill use, such as support instructions, reproducible evals, or review handoffs.

```text
Use Humanizer to rewrite this:

[paste draft]
```

Avoid relying on automatic skill selection when activation matters. Client auto-selection can vary. This repository's live evals force a read of `skills/humanizer/SKILL.md` for positive cases because `codex exec` traces do not expose a separate skill-invocation event.
