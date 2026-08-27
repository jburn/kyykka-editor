import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import render_highlights

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required",
)
def test_real_render_is_windows_compatible_and_keeps_source_rate(
    tmp_path: Path, qapp: QApplication
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
    render_highlights(project, output, 4_000)

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
    assert video["codec_name"] == "h264"
    assert video["profile"] == "High"
    assert video["pix_fmt"] == "yuv420p"
    # FFprobe may omit the field when the limited-range yuv420p default is used.
    assert video.get("color_range") in {None, "tv"}
    assert Fraction(video["r_frame_rate"]) == Fraction(rate)
    assert abs(float(video.get("start_time", 0))) < 0.05
    assert abs(float(video["duration"]) - float(audio["duration"])) < 0.15
    assert not list(tmp_path.glob(".kyykka-*.png"))
