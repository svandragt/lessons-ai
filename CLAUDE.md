# lessons project

Single-file Python web server (`server.py`) that renders TIL lesson
notes, plus the Claude Code lessons skill (`skill/SKILL.md`).

- Lesson data lives in `~/Documents/lessons/NNN-slug.md`, NOT in this
  repo. `LESSONS_DIR` env var overrides the location.
- Run with `uv run server.py [port]` — dependencies are declared inline
  (PEP 723); do not add a requirements.txt or venv.
- Keep it a single file and stdlib http.server; no framework.
- `skill/SKILL.md` is symlinked from `~/dev/llm/skills/lessons`, which
  `~/.claude/skills/lessons` points at. Editing it here updates the
  live skill — keep frontmatter valid.
- Lesson frontmatter keys the server relies on: `concept`, `created`,
  `project`, `tags`. Update `load_lessons()` if the skill's format
  changes.
