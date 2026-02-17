import tkinter as tk
from tkinter import filedialog
import cv2

DISPLAY_SCALE = 0.6
SKIP_SECONDS = 5.0


def seek(cap, delta_seconds):
    current = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
    target = max(0.0, current + delta_seconds)
    cap.set(cv2.CAP_PROP_POS_MSEC, target * 1000.0)


def pick_video_file():
    """Open file dialog and return selected video path or None."""
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.m4v"),
            ("All files", "*.*")
        ]
    )

    root.destroy()
    return file_path or None


def log_video_timestamps(video_file=None):
    """
    Run timestamp logger.

    Returns:
        list[float]: timestamps in seconds
    """

    if video_file is None:
        video_file = pick_video_file()

    if not video_file:
        return []

    cap = cv2.VideoCapture(video_file)

    if not cap.isOpened():
        raise RuntimeError("Could not open video")

    timestamps = []
    playing = True
    frame = None

    print("Controls:")
    print("  Space = log throw impact")
    print("  p     = pause / resume")
    print("  Esc   = quit")
    print("  ->    = skip 5s ahead")
    print("  <-    = skip 5s behind")

    while True:
        if playing:
            ret, frame = cap.read()
            if not ret:
                break

        if frame is None:
            continue

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

        cv2.imshow("Timestamp Logger", display)

        if cv2.getWindowProperty("Timestamp Logger", cv2.WND_PROP_VISIBLE) < 1:
            break

        key = cv2.waitKeyEx(30)

        if key == 27:  # ESC
            break

        elif key == ord("p"):
            playing = not playing

        elif key == 32:  # SPACE
            timestamps.append(pos_s)
            print(f"Logged at {pos_s:.2f}s")

        elif key == 2424832:  # LEFT
            seek(cap, -SKIP_SECONDS)

        elif key == 2555904:  # RIGHT
            seek(cap, SKIP_SECONDS)

    cap.release()
    cv2.destroyAllWindows()

    return video_file, timestamps
