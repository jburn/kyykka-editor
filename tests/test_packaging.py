import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_packaging_configuration_contains_required_runtime_files() -> None:
    spec = (PROJECT_ROOT / "packaging/kyykka_editor.spec").read_text(encoding="utf-8")
    assert 'ffmpeg_bin / "ffmpeg.exe"' in spec
    assert 'ffmpeg_bin / "ffprobe.exe"' in spec
    assert '"kyykka_editor/bin"' in spec
    assert '"LICENSE"' in spec
    assert '"THIRD_PARTY_NOTICES.md"' in spec
    assert "console=False" in spec
    assert "kyykka-editor.ico" in spec


def test_build_script_validates_complete_output() -> None:
    script = (PROJECT_ROOT / "packaging/build.ps1").read_text(encoding="utf-8")
    for required in (
        "KyykkaEditor.exe",
        "ffmpeg.exe",
        "ffprobe.exe",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
    ):
        assert required in script


def test_project_declares_and_contains_gplv3_or_later() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["license"] == "GPL-3.0-or-later"
    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007")
    assert "either version 3 of the License, or (at your option) any later version" in license_text
