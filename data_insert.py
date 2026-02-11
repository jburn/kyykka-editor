import tkinter as tk
from tkinter import ttk


class Spacer(tk.Frame):
    """
    A reusable invisible spacer for Tkinter layouts.
    Can be used with pack or grid.
    """
    def __init__(self, master=None, width=0, height=0, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        # Prevent the frame from shrinking
        self.pack_propagate(False)
        self.grid_propagate(False)

class InsertGame(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Kyykkä score insert")
        self.team1_name = tk.StringVar()
        self.team2_name = tk.StringVar()

        self.team1 = [[tk.StringVar() for _ in range(5)] for _ in range(4)]
        self.team2 = [[tk.StringVar() for _ in range(5)] for _ in range(4)]

        self._build_ui()

    def _build_ui(self):
        # Row 1
        Spacer().grid(
            row=0, column=0, padx=5, pady=10, sticky="e"
        )
        ttk.Label(self, text="Team 1 name").grid(
            row=0, column=1, padx=5, pady=10, sticky="e"
        )
        ttk.Entry(self, textvariable=self.team1_name).grid(
            row=0, column=2, padx=0, pady=10, sticky="w"
        )

        ttk.Label(self, text="Team 2 name").grid(
            row=0, column=3, padx=5, pady=10, sticky="e"
        )
        ttk.Entry(self, textvariable=self.team2_name).grid(
            row=0, column=4, padx=0, pady=10, sticky="w"
        )

        # Row 1
        ttk.Label(self, text="Player").grid(
            row=1, column=0, padx=10, pady=10, sticky="w"
        )
        for n in range(4):
            ttk.Label(self, text=f"Throw{n+1}").grid(
                row=1, column=n+1, padx=10, pady=10, sticky="e"
            )
        
        # Row 2
        ttk.Label(self, text="Team 1 throwing").grid(
            row=2, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 3
        for i, txtvar in enumerate(self.team1[0]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=3, column=i+1, padx=0, pady=10, sticky="w"
            )

        # Row 4
        for i, txtvar in enumerate(self.team1[1]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=4, column=i+1, padx=0, pady=10, sticky="w"
            )

        # Row 5
        ttk.Label(self, text="Team 2 throwing").grid(
            row=5, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 6
        for i, txtvar in enumerate(self.team2[0]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=6, column=i+1, padx=0, pady=10, sticky="w"
            )

        # Row 7
        for i, txtvar in enumerate(self.team2[1]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=7, column=i+1, padx=0, pady=10, sticky="w"
            )

        



if __name__ == "__main__":
    app = InsertGame()
    app.mainloop()