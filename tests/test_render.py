import json
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

import kyykka_editor.render as render_module
from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import (
    RenderError,
    build_intervals,
    create_score_card,
    create_thrower_overlay,
    create_title_card,
    find_media_tool,
    render_highlights,
    source_dimensions,
    source_frame_rate,
    source_has_audio,
)


def test_intervals_are_clamped_and_overlaps_are_merged() -> None:
    project = EditorProject(
        pre_roll_ms=4_000,
        post_roll_ms=3_000,
        impacts=[Impact(2_000), Impact(7_000), Impact(19_000)],
    )
    assert build_intervals(project, 20_000) == [(0.0, 10.0), (15.0, 20.0)]


def test_no_impacts_produces_no_intervals() -> None:
    assert build_intervals(EditorProject(), 10_000) == []


def test_media_tool_prefers_bundled_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "kyykka_editor"
    bundled = package / "bin" / "ffmpeg.exe"
    bundled.parent.mkdir(parents=True)
    bundled.touch()
    monkeypatch.setattr(render_module, "__file__", str(package / "render.py"))
    monkeypatch.setattr(render_module.shutil, "which", lambda _name: "path/ffmpeg.exe")
    assert find_media_tool("ffmpeg") == str(bundled)


def test_media_tool_falls_back_to_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_module.shutil, "which", lambda name: f"path/{name}.exe")
    assert find_media_tool("ffprobe") == "path/ffprobe.exe"


def test_media_tools_do_not_open_console_windows_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(render_module.sys, "platform", "win32")
    assert render_module._media_subprocess_options() == {
        "creationflags": subprocess.CREATE_NO_WINDOW
    }


def test_media_subprocess_has_no_platform_flags_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(render_module.sys, "platform", "linux")
    assert render_module._media_subprocess_options() == {}


def test_rendered_cards_and_overlay_are_valid_images(qapp: QApplication, tmp_path: Path) -> None:
    project = EditorProject(
        title="Playoffs game 3",
        team_one="One",
        team_two="Two",
        team_one_round_one_score=-2,
        team_two_round_one_score=-1,
        team_one_round_two_score=4,
        team_two_round_two_score=1,
    )
    paths = {
        "title": tmp_path / "title.png",
        "round": tmp_path / "round.png",
        "final": tmp_path / "final.png",
        "thrower": tmp_path / "thrower.png",
    }
    create_title_card(project, paths["title"], (640, 360))
    create_score_card(project, paths["round"], (640, 360), final=False)
    create_score_card(project, paths["final"], (640, 360), final=True)
    create_thrower_overlay("Player", paths["thrower"], (640, 360))

    for path in paths.values():
        image = QImage(str(path))
        assert not image.isNull()
        assert (image.width(), image.height()) == (640, 360)
    assert QImage(str(paths["thrower"])).hasAlphaChannel()


def _probe_result(payload: object, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, json.dumps(payload), "")


def test_source_frame_rate_prefers_nominal_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kyykka_editor.render._probe",
        lambda *_args: _probe_result(
            {"streams": [{"r_frame_rate": "60000/1001", "avg_frame_rate": "59940/1000"}]}
        ),
    )
    assert source_frame_rate("source.mp4") == Fraction(60_000, 1_001)


def test_source_frame_rate_falls_back_to_average(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kyykka_editor.render._probe",
        lambda *_args: _probe_result(
            {"streams": [{"r_frame_rate": "0/0", "avg_frame_rate": "25/1"}]}
        ),
    )
    assert source_frame_rate("source.mp4") == Fraction(25, 1)


@pytest.mark.parametrize("payload", [{}, {"streams": []}, {"streams": [{}]}])
def test_invalid_dimensions_raise_render_error(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    monkeypatch.setattr("kyykka_editor.render._probe", lambda *_args: _probe_result(payload))
    with pytest.raises(RenderError, match="dimensions"):
        source_dimensions("source.mp4")


def test_audio_probe_handles_missing_and_malformed_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "kyykka_editor.render._probe", lambda *_args: _probe_result({"streams": []})
    )
    assert not source_has_audio("silent.mp4")
    monkeypatch.setattr(
        "kyykka_editor.render._probe", lambda *_args: _probe_result("not a stream object")
    )
    assert not source_has_audio("broken.mp4")


