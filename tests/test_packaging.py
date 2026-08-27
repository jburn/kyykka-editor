import tomllib
from pathlib import Path

from kyykka_editor import __version__

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
    assert "Get-Command python.exe" in script
    assert "$PythonExecutable -m PyInstaller" in script


def test_ci_uploads_a_validated_windows_archive() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    assert "branches: [main]" in workflow
    assert "pull_request_review:" in workflow
    assert "types: [submitted]" in workflow
    assert "github.event.review.state == 'approved'" in workflow
    assert "github.event.pull_request.base.ref == 'main'" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "ffmpeg-9.0.1-essentials_build.zip" in workflow
    assert "fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9" in workflow
    assert "Get-FileHash" in workflow
    assert "-FFmpegBin $env:FFMPEG_BIN" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "path: dist/KyykkaEditor" in workflow
    assert "if-no-files-found: error" in workflow
    assert "retention-days: 14" in workflow


def test_version_tags_publish_github_releases() -> None:
    workflow = (PROJECT_ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    assert 'tags: ["v*"]' in workflow
    assert "Release tag $env:GITHUB_REF_NAME does not match application version" in workflow
    assert "Compress-Archive" in workflow
    assert "name: release-package" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "contents: write" in workflow
    assert 'gh release create "$GITHUB_REF_NAME"' in workflow
    assert 'gh release upload "$GITHUB_REF_NAME" "$asset" --clobber' in workflow
    assert "--generate-notes" in workflow


def test_project_declares_and_contains_gplv3_or_later() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == __version__
    assert metadata["project"]["license"] == "GPL-3.0-or-later"
    license_text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007")
    assert "either version 3 of the License, or (at your option) any later version" in license_text
