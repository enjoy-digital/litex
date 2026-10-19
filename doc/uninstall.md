# Uninstalling LiteX

Use the Python interpreter/environment into which you installed LiteX. For a
virtual environment, activate it first, or invoke its Python executable directly.
Keep `litex_repos.py` next to `litex_setup.py`; uninstall uses that local repository
list and does not download files or auto-update the scripts.

Preview the selected packages and package-manager command:

```sh
python3 litex_setup.py --uninstall --config=standard --dry-run
```

Remove them after reviewing the preview:

```sh
python3 litex_setup.py --uninstall --config=standard
```

The script asks for confirmation. For unattended use, pass `--yes`:

```sh
/path/to/venv/bin/python litex_setup.py --uninstall --config=full --yes
```

The default config is `standard`. `minimal` selects Migen and LiteX; `full`
selects all Python packages in the local LiteX repository catalog. Packages that
are not installed are skipped. A failed package-manager command returns a nonzero
exit status; some earlier removals may have succeeded, so resolve the reported
error and rerun the command.

## What is removed

The script delegates removal of the selected distributions, their managed
editable-install metadata, and installed command-line entry points to
`python -m pip uninstall`. In a uv-created virtual environment it uses
`uv pip uninstall --python <interpreter>` when uv is available, matching the
installer's environment selection.

It does not require the repositories to still exist. It acts on the packages
visible to the selected interpreter, not on every Python installation on the
machine. A package installed from a different source checkout under the same
distribution name is also selected. Review the interpreter and package list
printed before confirmation.

`--user` is an install-only option: pip does not provide a user-only uninstall
switch. User installs are handled by invoking the same Python interpreter without
`--user`. Activate the appropriate virtual environment when applicable. No `sudo`
commands or manual site-packages deletions are performed. For an externally
managed Python installation, use its package manager; the existing
`--break-system-packages` option is available as an explicit override.

## Source files and other tools

Source repositories, local changes, build directories, downloaded compiler
toolchains, and shared dependencies (such as setuptools, pyserial, Amaranth, and
LUNA) are retained. This allows reinstalling with `--install` without losing work.
If you also want to reclaim the source directory, inspect and back up local
changes, untracked files, and local commits before removing that directory
yourself. Removing a virtual environment dedicated to LiteX is another way to
remove its shared Python dependencies after package removal.

For update problems, an uninstall is not always necessary: inspect the selected
interpreter and checkout paths, update the repositories, and rerun `--install`.

## Verification and older installations

Run verification outside retained source checkouts, with the same interpreter:

```sh
python3 -m pip show litex migen litex-boards
```

For uv environments without pip, use `uv pip list --python /path/to/venv/bin/python`.
A source checkout on the current directory or `PYTHONPATH` can still be imported
after uninstalling, and a command earlier on `PATH` may belong to another Python
environment.

Legacy `setup.py install`/`develop` installations may lack complete removal
metadata. If the package manager reports this, inspect the reported installation
paths and handle that specific legacy installation separately. This command does
not search for or delete files by broad `litex*` or `pythondata*` patterns.
