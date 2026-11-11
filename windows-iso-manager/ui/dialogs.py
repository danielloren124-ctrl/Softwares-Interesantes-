"""Custom dialogs."""
from tkinter import simpledialog


def ask_confirmation(parent, prompt: str, expected: str) -> bool:
    """Ask the user to type `expected` to confirm a risky action."""
    typed = simpledialog.askstring("Confirmar", prompt, parent=parent)
    return typed == expected
