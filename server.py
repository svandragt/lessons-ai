# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown", "pyyaml"]
# ///
"""Simple lesson server.

Run server:   uv run server.py [port]
Static build: uv run server.py build [outdir]     (published lessons only)
Deploy:       uv run server.py deploy             (build + rsync to $LESSONS_RSYNC_DEST)

Lessons are drafts until their frontmatter has `published: true`.
Approve them from the browser; approving auto-deploys when
LESSONS_RSYNC_DEST is set (e.g. "user@example.com:/var/www/lessons/").
"""
import html as html_mod
import http.server
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import markdown
import yaml

LESSONS_DIR = Path(os.environ.get("LESSONS_DIR", "~/Documents/lessons")).expanduser()

STYLE = """
<style>
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
a { color: #2563eb; } a:visited { color: #7c3aed; }
code { background: rgba(127,127,127,.15); padding: .1em .3em; border-radius: 3px; }
pre { background: rgba(127,127,127,.12); padding: .8em; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; } td, th { border: 1px solid rgba(127,127,127,.4); padding: .3em .6em; }
.tag { display: inline-block; background: rgba(127,127,127,.15); border-radius: 999px; padding: .05em .7em; font-size: .85em; margin-right: .3em; }
.meta { color: #888; font-size: .9em; }
.draft { color: #b45309; font-weight: 600; }
.related { border-top: 1px solid rgba(127,127,127,.3); margin-top: 2rem; padding-top: 1rem; }
li.lesson { margin: .4em 0; }
form.publish { display: inline; }
form.publish button { background: #16a34a; color: white; border: 0; border-radius: 6px; padding: .3em .9em; cursor: pointer; }
</style>
"""


def load_lessons():
    lessons = []
    for f in sorted(LESSONS_DIR.glob("[0-9]*.md")):
        text = f.read_text()
        meta, body = {}, text
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if m:
            try:
                meta = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                meta = {}
            body = m.group(2)
        lessons.append({
            "file": f.name,
            "path": f,
            "slug": f.stem,
            "title": meta.get("concept", f.stem),
            "tags": set(meta.get("tags") or []),
            "project": meta.get("project", ""),
            "created": str(meta.get("created", "")),
            "published": bool(meta.get("published", False)),
            "body": body,
        })
    return lessons


def set_published(path):
    """Add or update `published: true` in the file's frontmatter."""
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return False
    front = m.group(1)
    if re.search(r"^published:", front, re.M):
        front = re.sub(r"^published:.*$", "published: true", front, flags=re.M)
    else:
        front += "\npublished: true"
    path.write_text(f"---\n{front}\n---\n" + text[m.end():])
    return True


def related(lesson, lessons):
    scored = []
    for other in lessons:
        if other["slug"] == lesson["slug"]:
            continue
        shared = lesson["tags"] & other["tags"]
        if shared:
            scored.append((len(shared), shared, other))
    scored.sort(key=lambda x: -x[0])
    return scored


def page(title, body):
    return f"<!doctype html><title>{title}</title>{STYLE}{body}".encode()


def hrefs(static):
    """Return (home, lesson, tag) URL builders for dynamic or static mode."""
    if static:
        return "index.html", lambda s: f"{s}.html", lambda t: f"tag-{t}.html"
    return "/", lambda s: f"/{s}", lambda t: f"/tag/{t}"


def tags_html(tags, static=False):
    _, _, tag_href = hrefs(static)
    return "".join(f'<a class="tag" href="{tag_href(t)}">{t}</a>' for t in sorted(tags))


def index_html(lessons, heading, static=False):
    home, lesson_href, _ = hrefs(static)
    items = "".join(
        f'<li class="lesson"><a href="{lesson_href(l["slug"])}">{l["title"]}</a> '
        + ('' if l["published"] or static else '<span class="draft">draft</span> ')
        + f'<span class="meta">{l["project"]} · {l["created"]}</span><br>{tags_html(l["tags"], static)}</li>'
        for l in lessons)
    back = '' if heading == "Lessons" else f'<p><a href="{home}">← all lessons</a></p>'
    search = '' if static else (
        '<form action="/search"><input name="q" placeholder="Search lessons…" '
        'style="padding:.4em .6em;width:60%"> <button>Search</button></form>')
    empty = '' if lessons else '<p class="meta">No matches.</p>'
    return page(heading, f"{back}<h1>{heading}</h1>{search}<ul>{items}</ul>{empty}")


