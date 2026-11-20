"""Renderização em cache de ícones vetoriais Lucide armazenados em assets/icons/."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

ICONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "icons"


@st.cache_data(show_spinner=False)
def load_lucide_svg(name: str, *, size: int = 20, color: str = "currentColor") -> str:
    """Lê um ícone SVG de assets/icons/<name>.svg e aplica tamanho e cor."""
    path = ICONS_DIR / f"{name}.svg"
    if not path.exists():
        return ""
    svg = path.read_text(encoding="utf-8").strip()
    svg = svg.replace('width="24"', f'width="{size}"').replace('height="24"', f'height="{size}"')
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    return svg
