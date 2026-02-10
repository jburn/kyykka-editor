import cv2
import csv

VIDEO_FILE = "vid.mp4"
OUTPUT_CSV = "throws.csv"
DISPLAY_SCALE = 0.6  # 60% of original size
SKIP_SECONDS = 5.0

def seek(cap, delta_seconds):
    current = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
    target = max(0.0, current + delta_seconds)
    cap.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)


cap = cv2.VideoCapture(VIDEO_FILE)

if not cap.isOpened():
    raise RuntimeError("Could not open video")

fps = cap.get(cv2.CAP_PROP_FPS)

timestamps = []
playing = True

print("Controls:")
print("  Space = log throw impact")
print("  p     = pause / resume")
print("  Esc   = quit and save")

while True:
    if playing:
        ret, frame = cap.read()
        if not ret:
            break

    pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
    pos_s = pos_ms / 1000.0

    display = frame.copy()
    cv2.putText(
        display,
        f"Time: {pos_s:.2f}s",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )

    if DISPLAY_SCALE != 1.0:
        display = cv2.resize(
            display,
            None,
            fx=DISPLAY_SCALE,
            fy=DISPLAY_SCALE,
            interpolation=cv2.INTER_AREA
            )

    cv2.imshow("Kyykka Timestamp Logger", display)

    key = cv2.waitKeyEx(30)

    if key == 27:  # ESC
        break

    elif key == ord("p"):
        playing = not playing

    elif key == 32:  # SPACE
        timestamps.append(pos_s)
        print(f"Logged throw at {pos_s:.2f}s")

    elif key == 2424832:  # LEFT ARROW
        seek(cap, -SKIP_SECONDS)

    elif key == 2555904:  # RIGHT ARROW
        seek(cap, SKIP_SECONDS)


cap.release()
cv2.destroyAllWindows()

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["throw_index", "timestamp"])
    for i, t in enumerate(timestamps, start=1):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        writer.writerow([i, f"{h:02d}:{m:02d}:{s:05.2f}"])

print(f"Saved {len(timestamps)} throws to {OUTPUT_CSV}")
