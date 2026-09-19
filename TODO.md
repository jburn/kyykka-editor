# TODO

## High-priority fixes

- [ ] Preserve the recovery file when recovery fails or locating the source video is cancelled. Delete it only after successful recovery or explicit discard. Add regression coverage for failed recovery followed by closing the app.
- [ ] Prevent large highlight exports from exceeding Windows' command-line limit. Move the FFmpeg filter graph into a file and check whether inputs also need batching. Test realistic match sizes, including 96 throws with player overlays and long file paths.

## Correctness and reliability

- [ ] Respect rotation metadata and sample aspect ratio when rendering highlights so portrait and anamorphic videos retain their proportions. Share source-dimension handling with Combine videos and add rotated-video coverage.
- [ ] Preserve playback position and paused/playing state when saving Match details without changing the source video. Avoid reloading the video for title, roster, or score edits.
- [ ] Automatically add `.mp4` when the highlight export filename has no extension, matching Combine videos. Test an extensionless filename.
- [ ] Make initial FFprobe calls cancellable and give them a timeout so cancelling an export also interrupts media probing.
- [ ] Isolate application settings and recovery paths across the entire test suite. Tests must not read or overwrite the developer's saved preferences, hotkeys, or workspace state.
- [ ] Preserve millisecond timing overrides when editing other throw fields, or consistently reject unsupported precision when loading projects. Test that a valid 1500 ms override is not silently changed to 1000 ms.

## Documentation cleanup

- [ ] Use one virtual-environment directory name consistently in README setup and build instructions, and list FFprobe alongside FFmpeg in the requirements.
- [ ] Update README screen-background options to match the separate Color and Image choices, and fix the `Settings ? Preferences?` text.
- [ ] Refresh README screenshots to show the current layout and the timing controls under Preferences.
- [ ] Correct the FFmpeg vendor instructions: `build.ps1` currently requires tools on PATH or an explicit `-FFmpegBin`; merely placing them in `vendor/ffmpeg/bin` is insufficient.
- [ ] Make the bundled FFmpeg description consistent: About refers to the Gyan full build, while CI packages essentials.

## Further improvements

- [ ] Expand rendering integration coverage beyond one or two throws to include realistic match sizes and the export edge cases above.
- [ ] Make editing the current project's screen styles more direct. Screen settings currently starts from application defaults even when the open project has different styles.
- [ ] Gradually separate project persistence, playback, and dialogs from `app.py` to reduce coupling and simplify regression testing.
