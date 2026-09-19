import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import estimate_export, render_highlights

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required",
)
def test_large_match_with_overlays_keeps_command_short(tmp_path, qapp, monkeypatch):
    from kyykka_editor import render

    directory = tmp_path / ("Player's matches " + "x" * 25)
    directory.mkdir()
    source = directory / "source.mp4"
    output = directory / ("Highlights " + "y" * 35 + ".mp4")
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=10:duration=12",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=12",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    project = EditorProject(
        video_path=str(source),
        title="Large match",
        pre_roll_ms=0,
        post_roll_ms=100,
        impacts=[Impact((i + 1) * 100, f"Player {i}") for i in range(96)],
        round_one_end_ms=5000,
        game_end_ms=11000,
    )
    run = render._run_render
    lengths = []

    def checked_run(command, cancel, poll_progress=None, *, cwd=None):
        lengths.append(len(subprocess.list2cmdline(command)))
        assert lengths[-1] < 8000
        graph = Path(command[command.index("-filter_complex_script") + 1]).read_text()
        assert graph.count("movie=filename=") == 96
        assert "Player's matches" not in graph
        return run(command, cancel, poll_progress, cwd=cwd)

    monkeypatch.setattr(render, "_run_render", checked_run)
    updates = []
    render_highlights(project, output, 12000, progress=updates.append)
    assert len(lengths) == 1
    assert updates[-1] == 100
    probe = subprocess.run(
        [
            shutil.which("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    _, duration = estimate_export(project, 12000)
    assert float(json.loads(probe.stdout)["format"]["duration"]) == pytest.approx(
        duration / 1000, abs=0.3
    )
    assert not list(directory.glob(".kyykka-render-*"))


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required",
)
@pytest.mark.parametrize("with_title", [True, False])
@pytest.mark.parametrize("with_round", [False, True])
@pytest.mark.parametrize("background_mode", ["static", "video", "freeze"])
def test_real_render_is_windows_compatible_and_keeps_source_rate(
    tmp_path: Path, qapp: QApplication, with_title: bool, with_round: bool, background_mode: str
) -> None:
    source = tmp_path / "source.mp4"
    output = tmp_path / "highlights.mp4"
    rate = "30000/1001"
    subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=320x180:rate={rate}:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    project = EditorProject(
        video_path=str(source),
        title="Pipeline test",
        team_one="One",
        team_two="Two",
        pre_roll_ms=500,
        post_roll_ms=500,
        impacts=[Impact(2_000, "Player")],
        game_end_ms=3_000,
    )
    updates = []
    for style in (project.title_style, project.round_style, project.final_style):
        style.background_mode = background_mode
    if with_round:
        project.impacts = [Impact(1000, "Player"), Impact(3000, "Player")]
        project.round_one_end_ms = 2000
    if not with_title:
        project.title = project.team_one = project.team_two = ""

    def progress(percent):
        updates.append(percent)
        if percent == 100:
            assert output.is_file()

    render_highlights(project, output, 4_000, progress=progress)
    assert updates[0] == 0
    assert updates[-1] == 100
    assert any(0 < percent < 100 for percent in updates)
    assert updates == sorted(set(updates))

    probe = subprocess.run(
        [
            shutil.which("ffprobe") or "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,profile,pix_fmt,color_range,r_frame_rate,start_time,duration",
            "-of",
            "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    streams = json.loads(probe.stdout)["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    audio = next(stream for stream in streams if stream["codec_type"] == "audio")
    count, estimated_ms = estimate_export(project, 4_000)
    assert count == (2 if with_round else 1)
    assert abs(float(video["duration"]) - estimated_ms / 1000) < 0.15
    assert video["codec_name"] == "h264"
    assert video["profile"] == "High"
    assert video["pix_fmt"] == "yuv420p"
    # FFprobe may omit the field when the limited-range yuv420p default is used.
    assert video.get("color_range") in {None, "tv"}
    assert Fraction(video["r_frame_rate"]) == Fraction(rate)
    assert abs(float(video.get("start_time", 0))) < 0.05
    assert abs(float(video["duration"]) - float(audio["duration"])) < 0.15
    assert not list(tmp_path.glob(".kyykka-*.png"))
