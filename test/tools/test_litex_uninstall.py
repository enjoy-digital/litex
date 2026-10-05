# SPDX-License-Identifier: BSD-2-Clause

import os
import inspect
from pathlib import Path
import subprocess
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import venv
import zipfile

import pytest

import litex_setup


@pytest.fixture
def uninstall(monkeypatch):
    monkeypatch.setattr(litex_setup, "git_repos", {
        "litex": SimpleNamespace(develop=True),
        "pythondata-software-compiler_rt": SimpleNamespace(develop=True),
        "rtl-only": SimpleNamespace(develop=False),
    })
    monkeypatch.setattr(litex_setup, "install_configs", {
        "standard": ["litex", "pythondata-software-compiler_rt", "rtl-only"],
    })
    monkeypatch.setattr(litex_setup, "pip_install_in_uv_virtualenv", lambda: False)
    monkeypatch.setattr(litex_setup, "pip_install_externally_managed", lambda: False)
    run = Mock()
    monkeypatch.setattr(litex_setup.subprocess, "check_call", run)
    return run


def test_dry_run_does_not_prompt_or_modify(uninstall, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", Mock(side_effect=AssertionError("unexpected prompt")))
    # Preview must also work in an externally managed environment.
    monkeypatch.setattr(litex_setup, "pip_install_externally_managed", lambda: True)
    litex_setup.litex_setup_uninstall_repos(dry_run=True)
    uninstall.assert_not_called()
    output = capsys.readouterr().out
    assert sys.executable in output
    assert "pythondata-software-compiler_rt" in output
    assert "rtl-only" not in output
    assert "Dry run" in output


@pytest.mark.parametrize("answer", ["", "n", "no"])
def test_decline_keeps_packages(uninstall, monkeypatch, answer):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: answer)
    litex_setup.litex_setup_uninstall_repos()
    uninstall.assert_not_called()


def test_noninteractive_requires_yes(uninstall, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(litex_setup.SetupError):
        litex_setup.litex_setup_uninstall_repos()
    uninstall.assert_not_called()


@pytest.mark.parametrize("assume_yes", [False, True])
def test_confirmation_uses_selected_interpreter(uninstall, monkeypatch, assume_yes):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: not assume_yes)
    prompt = Mock(return_value="yes")
    monkeypatch.setattr("builtins.input", prompt)
    litex_setup.litex_setup_uninstall_repos(assume_yes=assume_yes)
    uninstall.assert_called_once_with([
        sys.executable, "-m", "pip", "uninstall", "--yes", "litex", "pythondata-software-compiler_rt",
    ])
    assert prompt.call_count == (0 if assume_yes else 1)


def test_uv_uninstall_has_no_pip_yes_flag(uninstall, monkeypatch):
    monkeypatch.setattr(litex_setup, "pip_install_in_uv_virtualenv", lambda: True)
    monkeypatch.setattr(litex_setup.shutil, "which", lambda command: "/tools/uv")
    litex_setup.litex_setup_uninstall_repos(assume_yes=True)
    uninstall.assert_called_once_with([
        "/tools/uv", "pip", "uninstall", "--python", sys.executable,
        "litex", "pythondata-software-compiler_rt",
    ])


def test_externally_managed_requires_explicit_override(uninstall, monkeypatch):
    monkeypatch.setattr(litex_setup, "pip_install_externally_managed", lambda: True)
    with pytest.raises(litex_setup.SetupError):
        litex_setup.litex_setup_uninstall_repos(assume_yes=True)
    uninstall.assert_not_called()
    litex_setup.litex_setup_uninstall_repos(assume_yes=True, break_system_packages=True)
    assert "--break-system-packages" in uninstall.call_args.args[0]


@pytest.mark.parametrize("error", [OSError("missing pip"), subprocess.CalledProcessError(1, ["pip"])])
def test_package_manager_errors_fail(uninstall, error, capsys):
    uninstall.side_effect = error
    with pytest.raises(litex_setup.SetupError):
        litex_setup.litex_setup_uninstall_repos(assume_yes=True)
    assert "Package uninstall failed" in capsys.readouterr().out


def test_uninstall_avoids_auto_update_and_checkout_checks(uninstall, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["litex_setup.py", "--uninstall", "--dry-run"])
    forbidden = Mock(side_effect=AssertionError("unexpected update or checkout check"))
    for name in ["litex_setup_auto_update", "litex_setup_update_repos_file", "litex_setup_location_check"]:
        monkeypatch.setattr(litex_setup, name, forbidden)
    load = Mock()
    monkeypatch.setattr(litex_setup, "litex_setup_import_repos", load)
    litex_setup.main()
    load.assert_called_once_with(download=False)
    uninstall.assert_not_called()


