import array
import shutil
import subprocess

import pytest
from PySide6.QtWidgets import QDialog

from kyykka_editor.app import EditMarkDialog
from kyykka_editor.model import EditorProject, Impact
from kyykka_editor.render import render_highlights
from kyykka_editor.storage import read_project, write_project


def test_sound_is_per_throw_and_persists(qapp, tmp_path):
    project = EditorProject(
        impacts=[
            Impact(1000, sound_path=str(tmp_path / "sound.wav"), sound_at="start"),
            Impact(2000),
        ]
    )
    path = tmp_path / "project.kyykka"
    write_project(path, project)
    loaded = read_project(path)
    assert loaded.impacts[0].sound_path == project.impacts[0].sound_path
    assert loaded.impacts[0].sound_at == "start"
    assert loaded.impacts[1].sound_path == ""
    dialog = EditMarkDialog(
        1000, 0, 0, 5000, [], "", sound_path=project.impacts[0].sound_path, sound_at="start"
    )
    assert dialog.sound_position.currentData() == "start"
    dialog._remove_sound()
    assert dialog.sound_path == ""
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected


@pytest.mark.integration
@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
@pytest.mark.parametrize("placement", ["start", "impact"])
def test_effect_timing_and_no_leak_into_next_throw(qapp, tmp_path, placement):
    ffmpeg = shutil.which("ffmpeg")
    source, effect, output = (
        tmp_path / name for name in ("source.mp4", "effect.wav", "output.mp4")
    )
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=25:d=12",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=10", str(effect)],
        check=True,
        capture_output=True,
    )
    project = EditorProject(
        video_path=str(source),
        pre_roll_ms=500,
        post_roll_ms=500,
        impacts=[Impact(3000, sound_path=str(effect), sound_at=placement), Impact(9000)],
    )
    render_highlights(project, output, 12000)

    def peak(start):
        result = subprocess.run(
            [
                ffmpeg,
                "-ss",
                str(start),
                "-i",
                str(output),
                "-t",
                "0.2",
                "-f",
                "s16le",
                "-ac",
                "1",
                "-ar",
                "48000",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        )
        samples = array.array("h", result.stdout)
        return max(abs(value) for value in samples)

    assert peak(3.1) > 100
    assert peak(0.5) > 100 if placement == "start" else peak(0.5) < 10
    assert peak(4.0) < 10
