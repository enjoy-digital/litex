This wiki is generated from the [`doc/wiki/`](https://github.com/enjoy-digital/litex/tree/master/doc/wiki)
directory of the LiteX repository: the pages are edited there, reviewed as pull requests and
published to the wiki by a GitHub Actions workflow on every push to `master`. Editing the wiki
directly is restricted to collaborators, and such edits are overwritten by the next sync, so
**please send your changes as pull requests** on https://github.com/enjoy-digital/litex.

Typos, outdated commands, a missing board or project, a better explanation: all welcome, even a
one line change. Open an issue if you are not sure where something belongs.

## Editing a page

- One page per file, `Page-Name.md` in `doc/wiki/`; the file name is the page URL
  (`/wiki/Page-Name`, `-` displayed as a space). Keep the existing names: they are linked from
  many places. If a page moves, leave a one line `Moved to [...](New-Page.md).` stub under the
  old name.
- Links to other pages are written with the extension: `[Installation](Installation.md)`,
  `[UARTBone](Host-Bridges.md#add-a-uartbone-bridge-to-your-soc)`.
  They work in the repository view and are rewritten for the wiki. No `[[Page]]` wiki-links,
  no absolute `https://github.com/enjoy-digital/litex/wiki/...` links.
- Links to files of the repository use the full URL
  (`https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md`).
- New pages go to `_Sidebar.md` (the navigation) and `llms.txt` (the index for AI agents, one
  line per page).
- A page starts with a short paragraph saying what the reader gets and ends with a `## Next`
  section; no `#` heading inside a page (the wiki shows the page name as the title). The shape
  and the voice are described below; `check` warns when a page drifts from them.
- Check that every command shown works with the current LiteX, and show its real output.

## Writing a page

Every page has the same shape, so a reader always knows where to look:

| Part | What it holds |
| --- | --- |
| Opening (no heading) | Two to four lines: what you will have or understand at the end, who it is for. |
| Visual | The diagram of a concept page, or the terminal capture of the first result, with a caption. |
| Try it | One to three commands and their real output (15 lines at most), then what you are looking at. |
| Body | Numbered steps ending with a visible result, or a few named sections; code before explanations. |
| Tables | Four columns at most, cells of a line, one sentence before the table saying how to read it. |
| `## Next` | Three to five `- [Page](Page.md): why you go there.` bullets, the natural continuation first. |

Longer lists go in a `<details>` block (as bullets or code, so that the cells stay short) or
on a reference page.

Alerts are for shortcuts and caveats, three per page at most: `> [!TIP]` for a shortcut,
`> [!NOTE]` for a caveat, `> [!WARNING]` when hardware or data is at risk.

> [!TIP]
> `python3 doc/wiki_sync.py check --strict` tells you when a page drifts from this shape; CI
> runs it on every pull request.

<details>
<summary>The three kinds of pages</summary>

- **How-to** (the numbered path, *Build your SoC*, *Run software on it*): the opening gives the
  result and the time it takes, step 1 is the first command, `Next` points to the following step
  and to the concept page behind it.
- **Concept** (*How LiteX works*): the opening says what it is in one sentence and where you meet
  it, the diagram comes first, then one "see it" command and the named sections.
- **Reference**: the opening says what is listed and the command that prints the live list; one
  section per group, a short table and a `<details>` block for the rest.

</details>

## The voice

LiteX is written by engineers for engineers who want to build something today, and the pages
sound like it:

- Open with what the reader gets, not with what the thing is made of.
- "We" for what LiteX and its developers decide, "you" for what the reader does; never "the user".
- One idea per sentence. The command first, the explanation second, the result third.
- Mark the moment after a result ("Et voilà!"), never before a command, and once per page.
- No marketing, no metaphors; "about forty cores" beats "various cores".
- Say how to read a table before the table. Show the five lines of output that matter, never a
  pasted `--help`.
- Humor is welcome where it fits, as in the first pages of this wiki, and never at the reader's
  expense.

## Pictures and screenshots

No large binaries in the LiteX repository: pictures and screenshots are hosted on GitHub. Drag
the image into a GitHub issue or pull request comment, copy the `https://github.com/user-attachments/...`
or `https://user-images.githubusercontent.com/...` URL GitHub generates and use it in the page
(`![alt text](URL)` or `<img src="URL" width="600">`). Images already hosted by a project you
link to (a README picture) can be referenced from their repository (`raw.githubusercontent.com`).

## Diagrams

The diagrams are generated in the LiteX style (chamfered grey boxes, grey arrows) by small
Python scripts in [`doc/diagrams/`](https://github.com/enjoy-digital/litex/tree/master/doc/diagrams):
one script per diagram, the SVG committed in `doc/wiki/images/` and embedded with
`![alt text](images/name.svg)`. See the [README](https://github.com/enjoy-digital/litex/blob/master/doc/diagrams/README.md)
there for the conventions, the lint and how to add one. Terminal captures (the text of a session in
`doc/diagrams/captures/`, drawn by `terminal.py`) and timing diagrams (`wave.py`) are generated the
same way, so they stay diffable and reviewable.

## Previewing the wiki locally

```sh
pip install markdown pygments             # once (Python-Markdown; Pygments for the syntax highlighting)
python3 doc/wiki_sync.py preview --serve  # renders doc/wiki/ to HTML and opens it in the browser
```

`preview` renders every page with the sidebar and the footer, like the GitHub wiki, and serves
them on `http://127.0.0.1:8000/` (`--port` to change it, `--no-browser` to only serve,
`--out DIR` to only write the HTML files). Re-run it after editing a page and reload the browser.
To review a pull request without touching your checkout, preview its branch directly:

```sh
git fetch origin
python3 doc/wiki_sync.py preview --ref origin/wiki/welcome --serve   # any branch, tag or commit
```

The rendering is close to GitHub's (same heading anchors, tables, code blocks, task lists) but not
identical: emoji shortcodes are limited to the common ones and GitHub alerts (`> [!NOTE]`) show as
plain quotes.

## Checking before a pull request

```sh
python3 doc/wiki_sync.py check --strict   # links, images, names, llms.txt, the page shape
python3 doc/diagrams/build.py --check     # diagrams match their scripts, labels fit
python3 doc/wiki_sync.py render --out /tmp/wiki   # the exact tree the sync pushes to the wiki
```

Without `--strict`, the page shape is reported as warnings instead of errors. The same checks
run in CI on the pull request, with `--strict`. After the merge, the `wiki` workflow pushes the
pages to the wiki (a few seconds); its log reports any direct wiki edit it overwrote.

## Next

- [Feedback, contribution, support](Feedback-Contribution-Support.md): the other ways to help.
- [LiteX for AI agents](LiteX-for-AI-Agents.md): the page an agent reads before editing anything.
- [Home](Home.md): what the whole wiki looks like from the top.
