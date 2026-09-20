# FFmpeg packaging input

You do not need to commit FFmpeg binaries here. The packaging script normally discovers
`ffmpeg.exe` and `ffprobe.exe` from `PATH`.

Alternatively, pass the directory containing both executables explicitly:

```powershell
.\packaging\build.ps1 -FFmpegBin C:\ffmpeg\bin
```

If you place the executables in `vendor/ffmpeg/bin`, pass that directory too:

```powershell
.\packaging\build.ps1 -FFmpegBin .\vendor\ffmpeg\bin
```

The build script does not automatically search the vendor directory. Run these
commands from the repository root.

Before distributing a build, retain the FFmpeg provider's license/build information and comply
with the license that applies to those binaries.
