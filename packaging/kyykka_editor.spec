from pathlib import Path
import os


spec_location = Path(SPECPATH).resolve()
project_root = spec_location.parent if spec_location.suffix else spec_location
project_root = project_root.parent
ffmpeg_bin = Path(os.environ.get("KYYKKA_FFMPEG_BIN", project_root / "vendor/ffmpeg/bin"))

required_tools = [ffmpeg_bin / "ffmpeg.exe", ffmpeg_bin / "ffprobe.exe"]
missing_tools = [str(path) for path in required_tools if not path.is_file()]
if missing_tools:
    raise SystemExit("Missing packaging binaries: " + ", ".join(missing_tools))

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root / "src")],
    binaries=[(str(path), "kyykka_editor/bin") for path in required_tools],
    datas=[
        (str(project_root / "src/kyykka_editor/assets"), "kyykka_editor/assets"),
        (str(project_root / "THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KyykkaEditor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project_root / "src/kyykka_editor/assets/kyykka-editor.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="KyykkaEditor",
)
