"""Carregamento em cache de assets estáticos (imagens e SVGs) em data URI."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets"

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


@st.cache_data(show_spinner=False)
def get_asset_data_uri(filename: str) -> str | None:
    """Lê um arquivo em assets/ e retorna como data URI base64 em cache."""
    path = ASSETS_DIR / filename
    if not path.exists():
        return None
    mime = _MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
