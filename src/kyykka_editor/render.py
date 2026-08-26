from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

from .model import EditorProject

TITLE_DURATION_MS = 4_000


class RenderError(RuntimeError):
    pass


def _probe(video_path: str, entries: str, stream: str) -> subprocess.CompletedProcess[str]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RenderError("FFprobe was not found on PATH")
    return subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            stream,
            "-show_entries",
            entries,
            "-of",
            "json",
            video_path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def source_has_audio(video_path: str) -> bool:
    try:
        result = _probe(video_path, "stream=index", "a:0")
        return result.returncode == 0 and bool(json.loads(result.stdout).get("streams"))
    except (RenderError, json.JSONDecodeError):
        return False


def source_dimensions(video_path: str) -> tuple[int, int]:
    result = _probe(video_path, "stream=width,height", "v:0")
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RenderError("Could not determine the source video's dimensions") from error


def source_frame_rate(video_path: str) -> Fraction:
    result = _probe(video_path, "stream=avg_frame_rate,r_frame_rate", "v:0")
    try:
        stream = json.loads(result.stdout)["streams"][0]
        rate = Fraction(stream.get("avg_frame_rate") or stream["r_frame_rate"])
        if rate <= 0:
            raise ValueError
        return rate
    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        ZeroDivisionError,
        json.JSONDecodeError,
    ) as error:
        raise RenderError("Could not determine the source video's frame rate") from error


def create_title_card(project: EditorProject, path: Path, size: tuple[int, int]) -> None:
    width, height = size
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#12213a"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("white"))

    title = project.title or "Kyykkä"
    matchup = ""
    if project.team_one and project.team_two:
        candidate = f"{project.team_one} vs. {project.team_two}"
        if candidate.casefold() not in title.casefold():
            matchup = candidate

    painter.setFont(QFont("Arial", max(24, height // 16), QFont.Weight.Bold))
    painter.drawText(
        QRect(width // 12, height // 4, width * 5 // 6, height // 3),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        title,
    )
    if matchup:
        painter.setFont(QFont("Arial", max(18, height // 28)))
        painter.drawText(
            QRect(width // 12, height * 7 // 12, width * 5 // 6, height // 6),
            Qt.AlignmentFlag.AlignCenter,
            matchup,
        )
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RenderError("Could not create the title screen image")


def build_intervals(project: EditorProject, duration_ms: int) -> list[tuple[float, float]]:
    """Return merged highlight intervals in seconds."""
    intervals: list[tuple[int, int]] = []
    for impact in sorted(project.impacts):
        start = max(0, impact.timestamp_ms - project.pre_roll_ms)
        end = min(duration_ms, impact.timestamp_ms + project.post_roll_ms)
        if intervals and start <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], end))
        elif end > start:
            intervals.append((start, end))
    return [(start / 1_000, end / 1_000) for start, end in intervals]


def render_highlights(project: EditorProject, output_path: Path, duration_ms: int) -> None:
    """Render a title card followed by all marked highlight intervals."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RenderError("FFmpeg was not found on PATH")
    if not project.video_path:
        raise RenderError("No source video is selected")
    intervals = build_intervals(project, duration_ms)
    if not intervals:
        raise RenderError("Mark at least one impact before exporting")

    has_audio = source_has_audio(project.video_path)
    title_seconds = TITLE_DURATION_MS / 1_000
    frame_rate = source_frame_rate(project.video_path)
    frame_rate_ffmpeg = f"{frame_rate.numerator}/{frame_rate.denominator}"

    title_path: Path | None = None
    command = [ffmpeg, "-y", "-fflags", "+genpts", "-i", project.video_path]
    filters: list[str] = []
    video_labels: list[str] = []
    audio_labels: list[str] = []

    width, height = source_dimensions(project.video_path)
    title_path = output_path.parent / f".kyykka-title-{uuid.uuid4().hex}.png"
    create_title_card(project, title_path, (width, height))
    command.extend(
        [
            "-loop",
            "1",
            "-framerate",
            frame_rate_ffmpeg,
            "-t",
            f"{title_seconds:.3f}",
            "-i",
            str(title_path),
        ]
    )
    filters.append(
        f"[1:v]scale={width}:{height},setsar=1,format=yuv420p,"
        f"trim=duration={title_seconds:.3f},settb=AVTB,"
        f"setpts=N/(({frame_rate_ffmpeg})*TB)[titlev]"
    )
    video_labels.append("[titlev]")
    if has_audio:
        command.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{title_seconds:.3f}",
                "-i",
                "anullsrc=sample_rate=48000:channel_layout=stereo",
            ]
        )
        filters.append(
            f"[2:a]atrim=duration={title_seconds:.3f},"
            "aformat=sample_rates=48000:channel_layouts=stereo,"
            "asetpts=N/SR/TB[titlea]"
        )
        audio_labels.append("[titlea]")

    for index, (start, end) in enumerate(intervals):
        filters.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},fps={frame_rate_ffmpeg},"
            f"scale={width}:{height},setsar=1,format=yuv420p,"
            f"settb=AVTB,setpts=N/(({frame_rate_ffmpeg})*TB)[v{index}]"
        )
        video_labels.append(f"[v{index}]")
        if has_audio:
            filters.append(
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},aresample=48000,"
                "aformat=sample_rates=48000:channel_layouts=stereo,"
                f"asetpts=N/SR/TB[a{index}]"
            )
            audio_labels.append(f"[a{index}]")

    if has_audio:
        segment_inputs = "".join(
            video + audio for video, audio in zip(video_labels, audio_labels, strict=True)
        )
        filters.append(f"{segment_inputs}concat=n={len(video_labels)}:v=1:a=1[outv][outa]")
    else:
        filters.append(f"{''.join(video_labels)}concat=n={len(video_labels)}:v=1:a=0[outv]")

    command.extend(["-filter_complex", ";".join(filters), "-map", "[outv]"])
    if has_audio:
        command.extend(["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"])
    else:
        command.append("-an")
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-r",
            frame_rate_ffmpeg,
            "-fps_mode",
            "cfr",
            "-video_track_timescale",
            "90000",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", check=False
        )
    finally:
        if title_path is not None:
            title_path.unlink(missing_ok=True)

    if result.returncode:
        lines = result.stderr.strip().splitlines()
        raise RenderError(f"FFmpeg failed: {lines[-1] if lines else 'Unknown error'}")
