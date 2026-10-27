#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""LiteX wiki sources (doc/wiki/): check, render and publish.

The GitHub wiki (https://github.com/enjoy-digital/litex/wiki) is generated from doc/wiki/: the
pages are edited here, reviewed as pull requests and pushed to the wiki repository by the
.github/workflows/wiki.yml workflow on every push to master. Direct edits on the wiki are
overwritten by the next sync.

Conventions (pages render both in the repository view and on the wiki):
- One page per file, `Page-Name.md` (`-` is shown as a space, the name is the URL:
  /wiki/Page-Name); `Home.md` is the landing page, `_Sidebar.md`/`_Footer.md` the wiki's
  special pages. ASCII names only, no `README.md` (it would become a page).
- Internal links are written with the extension: `[Text](Page-Name.md)`,
  `[Text](Page-Name.md#anchor)`; `render` strips the extension for the wiki. No `[[Page]]`
  wiki-links, no absolute https://github.com/enjoy-digital/litex/wiki/... links.
- Pictures and screenshots stay hosted on GitHub (drag them into a GitHub issue or comment and
  link the user-images URL) or on their original site: no large binaries in the repository. Only
  the generated diagrams (small SVGs, see doc/diagrams/) live in `images/` and are referenced
  relatively (`images/x.svg`).
- Links to files of the repository use absolute https://github.com/enjoy-digital/litex/blob/master/...
  URLs (the wiki cannot resolve `../`).
- `llms.txt` lists every page (one line each) for agents: `check` keeps it complete.

    python3 doc/wiki_sync.py check                      # sources are consistent (CI)
    python3 doc/wiki_sync.py preview --serve             # the wiki as HTML in your browser (pip install markdown)
    python3 doc/wiki_sync.py render --out DIR [--clean]  # wiki tree, links rewritten
    python3 doc/wiki_sync.py diff --wiki CLONE           # what a sync would change
"""

import argparse
import functools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser

ROOT      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki")
WIKI_URL  = "https://github.com/enjoy-digital/litex/wiki"
RAW_URL   = "https://raw.githubusercontent.com/wiki/enjoy-digital/litex"
PAGE_EXTS = (".md", ".asciidoc")
NAME_RE   = re.compile(r"^[A-Za-z0-9._()+,-]+$")   # ASCII only; ( ) , are legacy (they break markdown links).
SIZE_FAIL = 300*1024   # No large binaries in the repository: host pictures on GitHub issues.
SIZE_WARN = 100*1024

# Sources -------------------------------------------------------------------------------------------

def list_files(root=ROOT):
    """Every file under root, as relative POSIX paths."""
    out = []
    for d, _, fs in os.walk(root):
        for f in fs:
            out.append(os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/"))
    return sorted(out)

def pages(files=None):
    """Page name -> file name, for the top level pages."""
    files = list_files() if files is None else files
    return {os.path.splitext(f)[0]: f for f in files if "/" not in f and f.endswith(PAGE_EXTS)}

def texts_is_stub(path):
    """A one line 'Moved to ...' page."""
    try:
        text = open(path, encoding="utf-8").read().strip()
    except (UnicodeDecodeError, OSError):
        return False
    return text.startswith("Moved to ") and "\n" not in text

def strip_code(text):
    """Markdown text without fenced code blocks and inline code (links there are not links)."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)

def anchors(text):
    """GitHub's anchors for the headings of a markdown text."""
    seen, out = {}, set()
    for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", strip_code(text), flags=re.M):
        h = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1))   # link text only
        h = re.sub(r"<[^>]+>", "", h)                                # no html
        a = re.sub(r"[^\w\- ]", "", h.strip().lower()).replace(" ", "-")
        if a in seen:
            seen[a] += 1
            a = f"{a}-{seen[a]}"
        else:
            seen[a] = 0
        out.add(a)
    return out

LINK_RE  = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_IMG_RE = re.compile(r"<img\b[^>]*\bsrc=\"([^\"]+)\"")
HTML_A_RE   = re.compile(r"<a\b[^>]*\bhref=\"([^\"]+)\"")
REF_RE   = re.compile(r"^\[[^\]]+\]:\s*(\S+)", flags=re.M)

