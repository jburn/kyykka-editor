import csv
from moviepy import *
from insert_game import InsertGame

VIDEO_FILE = "vid.mp4"
OUTPUT_FILE = "output.mp4"
TIMESTAMPS_FILE = "throws.csv"

PRE = 4.0  # seconds before throw
POST = 3.0  # seconds after throw

debug = {'date': '10.12.1999', 'subtitle': 'Subtitle', 'names': ('Team1', 'Team2'), 'scores': ((11, 21), (12, 22)), 'throws': [[('Team1', 'a', '1'), ('Team1', 'a', '2'), ('Team1', 'b', '3'), ('Team1', 'b', '4'), ('Team2', 'c', '5'), ('Team2', 'c', '6'), ('Team2', 'd', '7'), ('Team2', 'd', '8'), ('Team1', 'f', '11'), ('Team1', 'f', '12'), ('Team2', 'g', '13'), ('Team2', 'g', '14'), ('Team2', 'h', '15'), ('Team2', 'h', '16'), ('Team1', 'a', '17'), ('Team1', 'a', '18'), ('Team1', 'b', '19'), ('Team1', 'b', '20'), ('Team2', 'c', '21'), ('Team2', 'c', '22'), ('Team2', 'd', '23'), ('Team2', 'd', '24'), ('Team1', 'f', '27'), ('Team1', 'f', '28'), ('Team2', 'g', '29'), ('Team2', 'g', '30'), ('Team2', 'h', '31'), ('Team2', 'h', '32')], [('Team2', 'c', '33'), ('Team2', 'c', '34'), ('Team2', 'd', '35'), ('Team2', 'd', '36'), ('Team1', 'a', '37'), ('Team1', 'a', '38'), ('Team1', 'b', '39'), ('Team1', 'b', '40'), ('Team2', 'g', '41'), ('Team2', 'g', '42'), ('Team2', 'h', '43'), ('Team2', 'h', '44'), ('Team1', 'f', '47'), ('Team1', 'f', '48'), ('Team2', 'c', '49'), ('Team2', 'c', '50'), ('Team2', 'd', '51'), ('Team2', 'd', '52'), ('Team1', 'a', '53'), ('Team1', 'a', '54'), ('Team1', 'b', '55'), ('Team1', 'b', '56'), ('Team2', 'g', '57'), ('Team2', 'g', '58'), ('Team2', 'h', '59'), ('Team2', 'h', '60'), ('Team1', 'f', '63'), ('Team1', 'f', '64')]]}

def build_scoreboard(base_clip, ):
    pass

def main():
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

    video = VideoFileClip(VIDEO_FILE)
    duration = video.duration

    clips = []

    for i, t in enumerate(timestamps, start=1):
        start = max(0, t - PRE)
        end = min(duration, t + POST)

        #scoreboard = 

        clip = video.subclipped(start, end)
        clips.append(clip)

        print(f"Throw {i}: {start:.2f}s → {end:.2f}s")

    final = concatenate_videoclips(clips, method="compose")

    final.write_videofile(
        OUTPUT_FILE,
        codec="libx264",
        audio_codec="aac",
        threads=4
    )

if __name__ == "__main__":
    app = InsertGame()
    app.mainloop()
    print(app.output)
