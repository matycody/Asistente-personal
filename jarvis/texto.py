"""Normalización de texto, compartida por el parser y el índice."""
from __future__ import annotations

import re
import unicodedata


def norm(text: str) -> str:
    """Minúsculas, sin tildes y sin signos: así compara lo que decís con lo que hay."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9: ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
