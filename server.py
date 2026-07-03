# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown", "pyyaml"]
# ///
"""Simple lesson server. Run: uv run server.py [port]"""
import html as html_mod
import http.server
import os
import re
import sys
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
.related { border-top: 1px solid rgba(127,127,127,.3); margin-top: 2rem; padding-top: 1rem; }
li.lesson { margin: .4em 0; }
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
            "slug": f.stem,
            "title": meta.get("concept", f.stem),
            "tags": set(meta.get("tags") or []),
            "project": meta.get("project", ""),
            "created": str(meta.get("created", "")),
            "body": body,
        })
    return lessons


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


def tags_html(tags):
    return "".join(f'<a class="tag" href="/tag/{t}">{t}</a>' for t in sorted(tags))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        lessons = load_lessons()
        url = urlsplit(self.path)
        path = unquote(url.path.rstrip("/")) or "/"
        if path == "/":
            body = self.index_html(lessons, "Lessons")
        elif path == "/search":
            q = parse_qs(url.query).get("q", [""])[0].strip()
            hits = [l for l in lessons if q.lower() in
                    f'{l["title"]} {" ".join(l["tags"])} {l["body"]}'.lower()] if q else []
            body = self.index_html(hits, f"Search: “{html_mod.escape(q)}”")
        elif path.startswith("/tag/"):
            tag = path[5:]
            body = self.index_html([l for l in lessons if tag in l["tags"]],
                                   f"Lessons tagged “{tag}”")
        else:
            slug = path.lstrip("/")
            lesson = next((l for l in lessons if l["slug"] == slug), None)
            if not lesson:
                self.send_error(404)
                return
            body = self.lesson_html(lesson, lessons)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def index_html(self, lessons, heading):
        items = "".join(
            f'<li class="lesson"><a href="/{l["slug"]}">{l["title"]}</a> '
            f'<span class="meta">{l["project"]} · {l["created"]}</span><br>{tags_html(l["tags"])}</li>'
            for l in lessons)
        home = '' if heading == "Lessons" else '<p><a href="/">← all lessons</a></p>'
        search = ('<form action="/search"><input name="q" placeholder="Search lessons…" '
                  'style="padding:.4em .6em;width:60%"> <button>Search</button></form>')
        empty = '' if lessons else '<p class="meta">No matches.</p>'
        return page(heading, f"{home}<h1>{heading}</h1>{search}<ul>{items}</ul>{empty}")

    def lesson_html(self, lesson, lessons):
        html = markdown.markdown(lesson["body"], extensions=["tables", "fenced_code"])
        rel = related(lesson, lessons)
        rel_html = ""
        if rel:
            items = "".join(
                f'<li><a href="/{o["slug"]}">{o["title"]}</a> '
                f'<span class="meta">shared: {", ".join(sorted(shared))}</span></li>'
                for _, shared, o in rel)
            rel_html = f'<div class="related"><h2>Related lessons</h2><ul>{items}</ul></div>'
        head = (f'<p><a href="/">← all lessons</a></p>'
                f'<p class="meta">{lesson["project"]} · {lesson["created"]} · {tags_html(lesson["tags"])}</p>')
        return page(lesson["title"], head + html + rel_html)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8321
    print(f"Lessons at http://localhost:{port}/")
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
