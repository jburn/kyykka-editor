# Kyykka Editor

A desktop application for marking impacts in a kyykka match video and rendering
a compact highlight video around those moments.

## Features

- Integrated video playback and scrubbing
- Visible controls for every marking action
- Keyboard shortcuts mirroring the graphical controls
- Editable impact list
- Four-second title screen using the match title and team names
- Timeline events for the round-one result and final result/winner screens
- Persistent bottom-left thrower-name overlay on each marked highlight
- Match setup dialog for title, video, teams, scores, and player rosters
- Custom OAMK application and Windows icon
- FFmpeg-based highlight rendering

## Requirements

- Python 3.11 or newer
- FFmpeg available on `PATH` for exporting videos

## Install and run

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
kyykka-editor
```

The installed `kyykka-editor` command launches as a GUI application on Windows,
without opening a console for Qt/FFmpeg backend diagnostics. Run `python main.py`
only when those diagnostics are useful during development.

For development, install `.[dev]` and run:

```powershell
ruff format --check .
ruff check .
pytest -m "not integration"
pytest -m integration
```

Integration tests generate a small video, render a complete highlight with the
real FFmpeg executable, and inspect the result with FFprobe. They require both
programs on `PATH`. The same checks run on Windows in GitHub Actions.

## Controls

| Action | Button | Shortcut |
| --- | --- | --- |
| Play or pause | Play/Pause | Space |
| Mark impact | Mark impact | M |
| Undo latest mark | Undo | Ctrl+Z |
| Seek backward 3 seconds | -3 s | Left arrow |
| Seek forward 5 seconds | +5 s | Right arrow |
| Remove selected mark | Remove | Delete |

All primary actions are available as buttons; shortcuts are supporting controls.