def check(external=False):
    files = list_files()
    pgs   = pages(files)
    errors, warnings = [], []
    err  = errors.append
    warn = warnings.append

    for required in ("Home.md", "_Sidebar.md", "_Footer.md", "llms.txt"):
        if required not in files:
            err(f"missing {required}")
    for f in files:
        base = os.path.basename(f)
        if any(not NAME_RE.match(p) for p in f.split("/")):
            err(f"{f}: non-ASCII or unsafe file name (allowed: [A-Za-z0-9._-])")
        elif re.search(r"[(),+]", f) and not texts_is_stub(os.path.join(ROOT, f)):
            warn(f"{f}: ( ) , + in a page name break markdown links, use - (keep a 'Moved to' stub)")
        if base.lower() == "readme.md":
            err(f"{f}: a README.md would become a wiki page, use Contributing-to-the-Wiki.md")
        if "/" in f and f.endswith(PAGE_EXTS):
            err(f"{f}: pages must stay at the top level (any .md in the tree becomes a page)")
        size = os.path.getsize(os.path.join(ROOT, f))
        if size > SIZE_FAIL:
            err(f"{f}: {size//1024} KB, larger than {SIZE_FAIL//1024} KB: host pictures on a GitHub issue, not in the repository")
        elif size > SIZE_WARN:
            warn(f"{f}: {size//1024} KB (limit {SIZE_FAIL//1024} KB)")

    texts = {n: open(os.path.join(ROOT, f), encoding="utf-8").read() for n, f in pgs.items()}
    page_anchors = {n: anchors(t) for n, t in texts.items() if pgs[n].endswith(".md")}
    externals = set()

    for n, text in texts.items():
        if not pgs[n].endswith(".md"):
            continue
        body = strip_code(text)
        if "[[" in body and "]]" in body:
            err(f"{n}: [[wiki-link]] found, use [Text](Page.md)")
        if WIKI_URL in body:
            err(f"{n}: absolute wiki URL found, use a relative [Text](Page.md) link")
        for m in re.finditer(r"\]\(\.\.?/", body):
            err(f"{n}: relative path with ./ or ../ (the wiki cannot resolve it)")
        dests  = [(d, "link")  for d in LINK_RE.findall(body)]
        dests += [(d, "image") for d in IMAGE_RE.findall(body)]
        dests += [(d, "image") for d in HTML_IMG_RE.findall(body)]
        dests += [(d, "link")  for d in HTML_A_RE.findall(body)]
        dests += [(d, "link")  for d in REF_RE.findall(body)]
        for dest, kind in dests:
            if dest.startswith(("http://", "https://", "mailto:", "irc://")):
                externals.add(dest)
                continue
            if dest.startswith("#"):
                if dest[1:] not in page_anchors.get(n, set()):
                    err(f"{n}: anchor {dest} not found in the page")
                continue
            path, _, anchor = dest.partition("#")
            if path in files:
                if path.endswith(PAGE_EXTS):
                    target = os.path.splitext(path)[0]
                    if anchor and target in page_anchors and anchor not in page_anchors[target]:
                        err(f"{n}: anchor #{anchor} not found in {path}")
                elif kind == "image" and not path.startswith("images/"):
                    err(f"{n}: image {path} outside images/")
                continue
            if path in pgs:
                err(f"{n}: link ]({dest}) to a page without its extension, use ]({pgs[path]}{'#' + anchor if anchor else ''})")
            else:
                err(f"{n}: broken link/image ]({dest})")

    if "llms.txt" in files:
        llms = open(os.path.join(ROOT, "llms.txt"), encoding="utf-8").read()
        for n in pgs:
            if n.startswith("_"):
                continue
            if f"{WIKI_URL}/{n}" not in llms:
                err(f"llms.txt: page {n} not listed")

    if external:
        for u in sorted(externals):
            try:
                req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0 litex-wiki-check"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    if r.status >= 400:
                        warn(f"external {u}: HTTP {r.status}")
            except Exception as e:
                warn(f"external {u}: {e}")

    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("error:", e)
    print(f"{len(pgs)} pages, {len(files)} files, {len(errors)} error(s), {len(warnings)} warning(s)")
    return len(errors) == 0

# Render --------------------------------------------------------------------------------------------

def rewrite_links(text, known, absolute_images=False, ext=""):
    """Wiki form of a page: `](Page.md#a)` -> `](Page#a)` for the known pages (`](Page.html#a)` with ext=".html")."""
    exts = "|".join(e[1:] for e in PAGE_EXTS)
    def sub(m):
        name = m.group(2)
        if name in known:
            return f"{m.group(1)}{name}{ext}{m.group(4) or ''}{m.group(5)}"
        return m.group(0)
    text = re.sub(r"(\]\()([A-Za-z0-9][A-Za-z0-9._-]*)\.(" + exts + r")(#[^)\s]*)?(\))", sub, text)
    def sub_ref(m):
        name = m.group(2)
        return f"{m.group(1)}{name}{ext}{m.group(4) or ''}" if name in known else m.group(0)
    text = re.sub(r"(^\[[^\]]+\]:\s*)([A-Za-z0-9][A-Za-z0-9._-]*)\.(" + exts + r")(#\S*)?$", sub_ref, text, flags=re.M)
    if absolute_images:
        text = re.sub(r"(\]\(|src=\")images/", r"\1" + RAW_URL + "/images/", text)
    return text