@pytest.mark.parametrize("args", [
    ["--dry-run"],
    ["--uninstall", "--init"],
    ["--uninstall", "--install"],
    ["--uninstall", "--update"],
    ["--uninstall", "--freeze"],
    ["--uninstall", "--gcc=riscv"],
    ["--uninstall", "--user"],
    ["--uninstall", "install"],
])
def test_incompatible_actions_fail_before_updates(uninstall, monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["litex_setup.py", *args])
    monkeypatch.setattr(litex_setup, "litex_setup_auto_update", Mock(side_effect=AssertionError("update")))
    with pytest.raises(SystemExit) as error:
        litex_setup.main()
    assert error.value.code == 2
    uninstall.assert_not_called()


def fixture_wheel(directory, name, source_dir=None):
    """Tiny local distributions: no network/build backend or real LiteX install."""
    normalized = name.replace("-", "_")
    metadata = f"{normalized}-0.0.0.dist-info"
    module = f"uninstall_fixture_{normalized}"
    files = {
        f"{module}.py": "def main():\n    print('uninstall fixture')\n",
        f"{metadata}/METADATA": f"Metadata-Version: 2.1\nName: {name}\nVersion: 0.0.0\n",
        f"{metadata}/WHEEL": "Wheel-Version: 1.0\nGenerator: litex-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{metadata}/entry_points.txt": f"[console_scripts]\n{module} = {module}:main\n",
    }
    if source_dir is not None:
        del files[f"{module}.py"]
        files[f"{module}.pth"] = str(source_dir) + "\n"
    files[f"{metadata}/RECORD"] = "".join(f"{path},,\n" for path in [*files, f"{metadata}/RECORD"])
    wheel = directory / f"{normalized}-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    return str(wheel)


@pytest.mark.parametrize("backend", ["pip", "uv"])
def test_real_uninstall_in_disposable_venv(tmp_path, backend):
    uv = shutil.which("uv")
    if backend == "uv" and uv is None:
        pytest.skip("uv is not installed")
    env_dir = tmp_path / "venv"
    scripts = env_dir / ("Scripts" if os.name == "nt" else "bin")
    python = str(scripts / ("python.exe" if os.name == "nt" else "python"))
    environment = {key: value for key, value in os.environ.items()
        if not key.startswith(("PIP_", "UV_")) and key not in ["PYTHONPATH", "PYTHONHOME"]}
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    environment["UV_NO_CONFIG"] = "1"
    environment["UV_PYTHON_DOWNLOADS"] = "never"
    if backend == "uv":
        result = subprocess.run([uv, "venv", "--python", sys.executable, str(env_dir)],
            env=environment, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        venv.EnvBuilder(with_pip=True).create(env_dir)

    def run(*args, success=True):
        command = [python, *map(str, args)]
        if backend == "uv" and args[:2] == ("-m", "pip"):
            command = [uv, "pip", str(args[2]), "--python", python, *map(str, args[3:])]
        result = subprocess.run(command, cwd=tmp_path, env=environment,
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        if success:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode != 0, result.stdout + result.stderr
        return result

    names = ["migen", "litex", "pythondata-software-compiler-rt", "pythondata-unrelated-fixture"]
    wheels = [fixture_wheel(tmp_path, name) for name in names[1:]]
    run("-m", "pip", "install", "--no-index", "--no-deps", *wheels)
    # Exercise a real PEP 660 editable install using a dependency-free backend.
    editable = tmp_path / "migen-source"
    editable.mkdir()
    (editable / "uninstall_fixture_migen.py").write_text("def main():\n    print('editable fixture')\n")
    (editable / "pyproject.toml").write_text(
        '[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n')
    (editable / "backend.py").write_text(
        "from pathlib import Path\nimport zipfile\n" + inspect.getsource(fixture_wheel) +
        "\ndef build_editable(wheel_directory, config_settings=None, metadata_directory=None):\n"
        "    return Path(fixture_wheel(Path(wheel_directory), 'migen', Path(__file__).parent)).name\n")
    run("-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation", "-e", editable)
    setup = Path(litex_setup.__file__).resolve()
    source = tmp_path / "litex" / "local-work.txt"
    source.parent.mkdir()
    source.write_text("Keep local work.\n")

    def installed():
        result = run("-c", "from importlib.metadata import distributions; print(*(d.metadata['Name'] for d in distributions()), sep=chr(10))")
        return set(result.stdout.splitlines())

    run(setup, "--uninstall", "--config=full", "--dry-run")
    assert set(names) <= installed()
    run(setup, "--uninstall", "--config=minimal", success=False)
    assert set(names) <= installed()
    run(setup, "--uninstall", "--config=minimal", "--yes")
    assert not {"migen", "litex"} & installed()
    assert set(names[2:]) <= installed()
    assert not list(scripts.glob("uninstall_fixture_litex*"))
    assert not list(scripts.glob("uninstall_fixture_migen*"))
    assert (editable / "uninstall_fixture_migen.py").is_file()
    assert run("-c", "import importlib.util; print(importlib.util.find_spec('uninstall_fixture_migen'))").stdout.strip() == "None"
    assert source.read_text() == "Keep local work.\n"
    run(setup, "--uninstall", "--config=full", "--yes")
    assert names[2] not in installed()
    assert names[3] in installed()
    run(setup, "--uninstall", "--config=full", "--yes")
