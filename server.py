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
#note-btn { position: absolute; display: none; background: #ffe066; color: #1a1a1a; border: 0;
  border-radius: 6px; padding: .3em .8em; font-size: .85em; font-weight: 600; cursor: pointer; z-index: 10; }
.notes { border-top: 1px solid rgba(127,127,127,.3); margin-top: 2rem; padding-top: 1rem; }
.note-item { background: #fef3c1; color: #1a1a1a; border-radius: 6px; padding: .6em .8em; margin: .5em 0; }
.note-item blockquote { margin: 0 0 .4em; padding-left: .6em; border-left: 3px solid rgba(127,127,127,.4);
  color: #6b5b00; font-size: .9em; }
.note-item button { float: right; background: none; border: 0; color: #b45309; cursor: pointer; margin-left: .6em; }
mark.noted { background: #ffe066; color: #1a1a1a; border-radius: 3px; cursor: pointer; padding: 0 .05em; }
</style>
"""

NOTES_SCRIPT = """
<script>
(function() {
  var key = "lesson-notes:%s";
  var notes = JSON.parse(localStorage.getItem(key) || "[]");
  var list = document.getElementById("notes-list");

  var lessonBody = document.getElementById("lesson-body");
  var noteBtn = document.getElementById("note-btn");

  function render() {
    list.innerHTML = notes.length ? "" : '<p class="meta">No notes yet — select some text to add one.</p>';
    notes.forEach(function(n, i) {
      var div = document.createElement("div");
      div.className = "note-item";
      var btn = document.createElement("button");
      btn.textContent = "Remove";
      btn.onclick = function() { notes.splice(i, 1); save(); render(); };
      var jump = document.createElement("button");
      jump.textContent = "Jump to text";
      jump.onclick = function() {
        var mark = document.getElementById("note-mark-" + i);
        if (mark) mark.scrollIntoView({behavior: "smooth", block: "center"});
      };
      var quote = document.createElement("blockquote");
      quote.textContent = n.text;
      var body = document.createElement("div");
      body.textContent = n.note;
      div.appendChild(btn);
      div.appendChild(jump);
      div.appendChild(quote);
      div.appendChild(body);
      list.appendChild(div);
    });
    highlightAll();
  }

  function save() { localStorage.setItem(key, JSON.stringify(notes)); }

  function unwrapMarks() {
    var marks = lessonBody.querySelectorAll("mark.noted");
    for (var i = 0; i < marks.length; i++) {
      var m = marks[i], parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
      parent.normalize();
    }
  }

  function locate(nodes, offset) {
    for (var j = 0; j < nodes.length; j++) {
      var len = nodes[j].node.nodeValue.length;
      if (offset <= nodes[j].start + len) return {node: nodes[j].node, offset: offset - nodes[j].start};
    }
    return null;
  }

  function highlightAll() {
    unwrapMarks();
    notes.forEach(function(n, i) {
      var walker = document.createTreeWalker(lessonBody, NodeFilter.SHOW_TEXT);
      var nodes = [], text = "", node;
      while (node = walker.nextNode()) {
        nodes.push({node: node, start: text.length});
        text += node.nodeValue;
      }
      var idx = text.indexOf(n.text);
      if (idx === -1) return;
      var start = locate(nodes, idx), end = locate(nodes, idx + n.text.length);
      if (!start || !end) return;
      var range = document.createRange();
      range.setStart(start.node, start.offset);
      range.setEnd(end.node, end.offset);
      var mark = document.createElement("mark");
      mark.className = "noted";
      mark.id = "note-mark-" + i;
      mark.title = n.note;
      mark.onclick = function() { editNote(i); };
      try { range.surroundContents(mark); } catch (e) {}
    });
  }

  function editNote(i) {
    var val = prompt("Edit note (blank to remove):", notes[i].note);
    if (val === null) return;
    if (val.trim()) { notes[i].note = val; } else { notes.splice(i, 1); }
    save();
    render();
  }

  document.addEventListener("mouseup", function(e) {
    var sel = window.getSelection();
    var text = sel.toString().trim();
    if (!text || !lessonBody.contains(sel.anchorNode)) {
      noteBtn.style.display = "none";
      return;
    }
    var range = sel.getRangeAt(0).getBoundingClientRect();
    noteBtn.style.left = (window.scrollX + range.left) + "px";
    noteBtn.style.top = (window.scrollY + range.bottom + 6) + "px";
    noteBtn.style.display = "block";
    noteBtn.onclick = function() {
      var note = prompt("Note for: \\u201c" + text.slice(0, 80) + "\\u201d");
      noteBtn.style.display = "none";
      if (note) {
        notes.push({text: text, note: note});
        save();
        render();
      }
    };
  });

  render();
})();
</script>
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


FOOTER = """
<footer class="meta" style="border-top:1px solid rgba(127,127,127,.3);margin-top:3rem;padding-top:1rem">
<span id="home-link"></span>Powered by <a href="https://github.com/svandragt/lessons-ai">lessons</a>.
<script>
var p = location.hostname.split(".");
if (p.length > 2) {
  var d = p.slice(1).join(".");
  document.getElementById("home-link").innerHTML =
    'Part of <a href="https://' + d + '">' + d + "</a> · ";
}
</script>
</footer>
"""


def page(title, body):
    return (f'<!doctype html><meta charset="utf-8">'
            f"<title>{title}</title>{STYLE}{body}{FOOTER}").encode()


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
    notes_html = ('<button id="note-btn">+ Note</button>'
                  '<div class="notes"><h2>My notes</h2><div id="notes-list"></div></div>'
                  + NOTES_SCRIPT % lesson["slug"])
    return page(lesson["title"], head + f'<div id="lesson-body">{html}</div>' + rel_html + notes_html)


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
        # -rltz not -a: the dest root is owned by another user, so preserving
        # perms/owner/group/dir-times on it fails with EPERM. --chmod=F644 still
        # forces readable files; new dirs take the remote umask.
        r = subprocess.run(["rsync", "-rltz", "--omit-dir-times", "--delete",
                            "--chmod=F644", f"{tmp}/", dest],
                           capture_output=True, text=True)
        if r.returncode:
            return f"deploy failed (rsync {r.returncode}): {r.stderr.strip()}"
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