def render(out, clean=False, absolute_images=False):
    files = list_files()
    known = set(pages(files))
    os.makedirs(out, exist_ok=True)
    if clean:
        for f in list_files(out):
            if f.split("/")[0] != ".git" and f not in files:
                os.remove(os.path.join(out, f))
                print("removed", f)
        for d, dirs, fs in os.walk(out, topdown=False):
            if ".git" not in d and not dirs and not fs and d != out:
                os.rmdir(d)
    for f in files:
        src, dst = os.path.join(ROOT, f), os.path.join(out, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if f.endswith(".md"):
            text = open(src, encoding="utf-8").read()
            with open(dst, "w", encoding="utf-8") as fo:
                fo.write(rewrite_links(text, known, absolute_images))
        else:
            shutil.copyfile(src, dst)
    print(f"rendered {len(files)} files to {out}")

def diff(wiki):
    """git diff --stat between a wiki clone (without its .git) and the rendered sources."""
    with tempfile.TemporaryDirectory() as tmp:
        current, rendered = os.path.join(tmp, "wiki"), os.path.join(tmp, "render")
        shutil.copytree(wiki, current, ignore=shutil.ignore_patterns(".git"))
        render(rendered)
        r = subprocess.run(["git", "-C", tmp, "diff", "--no-index", "--stat=100", "--", "wiki", "render"],
                           capture_output=True, text=True)
        print(r.stdout)


# Preview -------------------------------------------------------------------------------------------

PREVIEW_CSS = """
body { margin: 0; font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #1f2328; background: #ffffff; }
.wrap { max-width: 1280px; margin: 0 auto; padding: 16px 24px; display: flex; gap: 32px; align-items: flex-start; }
.main { flex: 1; min-width: 0; }
.sidebar { width: 296px; flex: none; position: sticky; top: 16px; border: 1px solid #d0d7de; border-radius: 6px; padding: 8px 16px; font-size: 14px; background: #f6f8fa; }
.sidebar h2 { font-size: 16px; border: none; margin: 8px 0; }
.sidebar ul { padding-left: 18px; margin: 4px 0; }
.topbar { font-size: 13px; color: #57606a; border-bottom: 1px solid #d0d7de; padding-bottom: 8px; margin-bottom: 16px; }
.topbar a { color: #0969da; text-decoration: none; }
h1.pagetitle { font-size: 32px; font-weight: 600; margin: 0 0 16px; }
.markdown-body h1, .markdown-body h2 { padding-bottom: .3em; border-bottom: 1px solid #d0d7de; margin-top: 24px; }
.markdown-body h1 { font-size: 2em; } .markdown-body h2 { font-size: 1.5em; } .markdown-body h3 { font-size: 1.25em; }
.markdown-body a { color: #0969da; text-decoration: none; } .markdown-body a:hover { text-decoration: underline; }
.markdown-body img { max-width: 100%; box-sizing: border-box; }
.markdown-body pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; font-size: 85%; line-height: 1.45; }
.markdown-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 85%; background: rgba(175,184,193,.2); padding: .2em .4em; border-radius: 6px; }
.markdown-body pre code { background: none; padding: 0; font-size: 100%; }
.markdown-body table { border-collapse: collapse; margin: 16px 0; display: block; overflow: auto; max-width: 100%; }
.markdown-body th, .markdown-body td { border: 1px solid #d0d7de; padding: 6px 13px; vertical-align: top; }
.markdown-body th { font-weight: 600; background: #f6f8fa; }
.markdown-body tr:nth-child(2n) { background: #f6f8fa; }
.markdown-body blockquote { margin: 0; padding: 0 1em; color: #57606a; border-left: .25em solid #d0d7de; }
.markdown-body hr { border: 0; border-top: 1px solid #d0d7de; margin: 24px 0; }
.footer { border-top: 1px solid #d0d7de; margin-top: 32px; padding-top: 16px; font-size: 14px; color: #57606a; }
"""

PREVIEW_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · LiteX wiki preview</title><style>{css}</style></head>
<body><div class="wrap">
<div class="main">
<div class="topbar">LiteX wiki preview (local, from doc/wiki) · <a href="Home.html">Home</a> · {name}</div>
<h1 class="pagetitle">{title}</h1>
<div class="markdown-body">{body}</div>
<div class="footer markdown-body">{footer}</div>
</div>
<div class="sidebar markdown-body">{sidebar}</div>
</div></body></html>
"""

EMOJI = {":heavy_check_mark:": "✔️", ":wink:": "\U0001F609", ":smile:": "\U0001F604", ":warning:": "⚠️",
         ":bulb:": "\U0001F4A1", ":rocket:": "\U0001F680", ":tada:": "\U0001F389", ":information_source:": "ℹ️",
         ":heavy_exclamation_mark:": "❗", ":fire:": "\U0001F525", ":fr:": "\U0001F1EB\U0001F1F7", ":+1:": "\U0001F44D"}

def gfm_slugify(value, separator="-"):
    """GitHub's heading anchors (the same rule as anchors())."""
    return re.sub(r"[^\w\- ]", "", value.strip().lower()).replace(" ", separator)

LIST_ITEM = re.compile(r"^ {0,3}([-*+]|\d+[.)]) ")

def gfm_lists(text):
    """GitHub lets a list interrupt a paragraph, Python-Markdown wants a blank line before it:
    insert one when a list item follows a plain text line (outside the fenced code blocks)."""
    out, fence, prev = [], False, ""
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and LIST_ITEM.match(line) and prev.strip() and not LIST_ITEM.match(prev) \
                and not prev.startswith((" ", "\t")):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)

