# lessons

Tools around my TIL lesson notes in `~/Documents/lessons/`.

Lessons are markdown files named `NNN-slug.md` with YAML frontmatter
(`concept`, `created`, `project`, `tags`, `published`). They are
created by the Claude Code `lessons` skill (in `skill/SKILL.md`)
whenever I type `til <topic>` or ask about something new. The skill
scrubs personal/system information, since lessons may be published.

## Server

A single-file web server that renders the lessons:

```bash
uv run server.py          # http://localhost:8321/
uv run server.py 9000     # custom port
```

Features:

- Index of all lessons with project, date, and clickable tag pills
- Markdown rendering (tables, fenced code)
- Related lessons on each page, ranked by shared tags
- Tag pages (`/tag/django`) and full-text search (`/search?q=...`)

Lessons are re-read on every request, so new lessons show up without a
restart. Set `LESSONS_DIR` to point at a different lessons directory.

## Publishing

Lessons start as drafts. The server shows a draft badge and an
**Approve & publish** button on each draft; clicking it sets
`published: true` in the frontmatter and deploys.

```bash
uv run server.py build ./site   # render published lessons to static HTML
uv run server.py deploy         # build + rsync to $LESSONS_RSYNC_DEST
```

`LESSONS_RSYNC_DEST` is an rsync target like
`user@example.com:/var/www/lessons/`. Set it locally (e.g. in the
gitignored `devbox.json`); when set, publishing from the browser
auto-deploys. A `Makefile` wraps the common commands: `make run`,
`make build`, `make deploy`.

## Layout

- `server.py` — the web server (uv inline dependencies, no venv needed)
- `skill/SKILL.md` — the Claude Code lessons skill; symlinked from
  `~/dev/llm/skills/lessons`
- `~/Documents/lessons/server.py` is a symlink here for convenience
