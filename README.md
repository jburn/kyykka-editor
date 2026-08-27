# Kyykka Editor

Copyright © 2026 jburn and contributors.

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

## Build a distributable Windows application

Install the development dependencies and run the packaging script:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
.\packaging\build.ps1
```

The script discovers `ffmpeg.exe` and `ffprobe.exe` from `PATH` and creates
`dist\KyykkaEditor`. You can select a particular FFmpeg distribution instead:

```powershell
.\packaging\build.ps1 -FFmpegBin C:\ffmpeg\bin
```

Share the complete `dist\KyykkaEditor` directory, not just `KyykkaEditor.exe`.
The application uses its bundled FFmpeg tools and only falls back to `PATH` in a
development installation. Review [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
before distributing the package.

## License

Kyykka Editor is free software licensed under the
[GNU General Public License, version 3 or later](LICENSE). You may use, study,
share, and modify it under the terms of that license. Distributed builds also
contain separately licensed components; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

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
