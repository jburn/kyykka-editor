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
SCORE_CARD_DURATION_MS = 8_000


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


def create_score_card(
    project: EditorProject,
    path: Path,
    size: tuple[int, int],
    final: bool,
) -> None:
    width, height = size
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#2a76bc"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("white"))
    heading = "Lopputulos" if final else "1. puolen tulos"
    one_score = project.team_one_total if final else project.team_one_round_one_score
    two_score = project.team_two_total if final else project.team_two_round_one_score

    painter.setFont(QFont("Arial", max(20, height // 25), QFont.Weight.Bold))
    painter.drawText(
        QRect(width // 10, height // 8, width * 4 // 5, height // 6),
        Qt.AlignmentFlag.AlignCenter,
        heading,
    )
    if final:
        team_font_size = max(24, height // 17)
        team_one_name = project.team_one or "Joukkue 1"
        team_two_name = project.team_two or "Joukkue 2"

        def team_font(name: str) -> QFont:
            font = QFont("Arial", team_font_size)
            if project.winner == name:
                font.setBold(True)
                font.setUnderline(True)
            return font

        while True:
            normal_font = QFont("Arial", team_font_size)
            segments = (
                (team_one_name, team_font(team_one_name)),
                (f" {one_score} - {two_score} ", normal_font),
                (team_two_name, team_font(team_two_name)),
            )
            widths = []
            for text, font in segments:
                painter.setFont(font)
                widths.append(painter.fontMetrics().horizontalAdvance(text))
            if sum(widths) <= width * 9 // 10 or team_font_size <= 14:
                break
            team_font_size -= 2
        x = (width - sum(widths)) // 2
        painter.setPen(QColor("white"))
        for (text, font), text_width in zip(segments, widths, strict=True):
            painter.setFont(font)
            painter.drawText(
                QRect(x, height * 2 // 5, text_width, height // 5),
                Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            x += text_width
    else:
        painter.setFont(QFont("Arial", max(24, height // 16), QFont.Weight.Bold))
        painter.drawText(
            QRect(width // 12, height // 3, width * 5 // 6, height // 4),
            Qt.AlignmentFlag.AlignCenter,
            f"{project.team_one or 'Joukkue 1'}  {one_score} — {two_score}  "
            f"{project.team_two or 'Joukkue 2'}",
        )
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RenderError("Could not create the score screen image")


def create_thrower_overlay(name: str, path: Path, size: tuple[int, int]) -> None:
    width, height = size
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Arial", max(16, height // 32), QFont.Weight.Bold)
    painter.setFont(font)
    metrics = painter.fontMetrics()
    padding_x = max(16, width // 100)
    padding_y = max(10, height // 100)
    box_width = metrics.horizontalAdvance(name) + padding_x * 2
    box_height = metrics.height() + padding_y * 2
    box = QRect(width // 40, height - box_height - height // 24, box_width, box_height)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 150))
    painter.drawRoundedRect(box, padding_y, padding_y)
    painter.setPen(QColor("white"))
    painter.drawText(box, Qt.AlignmentFlag.AlignCenter, name)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RenderError("Could not create the thrower overlay")


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
    if (
        project.round_one_end_ms is not None
        and project.game_end_ms is not None
        and project.game_end_ms < project.round_one_end_ms
    ):
        raise RenderError("The game-end marker must be after the round-one marker")
    included_impacts = [
        impact
        for impact in project.impacts
        if project.game_end_ms is None or impact.timestamp_ms <= project.game_end_ms
    ]
    if not included_impacts:
        raise RenderError("Mark at least one impact before exporting")
    if project.round_one_end_ms is None:
        impact_groups = [included_impacts]
    else:
        first = [
            impact for impact in included_impacts if impact.timestamp_ms <= project.round_one_end_ms
        ]
        second = [
            impact for impact in included_impacts if impact.timestamp_ms > project.round_one_end_ms
        ]
        impact_groups = [first, second]

    has_audio = source_has_audio(project.video_path)
    title_seconds = TITLE_DURATION_MS / 1_000
    score_card_seconds = SCORE_CARD_DURATION_MS / 1_000
    frame_rate = source_frame_rate(project.video_path)
    frame_rate_ffmpeg = f"{frame_rate.numerator}/{frame_rate.denominator}"

    temporary_paths: list[Path] = []
    command = [ffmpeg, "-y", "-fflags", "+genpts", "-i", project.video_path]
    filters: list[str] = []
    video_labels: list[str] = []
    audio_labels: list[str] = []

    width, height = source_dimensions(project.video_path)
    title_path = output_path.parent / f".kyykka-title-{uuid.uuid4().hex}.png"
    temporary_paths.append(title_path)
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

    input_index = 3 if has_audio else 2
    clip_index = 0
    card_index = 0

    def add_score_screen(final: bool) -> None:
        nonlocal input_index, card_index
        card_path = output_path.parent / f".kyykka-score-{uuid.uuid4().hex}.png"
        temporary_paths.append(card_path)
        create_score_card(project, card_path, (width, height), final)
        command.extend(
            [
                "-loop",
                "1",
                "-framerate",
                frame_rate_ffmpeg,
                "-t",
                f"{score_card_seconds:.3f}",
                "-i",
                str(card_path),
            ]
        )
        filters.append(
            f"[{input_index}:v]scale={width}:{height},setsar=1,format=yuv420p,"
            f"trim=duration={score_card_seconds:.3f},settb=AVTB,"
            f"setpts=N/(({frame_rate_ffmpeg})*TB)[cardv{card_index}]"
        )
        video_labels.append(f"[cardv{card_index}]")
        input_index += 1
        if has_audio:
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{score_card_seconds:.3f}",
                    "-i",
                    "anullsrc=sample_rate=48000:channel_layout=stereo",
                ]
            )
            filters.append(
                f"[{input_index}:a]atrim=duration={score_card_seconds:.3f},"
                "aformat=sample_rates=48000:channel_layouts=stereo,"
                f"asetpts=N/SR/TB[carda{card_index}]"
            )
            audio_labels.append(f"[carda{card_index}]")
            input_index += 1
        card_index += 1

    for group_index, impacts in enumerate(impact_groups):
        for impact in impacts:
            start = max(0, impact.timestamp_ms - project.pre_roll_ms) / 1_000
            end = min(duration_ms, impact.timestamp_ms + project.post_roll_ms) / 1_000
            if end <= start:
                continue
            filters.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},fps={frame_rate_ffmpeg},"
                f"scale={width}:{height},setsar=1,format=yuv420p,"
                f"settb=AVTB,setpts=N/(({frame_rate_ffmpeg})*TB)[basev{clip_index}]"
            )
            if impact.thrower:
                overlay_path = output_path.parent / f".kyykka-thrower-{uuid.uuid4().hex}.png"
                temporary_paths.append(overlay_path)
                create_thrower_overlay(impact.thrower, overlay_path, (width, height))
                command.extend(
                    ["-loop", "1", "-framerate", frame_rate_ffmpeg, "-i", str(overlay_path)]
                )
                filters.append(
                    f"[{input_index}:v]format=rgba[overlay{clip_index}];"
                    f"[basev{clip_index}][overlay{clip_index}]"
                    f"overlay=0:0:shortest=1[v{clip_index}]"
                )
                input_index += 1
            else:
                filters.append(f"[basev{clip_index}]null[v{clip_index}]")
            video_labels.append(f"[v{clip_index}]")
            if has_audio:
                filters.append(
                    f"[0:a]atrim=start={start:.3f}:end={end:.3f},aresample=48000,"
                    "aformat=sample_rates=48000:channel_layouts=stereo,"
                    f"asetpts=N/SR/TB[a{clip_index}]"
                )
                audio_labels.append(f"[a{clip_index}]")
            clip_index += 1
        if group_index == 0 and project.round_one_end_ms is not None:
            add_score_screen(final=False)

    if project.game_end_ms is not None:
        add_score_screen(final=True)

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
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)

    if result.returncode:
        lines = result.stderr.strip().splitlines()
        raise RenderError(f"FFmpeg failed: {lines[-1] if lines else 'Unknown error'}")
