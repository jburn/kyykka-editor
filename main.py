import csv
from moviepy import *

VIDEO_FILE = "vid.mp4"
OUTPUT_FILE = "throws_only.mp4"
TIMESTAMPS_FILE = "throws.csv"

PRE = 4.0  # seconds before throw
POST = 3.0  # seconds after throw


# --------------------
# Load timestamps
# --------------------
timestamps = []

with open(TIMESTAMPS_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        t = row["timestamp"]
        h, m, s = t.split(":")
        seconds = int(h) * 3600 + int(m) * 60 + float(s)
        timestamps.append(seconds)

if not timestamps:
    raise RuntimeError("No timestamps found")

# --------------------
# Load video
# --------------------
video = VideoFileClip(VIDEO_FILE)
duration = video.duration

clips = []

# --------------------
# Create clips
# --------------------
for i, t in enumerate(timestamps, start=1):
    start = max(0, t - PRE)
    end = min(duration, t + POST)

    clip = video.subclipped(start, end)
    clips.append(clip)

    print(f"Throw {i}: {start:.2f}s → {end:.2f}s")

# --------------------
# Concatenate and export
# --------------------
final = concatenate_videoclips(clips, method="compose")

final.write_videofile(
    OUTPUT_FILE,
    codec="libx264",
    audio_codec="aac",
    threads=4
)