# TODO

## Correctness and reliability

- [x] Respect rotation metadata and sample aspect ratio when rendering highlights so portrait and anamorphic videos retain their proportions. Share source-dimension handling with Combine videos and add rotated-video coverage.
- [x] Preserve playback position and paused/playing state when saving Match details without changing the source video. Avoid reloading the video for title, roster, or score edits.
- [x] Automatically add `.mp4` when the highlight export filename has no extension, matching Combine videos. Test an extensionless filename.
- [x] Isolate application settings and recovery paths across the entire test suite. Tests must not read or overwrite the developer's saved preferences, hotkeys, or workspace state.


## Documentation cleanup

- [ ] Use one virtual-environment directory name consistently in README setup and build instructions, and list FFprobe alongside FFmpeg in the requirements.
- [ ] Update README screen-background options to match the separate Color and Image choices, and fix the `Settings ? Preferences?` text.
- [ ] Refresh README screenshots to show the current layout and the timing controls under Preferences.
- [ ] Correct the FFmpeg vendor instructions: `build.ps1` currently requires tools on PATH or an explicit `-FFmpegBin`; merely placing them in `vendor/ffmpeg/bin` is insufficient.
- [ ] Make the bundled FFmpeg description consistent: About refers to the Gyan full build, while CI packages essentials.
