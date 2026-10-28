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
- `llms.txt` lists every page (one line each) for agents: `check` keeps it complete, its sections
  follow the sidebar's, the 'Moved to' stubs sit under its last heading.
- The page shape (no first-level heading, an opening paragraph, tables of at most 4 columns and
  100 characters per cell, no pasted --help, at most 3 alerts, a closing `## Next` section) is
  checked by `check` as warnings; `check --strict` makes them errors.
- The README's shared block (between `<!-- readme:begin -->` and `<!-- readme:end -->`) is
  generated from the same block of Home.md by `readme`; `check` fails when it is out of date.

    python3 doc/wiki_sync.py check                      # sources are consistent (CI)
    python3 doc/wiki_sync.py preview --serve             # the wiki as HTML in your browser (pip install markdown)
    python3 doc/wiki_sync.py preview --ref origin/wiki/welcome --serve   # a branch, without checking it out
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

# The one line "Moved to [...](Page.md)." pages: kept for the links from outside, never in the sidebar.
STUBS = {"Document-a-SoC", "Firmware", "OS-support", "Related-Projects", "Soft-CPU",
         "Reuse-a-(System)Verilog,-VHDL,-Amaranth,-Spinal-HDL,-Chisel-core",
         "Reuse-a-SystemVerilog-VHDL-Amaranth-Spinal-HDL-Chisel-core",
         "Use-Host-Bridge-to-control-debug-a-SoC", "JTAG-GDB-Debugging-with-VexRiscv-CPU",
         "JTAG-GDB-Debugging-with-VexRiscv-SMP-NaxRiscv-VexiiRiscv-CPUs", "Create-And-Load-Software-To-The-CPU",
         "Load-Application-Code-To-CPU", "Generate-Renode-simulation",
         "Create-A-complex-SoC-With-Cores-From-The-Ecosystem", "Export-Your-Core-SoC-To-Verilog",
         "Run-MicroPython-CircuitPython-On-Your-SoC", "FPGA-and-SPI-Flash-programmers"}
OPTIONAL_NEXT = {"Home", "LiteX-for-AI-Agents", "LiteX-for-Hardware-Engineers-2018"}   # No closing "## Next".
UNLISTED      = {"LiteX-for-Hardware-Engineers-2018"}   # Content pages allowed out of _Sidebar.md (archives).
ALERTS        = {"NOTE", "TIP", "WARNING"}
README        = os.path.normpath(os.path.join(ROOT, "..", "..", "README.md"))
README_BEGIN, README_END = "<!-- readme:begin -->", "<!-- readme:end -->"

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

