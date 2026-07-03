---
name: lessons
description: "Capture concepts the user is learning as numbered lesson files. Use when the user signals they are learning something new — 'what is X?', 'explain X', 'I don't understand X', 'how does X work?', 'TIL', 'never heard of X', 'first time using X', 'new to me' — AND the concept appears unfamiliar to them. Writes lessons to ~/Documents/lessons/NNN-slug.md (one central, cross-project location) with a short explanation, read-more links, and up to three minimally-scoped exercises. Also handles: 'list lessons', 'show lesson N', 'next exercise'."
---

# Lessons Skill

Turns moments of learning into durable, reviewable notes. When the user encounters a concept that is new *to them*, capture it as a lesson in `~/Documents/lessons/` (one central, cross-project location — single brain, single notebook) so they can revisit and practice it later.

## When to invoke

Invoke when BOTH conditions hold:

1. **Learning signal** — the user has said something like:
   - "what is X?", "what does X mean?", "explain X"
   - "I don't get X", "I don't understand X", "confused about X"
   - "first time seeing X", "new to me", "never used X before", "TIL"
   - "how does X work?" *(only when paired with novelty — not routine API lookups)*

2. **Novelty** — the concept is plausibly new to *this* user. Skip if:
   - It is something they have already used in this session/repo confidently.
   - A lesson with the same concept already exists in `~/Documents/lessons/`.
   - The question is a quick factual lookup ("what's the flag for X?") rather than a concept.

When in doubt, ask once: *"Want me to save a lesson for this?"* — then proceed if yes.

## What a lesson is

A single markdown file at `~/Documents/lessons/NNN-slug.md` where `NNN` is a zero-padded integer one greater than the highest existing prefix across the whole `~/Documents/lessons/` directory (start at `001`). The slug is kebab-case derived from the concept name. Numbering is global across projects, not per-project.

### File template

```markdown
---
concept: {{Concept name}}
created: {{YYYY-MM-DD}}
project: {{auto-detected repo or dir name — omit field entirely if detection fails}}
tags: [{{relevant, keywords}}]
---

# {{Concept name}}

## The idea
{{2–5 sentences. Plain language. Lead with what it *is* and why it matters.
Avoid jargon unless you immediately define it. If an analogy helps, use one.}}

## How it shows up
{{1–3 sentences or a tiny code/CLI snippet showing the concept in the wild —
ideally tied to what the user was just doing.}}

## Read more
- [{{Title}}]({{url}})
- [{{Title}}]({{url}})
{{2–4 links. Prefer official docs, canonical specs, or well-known explainers.
Only include URLs you are confident exist; if unsure, omit rather than guess.}}

## Exercises
{{1–3 exercises. Each must be:
 - minimally scoped (5–15 minutes)
 - concrete and verifiable (the user knows when they are done)
 - progressive (each builds on the last)
Format each as a numbered item with a one-line goal and a "Done when:" check.}}

1. **{{Goal}}** — {{one sentence of guidance}}
   *Done when:* {{observable result}}
2. ...
3. ...
```

## Rules

1. **Central location.** All lessons live in `~/Documents/lessons/`, regardless of which project the user is working in. `mkdir -p` on first use.
2. **Auto-detect `project:`.** Before writing, determine the project name from cwd:
   - In a git repo: `basename "$(git rev-parse --show-toplevel)"`.
   - Otherwise: `basename "$PWD"`.
   - If detection errors, omit the `project:` line entirely rather than guess.
3. **Number sequentially across the whole directory.** Scan existing files in `~/Documents/lessons/`, take the max `NNN`, add one. Pad to three digits.
4. **One concept per lesson.** If the user is learning two related things, write two lessons rather than one mega-file.
5. **Keep it short.** A lesson should be readable in 2 minutes. Long lessons do not get revisited.
6. **Tailor to the user's apparent level.** If they wrote senior-level code elsewhere in the session, do not over-explain basics; if they said "first time," start from zero.
7. **No fabricated links.** Better to give one solid link than three plausible-looking guesses.
8. **Exercises are optional ceiling, not floor.** Zero exercises is fine if the concept is purely conceptual; never exceed three.
9. **No personal or system information.** Lessons may be published publicly. Before writing, scrub anything identifying: real usernames, email addresses, hostnames, IP addresses, absolute paths containing a username (use `~/...`), client or employer names, secrets/tokens, and internal URLs. Replace any such detail with generic example data (`user@example.com`, `example-project`, `/home/user/...`). Personal project names and generic code snippets are fine.
10. **Lessons start as drafts.** Do not add a `published:` key when creating a lesson — the user reviews and approves each lesson in the browser (via the lessons server's "Approve & publish" button) before it goes live.
11. **Announce, do not interrupt.** After saving, mention the file path in one line and continue with the user's original task.

## Other commands

- *"list lessons"* → `ls ~/Documents/lessons/` and show titles.
- *"list lessons for <project>"* → grep frontmatter `project:` in `~/Documents/lessons/*.md` and show titles where it matches.
- *"show lesson N"* → read and display `~/Documents/lessons/NNN-*.md`.
- *"next exercise"* → find the most recent lesson and surface its first unchecked exercise.
- *"mark exercise N done in lesson M"* → edit the file to check the box (use `- [x]` style if user prefers, otherwise add a "✓ completed {{date}}" note).

## Example trigger

> User: "Wait, what's a monad? I keep seeing it in this Haskell code."

→ Detect learning signal + novelty → write `~/Documents/lessons/NNN-monads.md` with a plain-language explanation, links to *Learn You a Haskell* and the Haskell wiki, and 2–3 tiny exercises (e.g., "write a function that returns `Maybe Int` and chain two of them with `>>=`"). Then answer the original question inline as well.
