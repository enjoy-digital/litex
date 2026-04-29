# LiteX Release Process

LiteX releases use the `YYYY.04`, `YYYY.08` and `YYYY.12` tags. The default
release set is:

```text
litex, liteiclink, liteeth, litedram, litepcie, litesata, litesdcard,
litescope, litejesd204b, litespi, litei2c, litex-boards
```

`migen` and `pythondata-*` repositories are not released by default.
Release commands live in `litex_release.py`; `litex_setup.py` is kept for
checkout, update, install and toolchain setup tasks.

## Prepare The Changelog

During the cycle, keep the top `CHANGES.md` section as:

```text
[> Changes since 2025.12 release
--------------------------------
```

Update it with LiteX changes, notable `litex-boards` changes and notable core
changes from the released repositories. Do not bump `setup.py` and do not add
the release date header until the release is being made.

Useful commands:

```sh
git log --oneline 2025.12..HEAD
git -C ../litex-boards log --oneline 2025.12..HEAD
git -C ../litepcie log --oneline 2025.12..HEAD
git -C ../liteeth log --oneline 2025.12..HEAD
```

Recent releases used this pattern: commit the final `CHANGES.md` release header
in LiteX, then run the release helper so it creates the `Bump to version <tag>`
commits and tags in the released repositories.

## Preflight

Use a full checkout with sibling repositories next to `litex`:

```text
litex/
litex-boards/
liteeth/
litepcie/
litedram/
...
```

Run `litex_release.py` from the LiteX repository root. The helper resolves the
released sibling repositories one directory above the LiteX checkout.

Check the current release versions and last tags:

```sh
./litex_release.py --list-repos
./litex_release.py --check
```

Run the full release preflight without modifying repositories:

```sh
./litex_release.py --release 2026.04 --dry-run
```

The dry-run enforces initialized repositories, clean working trees, the expected
branch, upstream synchronization for pushed releases, push URLs, parseable
`setup.py` versions, local/remote tag collision checks and the LiteX release
tag format (`YYYY.04`, `YYYY.08` or `YYYY.12`).

Useful scoping options:

```sh
./litex_release.py --release 2026.04 --dry-run --repos litex,liteeth
./litex_release.py --check --with-pythondata
```

Override flags exist for deliberate exceptions after manual review:
`--allow-dirty`, `--allow-branch-mismatch`, `--allow-unpushed` and
`--allow-invalid-tag`.

## Finalize CHANGES.md

When making the release, change only the top header from:

```text
[> Changes since 2025.12 release
--------------------------------
```

to:

```text
[> 2026.04, released on <Month> <day><suffix> <year>
----------------------------------------------------
```

Use this commit title:

```text
CHANGES.md: Update and prepare for 2026.04 release
```

## Run The Release

Run the release:

```sh
./litex_release.py --release 2026.04
```

After confirmation, the helper bumps versioned `setup.py` files, commits
`Bump to version 2026.04`, creates lightweight tags, pushes branches and pushes
the release tags.

To split local preparation from pushing:

```sh
./litex_release.py --release 2026.04 --no-push
./litex_release.py --release 2026.04 --push
```

To resume only one phase, use `--bump`, `--tag` or `--push` with
`--release <tag>`.

## Post-Release Checks

Run:

```sh
./litex_release.py --check
```

Verify that `Last Tag` is the new release tag and `Setup Version` is the new
release tag for versioned repositories.

Check tagged checkout/update:

```sh
./litex_setup.py --dev --init --tag 2026.04
./litex_setup.py --dev --update --tag 2026.04
```

Check LiteX:

```sh
git tag --sort=-creatordate | head
python3 setup.py --version
```

`setuptools` normalizes versions such as `2026.04` to `2026.4` when queried
with `setup.py --version`; keep `setup.py` using the release tag string.

## Remaining Manual Checks

Confirm CI status before tagging. The helper also does not roll back earlier
repositories if a later repository fails after pushes or tags, so use dry-runs
and phase-based resumes to keep the release controlled.
