from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str, *, marker: str) -> None:
    text = read(path)
    if old in text:
        write(path, text.replace(old, new, 1))
        return
    if marker in text:
        return
    raise RuntimeError(f"Could not patch {path}: expected source block is missing")
