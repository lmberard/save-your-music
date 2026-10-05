#!/usr/bin/env python3
"""Turns a title into a simple file name: lowercase, ASCII and hyphens.

"RÜFÜS DU SOL - The Life (Official Audio)" -> "rufus-du-sol-the-life"
Usage: slug.py "<text>"
"""
import re
import sys
import unicodedata


def slug(text, max_len=80):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))  # ü -> u
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)  # (Official Audio), [Visualizer], (4K)...
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text[:max_len].strip("-")


if __name__ == "__main__":
    print(slug(" ".join(sys.argv[1:])))
