# Contributing to the Wiki

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
  `[UARTBone](Use-Host-Bridge-to-control-debug-a-SoC.md#add-a-uartbone-bridge-to-your-soc)`.
  They work in the repository view and are rewritten for the wiki. No `[[Page]]` wiki-links,
  no absolute `https://github.com/enjoy-digital/litex/wiki/...` links.
- Links to files of the repository use the full URL
  (`https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md`).
- New pages go to `_Sidebar.md` (the navigation) and `llms.txt` (the index for AI agents, one
  line per page).
- Style: direct and practical, commands and their output in code blocks, a short intro saying
  what the page covers. Check that every command shown works with the current LiteX.

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
there for the conventions, the lint and how to add one.

## Previewing the wiki locally

```sh
pip install markdown                      # once (Python-Markdown)
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
python3 doc/wiki_sync.py check            # links, images, names, llms.txt
python3 doc/diagrams/build.py --check     # diagrams match their scripts, labels fit
python3 doc/wiki_sync.py render --out /tmp/wiki   # the exact tree the sync pushes to the wiki
```

The same checks run in CI on the pull request. After the merge, the `wiki` workflow pushes the
pages to the wiki (a few seconds); its log reports any direct wiki edit it overwrote.
