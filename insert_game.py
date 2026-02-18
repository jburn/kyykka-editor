import tkinter as tk
from tkinter import ttk


class GameType(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Kyykkä-editor")
        self.output = None

        ttk.Label(self, text="Choose game type").pack(pady=10, padx=10)
        
        self.combo = ttk.Combobox(self, values=["1. Talvijoukkuepeli (pöytäkirjallinen)",
                                   "2. Talvijoukkuepeli",
                                   "3. Henkkari-/Paripeli",
                                   "4. Kesäjoukkuepeli"],
                                   width=32,
                                   state="readonly")
        self.combo.current(0)
        self.combo.pack(pady=10, padx=10)

        ttk.Button(self, text="Continue", command=self._submit).pack(pady=10, padx=10)

    def _submit(self):
        value = self.combo.get()
        self.output = int(value[0])
        self.destroy()


class InsertGame(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Kyykkä score insert")
        self.subtitle = tk.StringVar()
        self.date = tk.StringVar()

        self.team1_name = tk.StringVar()
        self.team2_name = tk.StringVar()

        self.team1 = [[[tk.StringVar() for _ in range(5)] for _ in range(4)] for _ in range(2)]
        self.team2 = [[[tk.StringVar() for _ in range(5)] for _ in range(4)] for _ in range(2)]

        self.team1_score = [tk.IntVar(), tk.IntVar()]
        self.team2_score = [tk.IntVar(), tk.IntVar()]

        self.output = None

        self._build_ui()

    def _submit(self):
        def _get_round1_scores():

            throws = []

            for row in self.team1[0][:2]:
                for val in row[1:3]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            for row in self.team2[0][:2]:
                for val in row[1:3]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            for row in self.team1[0][2:]:
                for val in row[1:3]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            for row in self.team2[0][2:]:
                for val in row[1:3]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))


            for row in self.team1[0][:2]:
                for val in row[3:5]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            for row in self.team2[0][:2]:
                for val in row[3:5]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            for row in self.team1[0][2:]:
                for val in row[3:5]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            for row in self.team2[0][2:]:
                for val in row[3:5]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            return throws

        def _get_round2_scores():
            throws = []

            for row in self.team2[1][:2]:
                for val in row[1:3]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            for row in self.team1[1][:2]:
                for val in row[1:3]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            for row in self.team2[1][2:]:
                for val in row[1:3]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            for row in self.team1[1][2:]:
                for val in row[1:3]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))


            for row in self.team2[1][:2]:
                for val in row[3:5]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            for row in self.team1[1][:2]:
                for val in row[3:5]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            for row in self.team2[1][2:]:
                for val in row[3:5]:
                    throws.append((self.team2_name.get(), row[0].get(), val.get()))

            for row in self.team1[1][2:]:
                for val in row[3:5]:
                    throws.append((self.team1_name.get(), row[0].get(), val.get()))

            return throws

        throws = []

        throws.append([throw for throw in _get_round1_scores() if throw[1] != 'e'])
        throws.append([throw for throw in _get_round2_scores() if throw[1] != 'e'])

        self.output = {
            "date": self.date.get(),
            "subtitle": self.subtitle.get(),
            "names": (self.team1_name.get(), self.team2_name.get()),
            "scores": ((self.team1_score[0].get(), self.team1_score[1].get()),
                       (self.team2_score[0].get(), self.team2_score[1].get())),
            "throws": throws
        }

        #print(self.output)
        self.destroy()

    def _build_ui(self):
        # Row 0
        ttk.Label(self, text="Subtitle:").grid(
            row=0, column=0, padx=0, pady=10, sticky="e"
        )
        ttk.Entry(self, textvariable=self.subtitle).grid(
            row=0, column=1, padx=0, pady=10, sticky="w"
        )

        ttk.Label(self, text="Date:").grid(
            row=0, column=2, padx=0, pady=10, sticky="e"
        )
        ttk.Entry(self, textvariable=self.date).grid(
            row=0, column=3, padx=0, pady=10, sticky="w"
        )

        # Row 1
        ttk.Label(self, text="Team 1 name:").grid(
            row=1, column=0, padx=5, pady=10, sticky="ne"
        )
        ttk.Entry(self, textvariable=self.team1_name).grid(
            row=1, column=1, padx=0, pady=10, sticky="nw"
        )

        ttk.Label(self, text="Team 2 name:").grid(
            row=1, column=2, padx=5, pady=10, sticky="ne",
        )
        ttk.Entry(self, textvariable=self.team2_name).grid(
            row=1, column=3, padx=0, pady=10, sticky="nw"
        )

        # Row 2
        ttk.Label(self, text="Player name").grid(
            row=2, column=0, padx=10, pady=0, sticky="s"
        )
        for n in range(4):
            ttk.Label(self, text=f"Throw{n+1}").grid(
                row=2, column=n+1, padx=10, pady=0, sticky="s"
            )

        # Row 3
        ttk.Label(self, text="Team 1 throwing").grid(
            row=3, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 4
        for i, txtvar in enumerate(self.team1[0][0]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=4, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 5
        for i, txtvar in enumerate(self.team1[0][1]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=5, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 6
        ttk.Label(self, text="Team 2 throwing").grid(
            row=6, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 7
        for i, txtvar in enumerate(self.team2[0][0]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=7, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 8
        for i, txtvar in enumerate(self.team2[0][1]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=8, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 9
        ttk.Label(self, text="Team 1 throwing").grid(
            row=9, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 10
        for i, txtvar in enumerate(self.team1[0][2]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=10, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 11
        for i, txtvar in enumerate(self.team1[0][3]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=11, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 12
        ttk.Label(self, text="Team 2 throwing").grid(
            row=12, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 13
        for i, txtvar in enumerate(self.team2[0][2]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=13, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 14
        for i, txtvar in enumerate(self.team2[0][3]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=14, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 15
        ttk.Label(self, text="Round 1 results:").grid(
            row=15, column=0, padx=5, pady=20, sticky="e"
        )

        ttk.Label(self, text="Team 1:").grid(
            row=15, column=1, padx=0, pady=20, sticky="e"
        )
        ttk.Entry(self, textvariable=self.team1_score[0]).grid(
            row=15, column=2, padx=0, pady=20, sticky="w"
        )

        ttk.Label(self, text="Team 2:").grid(
            row=15, column=3, padx=0, pady=20, sticky="e",
        )
        ttk.Entry(self, textvariable=self.team2_score[0]).grid(
            row=15, column=4, padx=0, pady=20, sticky="w"
        )

        # Row 16
        ttk.Label(self, text="Player name").grid(
            row=16, column=0, padx=10, pady=0, sticky="s"
        )
        for n in range(4):
            ttk.Label(self, text=f"Throw{n+1}").grid(
                row=16, column=n+1, padx=10, pady=0, sticky="s"
            )

        # Row 17
        ttk.Label(self, text="Team 2 throwing").grid(
            row=17, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 18
        for i, txtvar in enumerate(self.team2[1][0]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=18, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 19
        for i, txtvar in enumerate(self.team2[1][1]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=19, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 20
        ttk.Label(self, text="Team 1 throwing").grid(
            row=20, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 21
        for i, txtvar in enumerate(self.team1[1][0]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=21, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 22
        for i, txtvar in enumerate(self.team1[1][1]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=22, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 23
        ttk.Label(self, text="Team 2 throwing").grid(
            row=23, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 24
        for i, txtvar in enumerate(self.team2[1][2]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=24, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 25
        for i, txtvar in enumerate(self.team2[1][3]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=25, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 26
        ttk.Label(self, text="Team 1 throwing").grid(
            row=26, column=0, padx=10, pady=0, columnspan=5, sticky="w"
        )

        # Row 27
        for i, txtvar in enumerate(self.team1[1][2]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=27, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 28
        for i, txtvar in enumerate(self.team1[1][3]):
            ttk.Entry(self, textvariable=txtvar).grid(
                row=28, column=i, padx=10, pady=0, sticky="w"
            )

        # Row 29
        ttk.Label(self, text="Round 2 results:").grid(
            row=29, column=0, padx=5, pady=20, sticky="e"
        )

        ttk.Label(self, text="Team 1:").grid(
            row=29, column=1, padx=0, pady=20, sticky="e"
        )
        ttk.Entry(self, textvariable=self.team1_score[1]).grid(
            row=29, column=2, padx=0, pady=20, sticky="w"
        )

        ttk.Label(self, text="Team 2:").grid(
            row=29, column=3, padx=0, pady=20, sticky="e",
        )
        ttk.Entry(self, textvariable=self.team2_score[1]).grid(
            row=29, column=4, padx=0, pady=20, sticky="w"
        )

        # Row 30
        ttk.Button(self, text="Submit", command=self._submit).grid(
            row=30, column=2, padx=10, pady=20
        )
