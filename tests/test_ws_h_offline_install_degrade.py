from __future__ import annotations

import importlib.util
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL_DIR = ROOT / "tools" / "control_plane" / "install"


def _load(name: str, relpath: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, INSTALL_DIR / relpath)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


degrade = _load("ws_h_degrade", "degrade.py")
build_offline_bundle = _load("ws_h_build_offline_bundle", "build_offline_bundle.py")
verify_closure_mod = _load("ws_h_verify_closure", "verify_closure.py")


def _make_wheel(wheels_dir: Path, name: str, version: str, requires: list[str]) -> Path:
    wheels_dir.mkdir(parents=True, exist_ok=True)
    whl_path = wheels_dir / f"{name}-{version}-py3-none-any.whl"
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    for r in requires:
        metadata_lines.append(f"Requires-Dist: {r}")
    metadata = "\n".join(metadata_lines) + "\n"
    with zipfile.ZipFile(whl_path, "w") as zf:
        zf.writestr(f"{name}-{version}.dist-info/METADATA", metadata)
    return whl_path


def test_dry_run_plan_never_touches_subprocess(tmp_path, monkeypatch):

    def _boom(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called in dry-run mode")

    monkeypatch.setattr(subprocess, "run", _boom)

    bp = build_offline_bundle.build(
        dry_run=True,
        wheels_dir=tmp_path / "wheels",
        site_packages_dir=tmp_path / "site-packages",
    )
    assert "pip" in bp.download_cmd and "download" in bp.download_cmd
    assert "pip" in bp.install_cmd and "install" in bp.install_cmd


def test_install_phase_is_no_index_no_network():
    bp = build_offline_bundle.plan(
        wheels_dir=Path("/tmp/wheels"),
        site_packages_dir=Path("/tmp/site-packages"),
    )
    assert "--no-index" in bp.install_cmd
    assert "--find-links" in bp.install_cmd


    assert "--only-binary=:all:" in bp.download_cmd


def test_main_dry_run_cli_prints_and_executes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no subprocess in --dry-run")),
    )
    rc = build_offline_bundle.main(
        [
            "--wheels-dir",
            str(tmp_path / "wheels"),
            "--site-packages-dir",
            str(tmp_path / "site-packages"),
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "download:" in out and "install:" in out
    assert "nothing was executed" in out


def test_offline_boot_with_vendored_bundle_blocks_network(monkeypatch):
    site_packages = ROOT / "tools" / "control_plane" / ".vendor" / "site-packages"
    if not (site_packages / "fastapi").is_dir():
        pytest.skip("no platform-matched vendored bundle present in this environment")

    import socket

    def _no_network(*args, **kwargs):
        raise AssertionError("network access attempted during offline import")

    monkeypatch.setattr(socket.socket, "connect", _no_network)

    sys.path.insert(0, str(site_packages))
    try:
        for mod_name in ("fastapi", "uvicorn"):
            sys.modules.pop(mod_name, None)
        try:
            import fastapi
            import uvicorn
        except ImportError:
            pytest.skip("vendored bundle is not ABI-compatible with this interpreter")
    finally:
        sys.path.remove(str(site_packages))


def test_verify_closure_detects_missing_transitive_dep(tmp_path):
    wheels = tmp_path / "wheels"
    _make_wheel(wheels, "anyio", "4.14.2", ['exceptiongroup; python_version < "3.11"', "idna"])
    _make_wheel(wheels, "idna", "3.18", [])


    missing = verify_closure_mod.verify_closure(wheels, ("anyio",))
    assert missing == ["exceptiongroup"]


def test_verify_closure_passes_with_full_closure(tmp_path):
    wheels = tmp_path / "wheels"
    _make_wheel(wheels, "anyio", "4.14.2", ['exceptiongroup; python_version < "3.11"', "idna"])
    _make_wheel(wheels, "idna", "3.18", [])
    _make_wheel(wheels, "exceptiongroup", "1.3.1", [])

    assert verify_closure_mod.verify_closure(wheels, ("anyio",)) == []


def test_verify_closure_canonicalizes_names(tmp_path):
    wheels = tmp_path / "wheels"
    _make_wheel(wheels, "pydantic_core", "2.46.4", [])
    _make_wheel(wheels, "pydantic", "2.13.4", ["pydantic-core"])

    assert verify_closure_mod.verify_closure(wheels, ("pydantic",)) == []


def test_verify_closure_cli_exit_codes(tmp_path, capsys):
    wheels = tmp_path / "wheels"
    _make_wheel(wheels, "anyio", "4.14.2", ["exceptiongroup"])
    rc = verify_closure_mod.main(["--wheels-dir", str(wheels), "anyio"])
    assert rc == 1
    assert "INCOMPLETE" in capsys.readouterr().out

    _make_wheel(wheels, "exceptiongroup", "1.3.1", [])
    rc = verify_closure_mod.main(["--wheels-dir", str(wheels), "anyio"])
    assert rc == 0


def _write_features(path: Path, *, flag_on: bool) -> Path:
    path.write_text(f"ws_h_control_plane: {'true' if flag_on else 'false'}\n", encoding="utf-8")
    return path


def test_flag_off_is_inert_never_probes_deps(tmp_path, monkeypatch):
    features = _write_features(tmp_path / "features.yaml", flag_on=False)

    def _boom(*args, **kwargs):
        raise AssertionError("deps probe must not run when the flag is OFF")

    monkeypatch.setattr(degrade.importlib.util, "find_spec", _boom)

    decision = degrade.resolve_surface(features_path=features)
    assert decision.mode == "static"
    assert "OFF" in decision.reason


def test_flag_on_but_deps_absent_degrades_not_crashes(tmp_path, monkeypatch):
    features = _write_features(tmp_path / "features.yaml", flag_on=True)
    monkeypatch.setattr(degrade, "_deps_importable", lambda deps=None: False)

    decision = degrade.resolve_surface(features_path=features)
    assert decision.mode == "static"
    assert "not importable" in decision.reason


def test_flag_on_and_deps_present_selects_control_plane(tmp_path, monkeypatch):
    features = _write_features(tmp_path / "features.yaml", flag_on=True)
    monkeypatch.setattr(degrade, "_deps_importable", lambda deps=None: True)

    decision = degrade.resolve_surface(features_path=features)
    assert decision.mode == "control-plane"


def test_force_static_wins_even_with_deps_present(tmp_path, monkeypatch):
    features = _write_features(tmp_path / "features.yaml", flag_on=True)
    monkeypatch.setattr(degrade, "_deps_importable", lambda deps=None: True)

    decision = degrade.resolve_surface(features_path=features, force_static=True)
    assert decision.mode == "static"
    assert "force-static" in decision.reason


def test_degrade_serves_the_adr0028_static_cockpit(tmp_path):
    out = degrade.render_static_cockpit(ROOT, out=tmp_path / "cockpit.html")
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "DasLab Cockpit" in html
    assert "<!DOCTYPE html>" in html


def test_degrade_main_cli_flag_off_renders_static(tmp_path, capsys):
    features = _write_features(tmp_path / "features.yaml", flag_on=False)
    rc = degrade.main(
        [
            "--repo-root",
            str(ROOT),
            "--features",
            str(features),
            "--out",
            str(tmp_path / "cockpit.html"),
        ]
    )
    assert rc == 0
    assert (tmp_path / "cockpit.html").is_file()
    assert "degrade-to-static" in capsys.readouterr().out


def test_degrade_never_execs_uvicorn_itself():
    source = (INSTALL_DIR / "degrade.py").read_text(encoding="utf-8")
    assert "uvicorn.run(" not in source
    assert "import uvicorn" not in source


def test_core_requirements_do_not_carry_fastapi_or_uvicorn():
    for fname in ("requirements.txt", "requirements.in"):
        p = ROOT / fname
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8").lower()
        assert "fastapi" not in text
        assert "uvicorn" not in text


def test_vendor_cache_is_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "tools/control_plane/.vendor/" in gitignore


def test_unit_examples_are_opt_in_only():
    systemd = INSTALL_DIR / "systemd" / "daslab-control-plane.service.example"
    launchd = INSTALL_DIR / "launchd" / "com.daslab.control-plane.plist.example"
    assert systemd.is_file() and launchd.is_file()


    assert systemd.suffix == ".example"
    assert launchd.suffix == ".example"

    systemd_text = systemd.read_text(encoding="utf-8")
    launchd_text = launchd.read_text(encoding="utf-8")
    for text in (systemd_text, launchd_text):
        assert "OPTIONAL" in text
        assert "Founder" in text
        assert "127.0.0.1" in text


    for py_file in INSTALL_DIR.glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        assert "systemctl enable" not in src
        assert "launchctl load" not in src


def test_control_plane_requirements_unchanged_by_this_ticket():
    req = ROOT / "tools" / "control_plane" / "requirements-control.txt"
    assert req.is_file()
    text = req.read_text(encoding="utf-8")
    assert "fastapi" in text and "uvicorn" in text