def strip_fences(text):
    """Markdown text without the fenced code blocks; inline code kept, its characters masked."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", lambda m: "x"*len(m.group(0)), text)

def fences(text):
    """The fenced code blocks of a markdown text, as lists of lines (fences excluded)."""
    return [m.group(1).split("\n") for m in re.finditer(r"```[^\n]*\n(.*?)```", text, flags=re.S)]

def stub_target(text):
    """The page a 'Moved to [...](Page.md).' stub points to."""
    m = re.match(r"Moved to \[[^\]]*\]\(([^)#\s]+)", text.strip())
    return os.path.splitext(m.group(1))[0] if m else None

def check_style(n, text, report, err):
    """The page shape: no first-level heading, an opening paragraph, narrow tables, no pasted --help,
    a few alerts, a closing ## Next section. report() is warn or err (check --strict)."""
    body = strip_code(text)
    if re.search(r"^# ", body, flags=re.M) or re.search(r"^=+\s*$", body, flags=re.M):
        report(f"{n}: first-level heading in the page (the wiki shows the page name as its title, use ##)")
    first, count = None, 0
    for l in body.split("\n"):
        t = l.strip()
        if t.startswith("#"):
            break
        if not t or t.startswith(("<p", "</p", "<img", "![", "[![", "<!--", "<div", "</div")):
            continue
        if first is None:
            first = t
        count += 1
    if first is None or first.startswith(("|", ">", "```", "~~~", "- ", "* ")):
        report(f"{n}: no opening paragraph before the first heading (start with what the reader gets)")
    elif count < 2:
        report(f"{n}: the opening is one line, say what the reader gets in two or three")
    if n not in OPTIONAL_NEXT:
        h2 = re.findall(r"^## +(.+?)\s*$", body, flags=re.M)
        if not h2 or h2[-1] != "Next":
            report(f"{n}: the last section is not '## Next' (3-5 links on where to go)")
        elif len(re.findall(r"^- \[[^\]]+\]\([A-Za-z0-9][^)\s]*\.md", body[body.rfind("## Next"):], flags=re.M)) < 2:
            report(f"{n}: '## Next' needs at least two '- [Page](Page.md): why' bullets")
    wide, long = [], []
    for l in strip_fences(text).split("\n"):
        if not l.startswith("|"):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
            continue
        if len(cells) > 4:
            wide.append(len(cells))
        # The length a reader sees: links keep their text, images and badges take no room.
        shown = [re.sub(r"<img\b[^>]*>", "", re.sub(r"!\[[^\]]*\]\([^)]*\)", "", c)) for c in cells]
        shown = [re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", c) for c in shown]
        if max(len(c) for c in shown) > 100:
            long.append(max(len(c) for c in shown))
    if wide:
        report(f"{n}: {len(wide)} table row(s) with more than 4 columns (up to {max(wide)})")
    if long:
        report(f"{n}: {len(long)} table cell(s) longer than 100 characters (up to {max(long)}): split the table or move the details below it")
    for block in fences(text):
        if len(block) > 60:
            report(f"{n}: a code block of {len(block)} lines (60 at most: show what matters)")
        elif len(block) > 12 and re.search(r"^(usage:|options:|optional arguments:)", "\n".join(block), flags=re.M | re.I):
            report(f"{n}: pasted --help output ({len(block)} lines): show the options the reader needs")
    kinds = re.findall(r"^> \[!(\w+)\]", body, flags=re.M)
    for k in kinds:
        if k not in ALERTS:
            report(f"{n}: alert [!{k}] (NOTE, TIP or WARNING)")
    if len(kinds) > 3:
        report(f"{n}: {len(kinds)} alerts (3 at most)")
    for m in re.finditer(r"\b(FIXME|TODO|XXX)\b", body):
        err(f"{n}: {m.group(1)} left in the page text")

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

def check(external=False, strict=False):
    files = list_files()
    pgs   = pages(files)
    errors, warnings = [], []
    err  = errors.append
    warn = warnings.append
    report = err if strict else warn   # The page shape checks.
    inbound = {}                       # page -> pages linking to it (the sidebar counts).

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
    sidebar   = texts.get("_Sidebar", "")

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
                    if target != n:
                        inbound.setdefault(target, set()).add(n)
                    if anchor and target in page_anchors and anchor not in page_anchors[target]:
                        err(f"{n}: anchor #{anchor} not found in {path}")
                elif kind == "image" and not path.startswith("images/"):
                    err(f"{n}: image {path} outside images/")
                continue
            if path in pgs:
                err(f"{n}: link ]({dest}) to a page without its extension, use ]({pgs[path]}{'#' + anchor if anchor else ''})")
            else:
                err(f"{n}: broken link/image ]({dest})")
        if not n.startswith("_") and n not in STUBS and n != "Home":
            check_style(n, text, report, err)

    # Stubs: one line pages, listed in STUBS, pointing to a real page, out of the sidebar.
    found = {n for n, f in pgs.items() if texts_is_stub(os.path.join(ROOT, f))}
    for n in sorted(found - STUBS):
        err(f"{n}: a 'Moved to' page not listed in STUBS (doc/wiki_sync.py)")
    for n in sorted(STUBS - found):
        err(f"{n}: listed in STUBS but not a one line 'Moved to' page")
    for n in sorted(found):
        t = stub_target(texts[n])
        if t in STUBS:
            err(f"{n}: points to another stub ({t}), point to the final page")
        if f"]({pgs[n]})" in sidebar:
            err(f"_Sidebar: {n} is a stub, remove it from the sidebar")
    # Every content page is in the sidebar (or UNLISTED) and reachable from another page.
    for n, f in pgs.items():
        if n.startswith("_") or n in STUBS:
            continue
        if n not in UNLISTED and f"]({f})" not in sidebar and f"]({f}#" not in sidebar:
            err(f"_Sidebar: page {n} is not in the sidebar (or add it to UNLISTED in doc/wiki_sync.py)")
        if n != "Home" and not (inbound.get(n, set()) - STUBS):
            warn(f"{n}: no page links to it")

    if "llms.txt" in files:
        llms = open(os.path.join(ROOT, "llms.txt"), encoding="utf-8").read()
        moved = llms.find("\n## Moved")
        for n in pgs:
            if n.startswith("_"):
                continue
            pos = llms.find(f"{WIKI_URL}/{n})")
            if pos < 0:
                err(f"llms.txt: page {n} not listed")
            elif n in STUBS and (moved < 0 or pos < moved):
                err(f"llms.txt: the stub {n} belongs under the '## Moved ...' heading")
            elif n not in STUBS and moved >= 0 and pos > moved:
                err(f"llms.txt: {n} is listed under '## Moved ...' but is not a stub")
        sections = re.findall(r"^\* ([^\[\n]+?)\s*$", sidebar, flags=re.M)
        heads = [h for h in re.findall(r"^## +(.+?)\s*$", llms, flags=re.M) if not h.startswith("Moved")]
        if sections and heads != sections:
            err(f"llms.txt: its sections {heads} must follow the sidebar's {sections}")

    known = set(pgs)
    if readme_block(known) is not None and not readme(write=False):
        err(f"README.md: its shared block differs from Home.md's, run: python3 {os.path.basename(__file__)} readme")

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

def rewrite_links(text, known, absolute_images=False, ext="", prefix=""):
    """Wiki form of a page: `](Page.md#a)` -> `](Page#a)` for the known pages (`](Page.html#a)` with
    ext=".html", `](<prefix>Page#a)` with a prefix such as the wiki URL)."""
    exts = "|".join(e[1:] for e in PAGE_EXTS)
    def sub(m):
        name = m.group(2)
        if name in known:
            return f"{m.group(1)}{prefix}{name}{ext}{m.group(4) or ''}{m.group(5)}"
        return m.group(0)
    text = re.sub(r"(\]\()([A-Za-z0-9][A-Za-z0-9._-]*)\.(" + exts + r")(#[^)\s]*)?(\))", sub, text)
    def sub_ref(m):
        name = m.group(2)
        return f"{m.group(1)}{prefix}{name}{ext}{m.group(4) or ''}" if name in known else m.group(0)
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

def readme_block(known):
    """The README's shared block, generated from the marked block of Home.md (None without markers):
    the page links become absolute wiki URLs, the images point into doc/wiki/images/."""
    home = open(os.path.join(ROOT, "Home.md"), encoding="utf-8").read()
    if README_BEGIN not in home or README_END not in home:
        return None
    block = home.split(README_BEGIN, 1)[1].split(README_END, 1)[0]
    block = rewrite_links(block, known, prefix=WIKI_URL + "/").replace(f"]({WIKI_URL}/Home)", f"]({WIKI_URL})")
    return re.sub(r"(\]\(|src=\")images/", r"\1doc/wiki/images/", block)

def readme(write=True):
    """Rewrite the README's shared block from Home.md; returns True when the README was already up to date."""
    block = readme_block(set(pages()))
    if block is None:
        raise SystemExit(f"Home.md has no {README_BEGIN} / {README_END} markers")
    text = open(README, encoding="utf-8").read()
    if README_BEGIN not in text or README_END not in text:
        raise SystemExit(f"{README} has no {README_BEGIN} / {README_END} markers")
    head, rest = text.split(README_BEGIN, 1)
    tail = rest.split(README_END, 1)[1]
    new = head + README_BEGIN + block + README_END + tail
    if write:
        if new != text:
            open(README, "w", encoding="utf-8").write(new)
            print(f"{README}: shared block updated from Home.md")
        else:
            print(f"{README}: already up to date")
    return new == text

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
.markdown-body .highlight { background: #f6f8fa; border-radius: 6px; } .markdown-body .highlight pre { margin: 0; }
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
<title>{title} · LiteX wiki preview</title><style>{css}
{hl_css}</style></head>
<body><div class="wrap">
<div class="main">
<div class="topbar">LiteX wiki preview ({source}) · <a href="Home.html">Home</a>{name}</div>
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
    md = markdown.Markdown(extensions=["extra", "toc", "sane_lists", "codehilite"],
                           extension_configs={"toc": {"slugify": gfm_slugify},
                                              "codehilite": {"guess_lang": False, "css_class": "highlight"}})
    return md.convert(text)

def highlight_css():
    """The style of the code blocks (Pygments, GitHub-like colors); empty without Pygments."""
    try:
        from pygments.formatters import HtmlFormatter
    except ImportError:
        return ""
    return HtmlFormatter(style="default").get_style_defs(".highlight")

def wiki_at_ref(ref):
    """doc/wiki/ of a git ref (a branch, a tag, a commit: origin/wiki/welcome, v2026.08, ...) extracted
    to a temporary directory, so a branch can be previewed without checking it out. The ref is looked
    up in the repository of the current directory, then in the one holding this script."""
    import io, subprocess, tarfile
    here  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    error = "git not found"
    for repo in dict.fromkeys([os.getcwd(), here]):
        try:
            data = subprocess.run(["git", "-C", repo, "archive", "--format=tar", ref, "doc/wiki"],
                                  capture_output=True, check=True).stdout
            break
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError as e:
            error = e.stderr.decode(errors="replace").strip()
    else:
        sys.exit(f"preview --ref {ref}: {error}")
    tmp = tempfile.mkdtemp(prefix="litex-wiki-")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        try:
            tar.extractall(tmp, filter="data")
        except TypeError:                               # Python < 3.12
            tar.extractall(tmp)
    return os.path.join(tmp, "doc", "wiki")

def preview(out, serve=False, port=8000, browser=True, ref=None):
    """Render doc/wiki/ (or the one of a git ref) to HTML pages with the sidebar and footer, like the
    GitHub wiki, and serve them."""
    import html
    root  = wiki_at_ref(ref) if ref else ROOT
    files = list_files(root)
    pgs   = pages(files)
    known = set(pgs)
    os.makedirs(out, exist_ok=True)
    def read(name):
        return open(os.path.join(root, name), encoding="utf-8").read()
    hl_css  = highlight_css()
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
        page = PREVIEW_TEMPLATE.format(title=html.escape(name.replace("-", " ")),
                                       name=("" if name == "Home" else " · " + html.escape(name)),
                                       source=html.escape(ref or "doc/wiki"),
                                       css=PREVIEW_CSS, hl_css=hl_css, body=body, footer=footer, sidebar=sidebar)
        with open(os.path.join(out, name + ".html"), "w", encoding="utf-8") as fo:
            fo.write(page)
        n += 1
    for f in files:
        if "/" in f or not f.endswith(PAGE_EXTS):      # images/, llms.txt, ...
            dst = os.path.join(out, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(root, f), dst)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fo:
        fo.write('<!doctype html><meta http-equiv="refresh" content="0; url=Home.html">')
    print(f"{n} pages of {ref or 'doc/wiki'} rendered to {out} (open {os.path.join(out, 'Home.html')})")
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
    parser = argparse.ArgumentParser(description="LiteX wiki sources: check, preview, render, diff, readme.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="Check the sources (links, images, names, llms.txt).")
    p.add_argument("--external", action="store_true", help="Also HEAD-request the external links and images (slow, not in CI).")
    p.add_argument("--strict", action="store_true", help="The page shape warnings (opening, tables, Next...) become errors.")
    sub.add_parser("readme", help="Regenerate the README's shared block from Home.md.")
    p = sub.add_parser("preview", help="Render the pages to HTML (sidebar, footer) and open them in the browser.")
    p.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "litex-wiki-preview"), help="Output directory.")
    p.add_argument("--serve", action="store_true", help="Serve the directory on localhost and open the browser.")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true", help="With --serve: do not open the browser.")
    p.add_argument("--ref", help="Preview doc/wiki of this git ref (origin/wiki/welcome, a tag, a commit) instead of the checkout.")
    p = sub.add_parser("render", help="Write the wiki tree (links rewritten) to a directory.")
    p.add_argument("--out", required=True)
    p.add_argument("--clean", action="store_true", help="Remove files of --out that are not in the sources (keeps .git).")
    p.add_argument("--absolute-images", action="store_true", help="Point images to raw.githubusercontent.com/wiki/...")
    p = sub.add_parser("diff", help="Show what a sync would change in a wiki clone.")
    p.add_argument("--wiki", required=True, help="Clone of https://github.com/enjoy-digital/litex.wiki.git")
    args = parser.parse_args()
    if args.cmd == "check":
        sys.exit(0 if check(args.external, args.strict) else 1)
    if args.cmd == "readme":
        readme()
    if args.cmd == "preview":
        preview(args.out, args.serve, args.port, browser=not args.no_browser, ref=args.ref)
    if args.cmd == "render":
        render(args.out, args.clean, args.absolute_images)
    if args.cmd == "diff":
        diff(args.wiki)

if __name__ == "__main__":
    main()
