"""Join standalone match videos without reading or changing an editor project."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from .i18n import tr
from .render import RenderCancelled, RenderError, _run_render, find_media_tool


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    duration: float
    streams: list[dict]
    width: int
    height: int
    rate: Fraction

    @property
    def has_audio(self) -> bool:
        return any(stream.get("codec_type") == "audio" for stream in self.streams)


def inspect_videos(paths: Sequence[Path], cancel: Event | None = None) -> list[VideoInfo]:
    cancel = cancel if cancel is not None else Event()
    if len(paths) < 2:
        raise RenderError(tr("Select at least two videos."))
    probe = find_media_tool("ffprobe")
    if not probe:
        raise RenderError(tr("FFprobe was not found in the application bundle or on PATH"))
    videos = []
    for path in paths:
        path = path.resolve()
        if not path.is_file() or any(char in str(path) for char in "\r\n"):
            raise RenderError(tr("Could not read video: {path}", path=path))
        result = _run_render(
            [
                probe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-show_data_hash",
                "sha256",
                "-of",
                "json",
                str(path),
            ],
            cancel,
        )
        try:
            if result.returncode:
                raise ValueError(result.stderr)
            data = json.loads(result.stdout)
            streams = data["streams"]
            video = next(
                s
                for s in streams
                if s.get("codec_type") == "video"
                and not s.get("disposition", {}).get("attached_pic")
            )
            duration = float(video.get("duration", data["format"].get("duration", 0)))
            rate = Fraction(video.get("avg_frame_rate", "0/1"))
            if rate <= 0:
                rate = Fraction(video["r_frame_rate"])
            width, height = int(video["width"]), int(video["height"])
            sar = video.get("sample_aspect_ratio", "1:1")
            if sar not in ("N/A", "0:1"):
                width = round(width * Fraction(sar.replace(":", "/")))
            rotation = next(
                (s.get("rotation", 0) for s in video.get("side_data_list", []) if "rotation" in s),
                0,
            )
            if abs(round(float(rotation))) % 180 == 90:
                width, height = height, width
            if (
                not math.isfinite(duration)
                or duration <= 0
                or min(width, height) <= 0
                or not 0 < rate <= 240
            ):
                raise ValueError("Invalid video dimensions, duration or frame rate")
        except (ValueError, KeyError, TypeError, StopIteration, ZeroDivisionError) as error:
            raise RenderError(tr("Could not read video: {path}", path=path)) from error
        videos.append(
            VideoInfo(path, duration, streams, width + width % 2, height + height % 2, rate)
        )
    return videos


def can_stream_copy(videos: Sequence[VideoInfo]) -> bool:
    """Conservative compatibility check for MP4 exports, including codec configuration."""
    fields = (
        "codec_type",
        "codec_name",
        "codec_tag_string",
        "profile",
        "level",
        "width",
        "height",
        "pix_fmt",
        "sample_aspect_ratio",
        "r_frame_rate",
        "avg_frame_rate",
        "time_base",
        "sample_fmt",
        "sample_rate",
        "channels",
        "channel_layout",
        "extradata_hash",
        "color_range",
        "color_space",
        "color_transfer",
        "color_primaries",
        "field_order",
        "side_data_list",
    )
    signatures = []
    for video in videos:
        kinds = [s.get("codec_type") for s in video.streams]
        if (
            kinds.count("video") != 1
            or kinds.count("audio") > 1
            or any(k not in ("video", "audio") for k in kinds)
        ):
            return False
        for stream in video.streams:
            if stream.get("codec_name") not in ("h264", "hevc", "aac") or not stream.get(
                "extradata_hash"
            ):
                return False
        signatures.append([{key: s.get(key) for key in fields} for s in video.streams])
    return len(signatures) >= 2 and all(s == signatures[0] for s in signatures[1:])


def _run_with_progress(command, cancel, progress_path, duration, progress):
    command[1:1] = ["-nostdin", "-nostats", "-stats_period", "0.2", "-progress", str(progress_path)]
    with progress_path.open("w+", encoding="utf-8") as handle:

        def poll():
            while True:
                position = handle.tell()
                line = handle.readline()
                if not line.endswith("\n"):
                    handle.seek(position)
                    break
                key, _, value = line.strip().partition("=")
                if key == "out_time_us":
                    try:
                        progress(max(0, min(1, int(value) / (duration * 1_000_000))))
                    except ValueError:
                        pass

        result = _run_render(command, cancel, poll)
    if result.returncode:
        raise RenderError(tr("Could not combine videos:\n{detail}", detail=result.stderr[-3000:]))


def combine_videos(
    videos: Sequence[VideoInfo],
    output: Path,
    *,
    convert: bool = False,
    cancel: Event | None = None,
    progress: Callable[[int], None] | None = None,
) -> None:
    cancel = cancel if cancel is not None else Event()
    if cancel.is_set():
        raise RenderCancelled()
    if len(videos) < 2:
        raise RenderError(tr("Select at least two videos."))
    output = output.resolve()
    for video in videos:
        if not video.path.is_file():
            raise RenderError(tr("Could not read video: {path}", path=video.path))
    if any(
        output == v.path.resolve() or (output.exists() and output.samefile(v.path)) for v in videos
    ):
        raise RenderError(tr("The combined video must be different from every input video."))
    if not convert and not can_stream_copy(videos):
        raise RenderError(tr("These videos need conversion to a common format."))
    ffmpeg = find_media_tool("ffmpeg")
    if not ffmpeg:
        raise RenderError(tr("FFmpeg was not found in the application bundle or on PATH"))
    last = -1

    def report(value):
        nonlocal last
        value = min(99, int(value))
        if value > last:
            last = value
            if progress:
                progress(value)

    report(0)
    total = sum(v.duration for v in videos)
    with TemporaryDirectory(prefix=".kyykka-combine-", dir=output.parent) as directory:
        work = Path(directory)
        sources = [v.path for v in videos]
        if convert:
            first = videos[0]
            audio = any(v.has_audio for v in videos)
            sources = []
            elapsed = 0
            for index, video in enumerate(videos):
                target = work / f"part-{index}.mp4"
                command = [ffmpeg, "-y", "-v", "error", "-i", str(video.path)]
                if audio and not video.has_audio:
                    command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                command += [
                    "-map",
                    "0:V:0",
                    "-vf",
                    (
                        f"scale=iw*sar:ih,setsar=1,scale={first.width}:{first.height}:"
                        "force_original_aspect_ratio=decrease:force_divisible_by=2,"
                        f"pad={first.width}:{first.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                        f"fps={first.rate},format=yuv420p"
                    ),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-video_track_timescale",
                    "90000",
                ]
                if audio:
                    command += [
                        "-map",
                        "0:a:0" if video.has_audio else "1:a:0",
                        "-af",
                        "aresample=48000,apad",
                        "-c:a",
                        "aac",
                        "-ar",
                        "48000",
                        "-ac",
                        "2",
                        "-b:a",
                        "192k",
                    ]
                command += [
                    "-map_metadata",
                    "-1",
                    "-map_chapters",
                    "-1",
                    "-t",
                    str(video.duration),
                    str(target),
                ]
                _run_with_progress(
                    command,
                    cancel,
                    work / "progress",
                    video.duration,
                    lambda fraction, elapsed=elapsed, duration=video.duration: report(
                        95 * (elapsed + duration * fraction) / total
                    ),
                )
                sources.append(target)
                elapsed += video.duration
        manifest = work / "inputs.ffconcat"
        manifest.write_text(
            "ffconcat version 1.0\n"
            + "".join("file '" + path.as_posix().replace("'", "'\\''") + "'\n" for path in sources),
            encoding="utf-8",
        )
        staged = work / "combined.mp4"
        command = [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-auto_convert",
            "0",
            "-i",
            str(manifest),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(staged),
        ]
        _run_with_progress(
            command,
            cancel,
            work / "progress",
            total,
            lambda fraction: report(95 + 4 * fraction if convert else 99 * fraction),
        )
        if cancel.is_set():
            raise RenderCancelled()
        staged.replace(output)
    if progress:
        progress(100)
