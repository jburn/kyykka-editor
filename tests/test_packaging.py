from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_packaging_configuration_contains_required_runtime_files() -> None:
    spec = (PROJECT_ROOT / "packaging/kyykka_editor.spec").read_text(encoding="utf-8")
    assert 'ffmpeg_bin / "ffmpeg.exe"' in spec
    assert 'ffmpeg_bin / "ffprobe.exe"' in spec
    assert '"kyykka_editor/bin"' in spec
    assert '"THIRD_PARTY_NOTICES.md"' in spec
    assert "console=False" in spec
    assert "kyykka-editor.ico" in spec


def test_build_script_validates_complete_output() -> None:
    script = (PROJECT_ROOT / "packaging/build.ps1").read_text(encoding="utf-8")
    for required in (
        "KyykkaEditor.exe",
        "ffmpeg.exe",
        "ffprobe.exe",
        "THIRD_PARTY_NOTICES.md",
    ):
        assert required in script
