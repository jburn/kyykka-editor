from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from .i18n import tr
from .model import EditorProject, Impact

TITLE_DURATION_MS = 4_000
SCORE_CARD_DURATION_MS = 8_000
EDGE_CLIP_EXTENSION_MS = 3_000
CROSSFADE_SECONDS = 1.0


class RenderError(RuntimeError):
    pass


class RenderCancelled(RenderError):
    pass


def _run_render(command: list[str], cancel: Event) -> subprocess.CompletedProcess[str]:
    if cancel.is_set():
        raise RenderCancelled()
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_media_subprocess_options(),
    ) as process:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if cancel.is_set():
                    process.kill()
                    process.communicate()
                    raise RenderCancelled()
    if cancel.is_set():
        raise RenderCancelled()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _media_subprocess_options() -> dict[str, int]:
    """Prevent console-based media tools from opening windows in the GUI app."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def find_media_tool(name: str) -> str | None:
    """Find a bundled FFmpeg tool, falling back to the development PATH."""
    package_bin = Path(__file__).resolve().parent / "bin"
    candidates = [package_bin / name]
    if not name.casefold().endswith(".exe"):
        candidates.insert(0, package_bin / f"{name}.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def _probe(video_path: str, entries: str, stream: str) -> subprocess.CompletedProcess[str]:
    ffprobe = find_media_tool("ffprobe")
    if not ffprobe:
        raise RenderError(tr("FFprobe was not found in the application bundle or on PATH"))
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
        **_media_subprocess_options(),
    )


def source_has_audio(video_path: str) -> bool:
    try:
        result = _probe(video_path, "stream=index", "a:0")
        payload = json.loads(result.stdout)
        return result.returncode == 0 and isinstance(payload, dict) and bool(payload.get("streams"))
    except (RenderError, json.JSONDecodeError):
        return False


def source_dimensions(video_path: str) -> tuple[int, int]:
    result = _probe(video_path, "stream=width,height", "v:0")
    try:
        stream = json.loads(result.stdout)["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RenderError(tr("Could not determine the source video's dimensions")) from error


def source_frame_rate(video_path: str) -> Fraction:
    result = _probe(video_path, "stream=avg_frame_rate,r_frame_rate", "v:0")
    try:
        stream = json.loads(result.stdout)["streams"][0]
        try:
            nominal = Fraction(stream.get("r_frame_rate", "0/1"))
        except (ValueError, ZeroDivisionError):
            nominal = Fraction(0)
        try:
            average = Fraction(stream.get("avg_frame_rate", "0/1"))
        except (ValueError, ZeroDivisionError):
            average = Fraction(0)
        rate = nominal if nominal > 0 else average
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
        raise RenderError(tr("Could not determine the source video's frame rate")) from error


def create_title_card(project: EditorProject, path: Path, size: tuple[int, int]) -> None:
    width, height = size
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#2a76bc"))
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
        raise RenderError(tr("Could not create the title screen image"))


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
    heading = tr("Final result") if final else tr("Round 1 result")
    one_score = project.team_one_total if final else project.team_one_round_one_score
    two_score = project.team_two_total if final else project.team_two_round_one_score

    painter.setFont(QFont("Arial", max(20, height // 25), QFont.Weight.Bold))
    painter.drawText(
        QRect(width // 10, height // 8, width * 4 // 5, height // 6),
        Qt.AlignmentFlag.AlignCenter,
        heading,
    )
    team_font_size = max(24, height // 17)
    team_one_name = project.team_one or tr("Team 1")
    team_two_name = project.team_two or tr("Team 2")
    winner_name = (
        team_one_name if one_score > two_score else team_two_name if two_score > one_score else None
    )
    name_score_gap = max(14, width // 80)
    center_gap = max(48, width // 9)
    score_padding = max(16, width // 100)

    def team_font(name: str) -> QFont:
        font = QFont("Arial", team_font_size)
        if not final:
            font.setBold(True)
        elif winner_name == name:
            font.setBold(True)
            font.setUnderline(True)
        return font

    while True:
        score_font = QFont("Arial", team_font_size, QFont.Weight.Bold)
        painter.setFont(team_font(team_one_name))
        team_one_width = painter.fontMetrics().horizontalAdvance(team_one_name)
        painter.setFont(team_font(team_two_name))
        team_two_width = painter.fontMetrics().horizontalAdvance(team_two_name)
        painter.setFont(score_font)
        score_one_width = (
            painter.fontMetrics().horizontalAdvance(str(one_score)) + 2 * score_padding
        )
        score_two_width = (
            painter.fontMetrics().horizontalAdvance(str(two_score)) + 2 * score_padding
        )
        total_width = (
            team_one_width
            + name_score_gap
            + score_one_width
            + center_gap
            + score_two_width
            + name_score_gap
            + team_two_width
        )
        if total_width <= width * 9 // 10 or team_font_size <= 14:
            break
        team_font_size -= 2

    row_height = max(height // 8, team_font_size * 2)
    row_y = height * 2 // 5
    x = (width - total_width) // 2
    painter.setPen(QColor("white"))
    painter.setFont(team_font(team_one_name))
    painter.drawText(
        QRect(x, row_y, team_one_width, row_height),
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        team_one_name,
    )
    x += team_one_width + name_score_gap

    def draw_score(score: int, box_width: int, box_x: int) -> None:
        box = QRect(box_x, row_y, box_width, row_height)
        painter.setPen(QPen(QColor(255, 255, 255, 180), max(1, height // 360)))
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.drawRoundedRect(box, 10, 10)
        painter.setPen(QColor("white"))
        painter.setFont(score_font)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, str(score))

    draw_score(one_score, score_one_width, x)
    x += score_one_width + center_gap
    draw_score(two_score, score_two_width, x)
    x += score_two_width + name_score_gap
    painter.setPen(QColor("white"))
    painter.setFont(team_font(team_two_name))
    painter.drawText(
        QRect(x, row_y, team_two_width, row_height),
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        team_two_name,
    )
    painter.end()
    if not image.save(str(path), "PNG"):
        raise RenderError(tr("Could not create the score screen image"))


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
        raise RenderError(tr("Could not create the thrower overlay"))


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


def _impact_bounds(
    project: EditorProject, impact: Impact, included: list[Impact], duration_ms: int
) -> tuple[float, float]:
    extra_before = EDGE_CLIP_EXTENSION_MS if impact is included[0] else 0
    extra_after = EDGE_CLIP_EXTENSION_MS if impact is included[-1] else 0
    return (
        max(0, impact.timestamp_ms - project.pre_roll_ms - extra_before) / 1_000,
        min(duration_ms, impact.timestamp_ms + project.post_roll_ms + extra_after) / 1_000,
    )


def estimate_export(project: EditorProject, duration_ms: int) -> tuple[int, int | None]:
    """Return exported clip count and approximate output milliseconds, not render time."""
    included = [
        impact
        for impact in project.impacts
        if project.game_end_ms is None or impact.timestamp_ms <= project.game_end_ms
    ]
    if not included:
        return 0, 0
    if duration_ms <= 0:
        return len(included), None
    if (
        project.round_one_end_ms is not None
        and project.game_end_ms is not None
        and project.game_end_ms < project.round_one_end_ms
    ):
        return len(included), None
    segments = [("title", TITLE_DURATION_MS / 1_000)]
    count = 0
    groups = (
        [included]
        if project.round_one_end_ms is None
        else [
            [impact for impact in included if impact.timestamp_ms <= project.round_one_end_ms],
            [impact for impact in included if impact.timestamp_ms > project.round_one_end_ms],
        ]
    )
    for index, group in enumerate(groups):
        for impact in group:
            start, end = _impact_bounds(project, impact, included, duration_ms)
            if end > start:
                segments.append(("clip", end - start))
                count += 1
        if index == 0 and project.round_one_end_ms is not None:
            segments.append(("round", SCORE_CARD_DURATION_MS / 1_000))
    if project.game_end_ms is not None:
        segments.append(("final", SCORE_CARD_DURATION_MS / 1_000))
    if not count:
        return 0, 0
    if len(segments) >= 2 and segments[1][0] == "clip":
        first, second = segments[0][1], segments[1][1]
        segments[:2] = [("intro", first + second - min(CROSSFADE_SECONDS, first / 2, second / 2))]
    if len(segments) >= 2 and segments[-1][0] == "final" and segments[-2][0] in {"clip", "intro"}:
        first, second = segments[-2][1], segments[-1][1]
        segments[-2:] = [("outro", first + second - min(CROSSFADE_SECONDS, first / 2, second / 2))]
    return count, round(sum(seconds for _, seconds in segments) * 1_000)


def render_highlights(
    project: EditorProject, output_path: Path, duration_ms: int, cancel: Event | None = None
) -> None:
    cancel = cancel if cancel is not None else Event()
    if cancel.is_set():
        raise RenderCancelled()
    if Path(project.video_path).resolve() == output_path.resolve():
        raise RenderError(tr("The export file must be different from the source video"))
    # Publish only complete videos, preserving any previous export on cancellation.
    with TemporaryDirectory(prefix=".kyykka-render-", dir=output_path.parent) as directory:
        staged_output = Path(directory) / output_path.name
        try:
            _render_highlights(project, staged_output, duration_ms, cancel)
        except RenderError:
            log = staged_output.with_suffix(".ffmpeg-error.log")
            if log.exists():
                destination = output_path.with_suffix(".ffmpeg-error.log")
                log.replace(destination)
                raise RenderError(
                    tr(
                        "FFmpeg failed. Full log: {path}\n{detail}",
                        path=destination,
                        detail=destination.read_text(encoding="utf-8")[-2000:],
                    )
                ) from None
            raise
        if cancel.is_set():
            raise RenderCancelled()
        staged_output.replace(output_path)


def _render_highlights(
    project: EditorProject, output_path: Path, duration_ms: int, cancel: Event
) -> None:
    """Render a title card followed by all marked highlight intervals."""
    ffmpeg = find_media_tool("ffmpeg")
    if not ffmpeg:
        raise RenderError(tr("FFmpeg was not found in the application bundle or on PATH"))
    if not project.video_path:
        raise RenderError(tr("No source video is selected"))
    if Path(project.video_path).resolve() == output_path.resolve():
        raise RenderError(tr("The export file must be different from the source video"))
    if (
        project.round_one_end_ms is not None
        and project.game_end_ms is not None
        and project.game_end_ms < project.round_one_end_ms
    ):
        raise RenderError(tr("The game-end marker must be after the round-one marker"))
    included_impacts = [
        impact
        for impact in project.impacts
        if project.game_end_ms is None or impact.timestamp_ms <= project.game_end_ms
    ]
    if not included_impacts:
        raise RenderError(tr("Mark at least one impact before exporting"))
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
    segment_kinds: list[str] = []
    segment_durations: list[float] = []

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
    segment_kinds.append("title")
    segment_durations.append(title_seconds)
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
        segment_kinds.append("final" if final else "round")
        segment_durations.append(score_card_seconds)
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
            if cancel.is_set():
                raise RenderCancelled()
            start, end = _impact_bounds(project, impact, included_impacts, duration_ms)
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
            segment_kinds.append("clip")
            segment_durations.append(end - start)
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

    def crossfade_pair(index: int, output_prefix: str) -> None:
        fade_duration = min(
            CROSSFADE_SECONDS,
            segment_durations[index] / 2,
            segment_durations[index + 1] / 2,
        )
        output_video = f"[{output_prefix}v]"
        output_audio = f"[{output_prefix}a]"
        filters.append(
            f"{video_labels[index]}{video_labels[index + 1]}xfade=transition=fade:"
            f"duration={fade_duration:.3f}:"
            f"offset={segment_durations[index] - fade_duration:.6f}{output_video}"
        )
        if has_audio:
            filters.append(
                f"{audio_labels[index]}{audio_labels[index + 1]}"
                f"acrossfade=d={fade_duration:.3f}{output_audio}"
            )
        video_labels[index : index + 2] = [output_video]
        if has_audio:
            audio_labels[index : index + 2] = [output_audio]
        segment_durations[index : index + 2] = [
            segment_durations[index] + segment_durations[index + 1] - fade_duration
        ]
        segment_kinds[index : index + 2] = [output_prefix]

    if len(segment_kinds) >= 2 and segment_kinds[:2] == ["title", "clip"]:
        crossfade_pair(0, "intro")

    if (
        len(segment_kinds) >= 2
        and segment_kinds[-1] == "final"
        and segment_kinds[-2]
        in {
            "clip",
            "intro",
        }
    ):
        crossfade_pair(len(segment_kinds) - 2, "outro")

    if has_audio:
        segment_inputs = "".join(
            video + audio for video, audio in zip(video_labels, audio_labels, strict=True)
        )
        filters.append(f"{segment_inputs}concat=n={len(video_labels)}:v=1:a=1[outv][outa]")
    else:
        filters.append(f"{''.join(video_labels)}concat=n={len(video_labels)}:v=1:a=0[outv]")
    filters.append("[outv]scale=in_range=auto:out_range=tv,format=yuv420p[compatv]")

    command.extend(["-filter_complex", ";".join(filters), "-map", "[compatv]"])
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
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
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
        result = _run_render(command, cancel)
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)

    if result.returncode:
        error_log = output_path.with_suffix(".ffmpeg-error.log")
        try:
            error_log.write_text(result.stderr, encoding="utf-8")
            log_note = tr("\n\nFull log: {path}", path=error_log)
        except OSError:
            log_note = ""
        lines = [
            line
            for line in result.stderr.strip().splitlines()
            if line.strip() and line.strip() != "Conversion failed!"
        ]
        detail = "\n".join(lines[-8:]) if lines else tr("Unknown FFmpeg error")
        raise RenderError(
            tr("FFmpeg failed:\n{detail}{log_note}", detail=detail, log_note=log_note)
        )