def lesson_html(lesson, lessons, static=False):
    home, lesson_href, _ = hrefs(static)
    html = markdown.markdown(lesson["body"], extensions=["tables", "fenced_code"])
    rel = related(lesson, lessons)
    if static:
        rel = [r for r in rel if r[2]["published"]]
    rel_html = ""
    if rel:
        items = "".join(
            f'<li><a href="{lesson_href(o["slug"])}">{o["title"]}</a> '
            f'<span class="meta">shared: {", ".join(sorted(shared))}</span></li>'
            for _, shared, o in rel)
        rel_html = f'<div class="related"><h2>Related lessons</h2><ul>{items}</ul></div>'
    status = ""
    if not static:
        if lesson["published"]:
            status = ' · <span class="meta">published</span>'
        else:
            status = (' · <span class="draft">draft</span> '
                      f'<form class="publish" method="post" action="/publish/{lesson["slug"]}">'
                      '<button>Approve &amp; publish</button></form>')
    head = (f'<p><a href="{home}">← all lessons</a></p>'
            f'<p class="meta">{lesson["project"]} · {lesson["created"]} · '
            f'{tags_html(lesson["tags"], static)}{status}</p>')
    return page(lesson["title"], head + html + rel_html)


def build(outdir):
    """Render published lessons to static HTML in outdir."""
    out = Path(outdir).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    lessons = [l for l in load_lessons() if l["published"]]
    (out / "index.html").write_bytes(index_html(lessons, "Lessons", static=True))
    tags = set()
    for l in lessons:
        (out / f'{l["slug"]}.html').write_bytes(lesson_html(l, lessons, static=True))
        tags |= l["tags"]
    for t in tags:
        (out / f"tag-{t}.html").write_bytes(
            index_html([l for l in lessons if t in l["tags"]], f"Lessons tagged “{t}”", static=True))
    return len(lessons)


def deploy():
    """Build to a temp dir and rsync to $LESSONS_RSYNC_DEST."""
    dest = os.environ.get("LESSONS_RSYNC_DEST")
    if not dest:
        return "LESSONS_RSYNC_DEST not set — skipped deploy"
    tmp = tempfile.mkdtemp(prefix="lessons-site-")
    try:
        n = build(tmp)
        subprocess.run(["rsync", "-az", "--delete", f"{tmp}/", dest], check=True)
        return f"deployed {n} lessons to {dest}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        lessons = load_lessons()
        url = urlsplit(self.path)
        path = unquote(url.path.rstrip("/")) or "/"
        if path == "/":
            body = index_html(lessons, "Lessons")
        elif path == "/search":
            q = parse_qs(url.query).get("q", [""])[0].strip()
            hits = [l for l in lessons if q.lower() in
                    f'{l["title"]} {" ".join(l["tags"])} {l["body"]}'.lower()] if q else []
            body = index_html(hits, f"Search: “{html_mod.escape(q)}”")
        elif path.startswith("/tag/"):
            tag = path[5:]
            body = index_html([l for l in lessons if tag in l["tags"]],
                              f"Lessons tagged “{tag}”")
        else:
            slug = path.lstrip("/")
            lesson = next((l for l in lessons if l["slug"] == slug), None)
            if not lesson:
                self.send_error(404)
                return
            body = lesson_html(lesson, lessons)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = unquote(urlsplit(self.path).path.rstrip("/"))
        if not path.startswith("/publish/"):
            self.send_error(404)
            return
        slug = path[len("/publish/"):]
        lesson = next((l for l in load_lessons() if l["slug"] == slug), None)
        if not lesson or not set_published(lesson["path"]):
            self.send_error(404)
            return
        msg = deploy()
        print(f"published {slug}: {msg}")
        self.send_response(303)
        self.send_header("Location", f"/{slug}")
        self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        n = build(sys.argv[2] if len(sys.argv) > 2 else "./site")
        print(f"built {n} published lessons")
    elif len(sys.argv) > 1 and sys.argv[1] == "deploy":
        print(deploy())
    else:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8321
        print(f"Lessons at http://localhost:{port}/")
        http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