def test_render_rejects_invalid_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("kyykka_editor.render.shutil.which", lambda _name: "ffmpeg")
    with pytest.raises(RenderError, match="No source"):
        render_highlights(EditorProject(), tmp_path / "out.mp4", 10_000)

    source = tmp_path / "source.mp4"
    source.touch()
    with pytest.raises(RenderError, match="different"):
        render_highlights(EditorProject(video_path=str(source)), source, 10_000)

    project = EditorProject(
        video_path=str(source),
        impacts=[Impact(2_000)],
        round_one_end_ms=5_000,
        game_end_ms=4_000,
    )
    with pytest.raises(RenderError, match="game-end"):
        render_highlights(project, tmp_path / "out.mp4", 10_000)


def test_render_command_preserves_rate_and_requests_windows_compatible_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    source.touch()
    output = tmp_path / "highlights.mp4"
    project = EditorProject(
        video_path=str(source),
        title="Final",
        team_one="One",
        team_two="Two",
        impacts=[Impact(5_000, "Player")],
        game_end_ms=8_000,
        pre_roll_ms=1_000,
        post_roll_ms=1_000,
    )
    captured: list[str] = []
    captured_options: dict[str, object] = {}

    monkeypatch.setattr("kyykka_editor.render.shutil.which", lambda name: name)
    monkeypatch.setattr("kyykka_editor.render.source_has_audio", lambda _path: True)
    monkeypatch.setattr(
        "kyykka_editor.render.source_frame_rate", lambda _path: Fraction(60_000, 1_001)
    )
    monkeypatch.setattr("kyykka_editor.render.source_dimensions", lambda _path: (320, 180))
    monkeypatch.setattr(
        "kyykka_editor.render.create_title_card", lambda _project, path, _size: path.touch()
    )
    monkeypatch.setattr(
        "kyykka_editor.render.create_score_card",
        lambda _project, path, _size, _final: path.touch(),
    )
    monkeypatch.setattr(
        "kyykka_editor.render.create_thrower_overlay",
        lambda _name, path, _size: path.touch(),
    )

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        captured_options.update(_kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("kyykka_editor.render.subprocess.run", fake_run)
    render_highlights(project, output, 12_000)

    command = " ".join(captured)
    filter_graph = captured[captured.index("-filter_complex") + 1]
    assert "fps=60000/1001" in filter_graph
    assert "xfade=transition=fade" in filter_graph
    assert "trim=start=1.000:end=9.000" in filter_graph
    assert "scale=in_range=auto:out_range=tv,format=yuv420p" in filter_graph
    assert "-profile:v high" in command
    assert "-level:v 4.1" in command
    assert "-pix_fmt yuv420p" in command
    assert "-color_range tv" in command
    assert "-r 60000/1001" in command
    assert "-fps_mode cfr" in command
    assert captured_options["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert not list(tmp_path.glob(".kyykka-*.png"))


def test_failed_render_writes_diagnostic_log_and_cleans_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.mp4"
    source.touch()
    output = tmp_path / "highlights.mp4"
    project = EditorProject(video_path=str(source), impacts=[Impact(5_000)])
    monkeypatch.setattr("kyykka_editor.render.shutil.which", lambda name: name)
    monkeypatch.setattr("kyykka_editor.render.source_has_audio", lambda _path: False)
    monkeypatch.setattr("kyykka_editor.render.source_frame_rate", lambda _path: Fraction(25, 1))
    monkeypatch.setattr("kyykka_editor.render.source_dimensions", lambda _path: (320, 180))
    monkeypatch.setattr(
        "kyykka_editor.render.create_title_card", lambda _project, path, _size: path.touch()
    )
    monkeypatch.setattr(
        "kyykka_editor.render.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "encoder exploded"),
    )
    with pytest.raises(RenderError, match="encoder exploded"):
        render_highlights(project, output, 10_000)
    assert output.with_suffix(".ffmpeg-error.log").read_text(encoding="utf-8") == "encoder exploded"
    assert not list(tmp_path.glob(".kyykka-*.png"))
