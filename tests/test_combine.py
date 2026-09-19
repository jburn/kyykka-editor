import json
import shutil
import subprocess
from dataclasses import replace
from threading import Event

import pytest

from kyykka_editor.combine import can_stream_copy, combine_videos, inspect_videos
from kyykka_editor.render import RenderCancelled, RenderError


@pytest.fixture
def clips(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and FFprobe are required")

    def create(name, color, size="160x90", rate="15", audio=True):
        path = tmp_path / name
        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}:r={rate}:d=1",
        ]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)]
        subprocess.run(command, check=True, capture_output=True)
        return path

    return create


def video_packet_hashes(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_packets",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            "packet=data_hash",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [packet["data_hash"] for packet in json.loads(result.stdout)["packets"]]


@pytest.mark.integration
def test_copy_preserves_encoded_frames_order_audio_and_duration(clips, tmp_path):
    red = clips("game Ä's 1.mp4", "red")
    blue = clips("game 2.mp4", "blue")
    videos = inspect_videos([blue, red])
    assert can_stream_copy(videos)
    output = tmp_path / "series.mp4"
    progress = []
    combine_videos(videos, output, progress=progress.append)
    combined = inspect_videos([output, output])[0]
    assert combined.duration == pytest.approx(2, abs=0.15)
    assert combined.has_audio
    assert video_packet_hashes(output) == video_packet_hashes(blue) + video_packet_hashes(red)
    assert progress[0] == 0 and progress[-1] == 100
    assert progress == sorted(set(progress))
    assert not list(tmp_path.glob(".kyykka-combine-*"))


@pytest.mark.integration
@pytest.mark.parametrize("first_audio,second_audio", [(True, False), (False, True), (False, False)])
def test_conversion_handles_mixed_dimensions_rates_and_missing_audio(
    clips, tmp_path, first_audio, second_audio
):
    first = clips("first.mp4", "red", audio=first_audio)
    second = clips("second.mp4", "blue", size="128x96", rate="24", audio=second_audio)
    videos = inspect_videos([first, second])
    assert not can_stream_copy(videos)
    output = tmp_path / "series.mp4"
    with pytest.raises(RenderError, match="conversion"):
        combine_videos(videos, output)
    assert not output.exists()
    combine_videos(videos, output, convert=True)
    result = inspect_videos([output, output])[0]
    assert (result.width, result.height, result.rate) == (160, 90, 15)
    assert result.duration == pytest.approx(2, abs=0.15)
    assert result.has_audio == (first_audio or second_audio)
    if result.has_audio:
        audio = next(s for s in result.streams if s["codec_type"] == "audio")
        assert audio["channels"] == 2
        assert audio["sample_rate"] == "48000"
        assert float(audio["duration"]) == pytest.approx(result.duration, abs=0.15)
    # Decode samples away from the join to verify order and playable output.
    for timestamp, channel in [("0.5", 0), ("1.5", 2)]:
        frame = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                timestamp,
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-vf",
                "scale=1:1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout
        assert frame[channel] > 150


@pytest.mark.integration
@pytest.mark.parametrize("convert", [False, True])
def test_cancel_failure_and_input_alias_preserve_files(clips, tmp_path, convert):
    source = clips("source.mp4", "red")
    videos = inspect_videos([source, source])
    original = source.read_bytes()
    with pytest.raises(RenderError, match="different"):
        combine_videos(videos, source)
    assert source.read_bytes() == original
    output = tmp_path / "existing.mp4"
    output.write_bytes(b"previous export")
    cancel = Event()

    def cancel_after_progress(percent):
        if percent > 0:
            cancel.set()

    with pytest.raises(RenderCancelled):
        combine_videos(
            videos, output, convert=convert, cancel=cancel, progress=cancel_after_progress
        )
    assert output.read_bytes() == b"previous export"
    source.unlink()
    with pytest.raises(RenderError):
        combine_videos(videos, output)
    assert output.read_bytes() == b"previous export"
    assert not list(tmp_path.glob(".kyykka-combine-*"))


@pytest.mark.integration
def test_compatibility_checks_codec_configuration_and_stream_layout(clips):
    source = clips("source.mp4", "red")
    videos = inspect_videos([source, source])
    for field, value in [
        ("extradata_hash", "different"),
        ("time_base", "1/1000"),
        ("pix_fmt", "yuv444p"),
        ("sample_aspect_ratio", "2:1"),
    ]:
        streams = [dict(s) for s in videos[1].streams]
        streams[0][field] = value
        assert not can_stream_copy([videos[0], replace(videos[1], streams=streams)])
    assert not can_stream_copy([videos[0], replace(videos[1], streams=videos[1].streams[:1])])


def test_inspect_rejects_too_few_inputs():
    with pytest.raises(RenderError, match="two"):
        inspect_videos([])


@pytest.mark.integration
def test_inspect_rejects_corrupt_input_and_honors_cancel(clips, tmp_path):
    good = clips("source.mp4", "red")
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(RenderError, match="Could not read video"):
        inspect_videos([good, bad])
    cancel = Event()
    cancel.set()
    with pytest.raises(RenderCancelled):
        inspect_videos([good, good], cancel)
