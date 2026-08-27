# FFmpeg packaging input

You do not need to commit FFmpeg binaries here. The packaging script normally discovers
`ffmpeg.exe` and `ffprobe.exe` from `PATH`.

Alternatively, place both executables in `vendor/ffmpeg/bin`, or pass their directory directly:

```powershell
.\packaging\build.ps1 -FFmpegBin C:\ffmpeg\bin
```

Before distributing a build, retain the FFmpeg provider's license/build information and comply
with the license that applies to those binaries.
