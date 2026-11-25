# Default Branch: Moving From master To main

Most LiteX repositories use `master` as their default branch, some newer ones
(LiteNVMe, LiteDSP, LiteI2C, LiteX-M2SDR, a few `pythondata-*`) use `main`.
This page is the plan to move them all to `main` without breaking existing
users, and what is already done.

A plain rename breaks users: Git has no redirect for branch names, so every
`git clone --branch master`, `git pull` on a local `master` tracking
`origin/master`, `pip install git+...@master`, submodule with
`branch = master` and `raw.githubusercontent.com/.../master/...` download
stops working once `master` disappears. The plan below avoids it by making
LiteX's own tooling independent of the branch name first, and by keeping
`master` as a mirror of `main` after the rename.

## Step 1: Branch-Agnostic Tooling (done)

- `litex_repos.py`: `GitRepo(branch=None)` is the default and means "the
  remote's default branch". `branch=` is only set to use another branch than
  the default one (`pythondata-cpu-naxriscv` uses `master`, its default is
  `main`).
- `litex_setup.py --init` clones the remote's default branch.
- `litex_setup.py --update` asks the remote for its default branch
  (`git ls-remote --symref origin HEAD`) and switches to it. When the remote
  renamed `master` to `main` and `origin/master` is gone, the local `master` is
  renamed to `main` and moved to `origin/main`; when `master` is kept as a
  mirror, a local `main` tracking `origin/main` is created and checked out.
  Single-branch (`--clone-depth`) clones get their fetch refspec moved to the
  new branch.
- `litex_setup.py` downloads itself and `litex_repos.py` from
  `raw.githubusercontent.com/enjoy-digital/litex/HEAD/...`, which serves the
  default branch whatever its name. The install command in the README and the
  wiki uses the same `HEAD` URL.
- `litex_release.py` expects each repository to be on its remote's default
  branch when `branch` is not set.

Before going on, this has to be in a release (and so in the `litex_setup.py`
users download) for a few months, so that most installs updated through it
once.

## Step 2: Rename Every Repository At Once

For each repository still on `master` (`enjoy-digital/*`, `litex-hub/*`,
`pythondata-*`), use GitHub's rename (Settings > Branches > rename the default
branch), not a new `main` and a deleted `master`. GitHub then:

- redirects web links (`/blob/master/...`, `/tree/master/...`) to `main`;
- retargets the open pull requests to `main`;
- moves the branch protection rules;
- shows the contributors the commands to update their clone.

Doing all the repositories in the same day keeps the ecosystem consistent; the
GitHub CLI can do it:

```sh
gh api -X POST repos/<org>/<repo>/branches/master/rename -f new_name=main
```

Check the CI workflows of each repository before (and the CI run after):
triggers such as `on: push: branches: [master]` (`.github/workflows/wiki.yml`
in LiteX) have to become `main` in the same change. The wiki repository
(`litex.wiki`) keeps its own `master` branch: `wiki.yml` pushes to it and is
not concerned.

## Step 3: Keep master As A Mirror

Right after the rename, recreate `master` and keep it equal to `main` with a
workflow in each repository, so that old `litex_setup.py` copies,
`wget .../master/litex_setup.py`, `pip install git+...@master`, submodules and
scripts that clone `-b master` keep working:

```yaml
name: master-mirror
on:
  push:
    branches: [main]
permissions:
  contents: write
jobs:
  mirror:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: git push origin HEAD:refs/heads/master
```

The push is a fast-forward (`master` only follows `main`). To keep it a
mirror, protect `master` against direct pushes with a ruleset that lets GitHub
Actions bypass it (check on one repository first that the workflow can still
push). Once `master` exists again, links to it serve the mirror instead of
being redirected to `main`, which is fine since the content is the same. The mirror costs nothing: keep it for good, or at
least several releases, and announce its removal a release before if it is
ever removed.

## Step 4: Update The References

Not urgent with the mirror, mechanical, one change per repository:

- `blob/master`, `tree/master` and `raw.githubusercontent.com/.../master/`
  links in READMEs, `doc/`, the wiki sources (`doc/wiki/`), `llms.txt` and the
  agent skills (prefer `HEAD` for raw links, which follows the default
  branch);
- `branch="master"` that would remain in `litex_repos.py` or in scripts (CI,
  `bench/`, `litex-boards` tests);
- the `master` mentions in `doc/release_process.md`, `CONTRIBUTING.md` and
  `AGENTS.md` ("one topic per pull request, from `master`").

## Step 5: Announce It

In the release notes (`CHANGES.md`), the README and the issue tracker: the new
branch name, that `litex_setup.py --update` migrates existing installs, that
`master` stays as a mirror, and the commands for other clones:

```sh
git branch -m master main
git fetch origin
git branch -u origin/main main
git remote set-head origin -a
```
