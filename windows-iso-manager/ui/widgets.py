"""Reusable UI widgets."""
import tkinter as tk


class Semaphore(tk.Canvas):
    """Simple traffic-light indicator."""

    COLORS = {"ok": "green", "warn": "orange", "error": "red", "idle": "grey"}

    def __init__(self, master, **kw):
        super().__init__(master, width=40, height=40, highlightthickness=0, **kw)
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        self.delete("all")
        self.create_oval(
            5, 5, 35, 35,
            fill=self.COLORS.get(state, "grey"),
            outline="black",
        )