def render_markdown(text, known):
    """A page as HTML, with the links pointing to the .html pages (needs Python-Markdown)."""
    try:
        import markdown
    except ImportError:
        sys.exit("preview needs Python-Markdown: pip install markdown")
    text = rewrite_links(text, known, ext=".html")
    for k, v in EMOJI.items():
        text = text.replace(k, v)
    text = gfm_lists(text)
    md = markdown.Markdown(extensions=["extra", "toc", "sane_lists"],
                           extension_configs={"toc": {"slugify": gfm_slugify}})
    return md.convert(text)

def preview(out, serve=False, port=8000, browser=True):
    """Render doc/wiki/ to HTML pages with the sidebar and footer, like the GitHub wiki, and serve them."""
    import html
    files = list_files()
    pgs   = pages(files)
    known = set(pgs)
    os.makedirs(out, exist_ok=True)
    def read(name):
        return open(os.path.join(ROOT, name), encoding="utf-8").read()
    sidebar = render_markdown(read("_Sidebar.md"), known) if "_Sidebar.md" in files else ""
    footer  = render_markdown(read("_Footer.md"),  known) if "_Footer.md"  in files else ""
    n = 0
    for name, f in sorted(pgs.items()):
        if name.startswith("_"):
            continue
        text = read(f)
        if f.endswith(".md"):
            body = render_markdown(text, known)
        else:
            body = "<p><em>This page is not markdown; shown as source.</em></p><pre>" + html.escape(text) + "</pre>"
        page = PREVIEW_TEMPLATE.format(title=html.escape(name.replace("-", " ")), name=html.escape(name),
                                       css=PREVIEW_CSS, body=body, footer=footer, sidebar=sidebar)
        with open(os.path.join(out, name + ".html"), "w", encoding="utf-8") as fo:
            fo.write(page)
        n += 1
    for f in files:
        if "/" in f or not f.endswith(PAGE_EXTS):      # images/, llms.txt, ...
            dst = os.path.join(out, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(ROOT, f), dst)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fo:
        fo.write('<!doctype html><meta http-equiv="refresh" content="0; url=Home.html">')
    print(f"{n} pages rendered to {out} (open {os.path.join(out, 'Home.html')})")
    if serve:
        import http.server
        url = f"http://127.0.0.1:{port}/Home.html"
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=out)
        with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
            print(f"serving {url} (Ctrl-C to stop)")
            if browser:
                webbrowser.open(url)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass

# Main ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX wiki sources: check, render, diff.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="Check the sources (links, images, names, llms.txt).")
    p.add_argument("--external", action="store_true", help="Also HEAD-request the external links and images (slow, not in CI).")
    p = sub.add_parser("preview", help="Render the pages to HTML (sidebar, footer) and open them in the browser.")
    p.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "litex-wiki-preview"), help="Output directory.")
    p.add_argument("--serve", action="store_true", help="Serve the directory on localhost and open the browser.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true", help="With --serve: do not open the browser.")
    p = sub.add_parser("render", help="Write the wiki tree (links rewritten) to a directory.")
    p.add_argument("--out", required=True)
    p.add_argument("--clean", action="store_true", help="Remove files of --out that are not in the sources (keeps .git).")
    p.add_argument("--absolute-images", action="store_true", help="Point images to raw.githubusercontent.com/wiki/...")
    p = sub.add_parser("diff", help="Show what a sync would change in a wiki clone.")
    p.add_argument("--wiki", required=True, help="Clone of https://github.com/enjoy-digital/litex.wiki.git")
    args = parser.parse_args()
    if args.cmd == "check":
        sys.exit(0 if check(args.external) else 1)
    if args.cmd == "preview":
        preview(args.out, args.serve, args.port, browser=not args.no_browser)
    if args.cmd == "render":
        render(args.out, args.clean, args.absolute_images)
    if args.cmd == "diff":
        diff(args.wiki)

if __name__ == "__main__":
    main()
