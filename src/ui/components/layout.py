"""Helpers de layout, formatação brasileira, barra lateral e controle de acesso nas páginas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import streamlit as st

from src.auth.google_auth import get_current_user
from src.auth.permissions import can_access_module, has_permission

TZ_SP = ZoneInfo("America/Sao_Paulo")


def fmt_brl(value: float | int | Decimal | None) -> str:
    """Formata número como moeda brasileira (R$ 1.234,56)."""
    if value is None:
        return "R$ 0,00"
    num = float(value)
    sinal = "-" if num < 0 else ""
    formatted = f"{abs(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {formatted}"


def fmt_qty(value: float | int | Decimal | None, unidade: str = "") -> str:
    if value is None:
        return f"0 {unidade}".strip()
    num = float(value)
    if num.is_integer():
        base = f"{int(num):,}".replace(",", ".")
    else:
        base = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{base} {unidade}".strip()


def fmt_datetime(value: datetime | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    dt = value.astimezone(TZ_SP) if value.tzinfo else value
    return dt.strftime("%d/%m/%Y %H:%M")


def fmt_date(value: date | datetime | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return fmt_datetime(value)[:10]
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def fmt_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    total = int(round(float(seconds)))
    mins, secs = divmod(total, 60)
    if mins == 0:
        return f"{secs}s"
    return f"{mins}m {secs:02d}s"


def render_sidebar_user_card(user: dict[str, Any]) -> None:
    """Exibe informações do usuário autenticado via Google e botão de logout na sidebar."""
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"**👤 {user.get('nome', 'Usuário')}**")
        st.caption(f"{user.get('email', '')}")
        st.caption(f"Perfil: `{user.get('perfil', 'GERENTE')}`")
        if st.button("🚪 Sair (Logout)", use_container_width=True, key="btn_sidebar_logout"):
            st.session_state.pop("current_user", None)
            st.logout()


def ensure_page_access(module_key: str) -> dict[str, Any]:
    """Garante usuário logado e autorizado a acessar o módulo atual."""
    user = get_current_user()
    if not user:
        st.warning("Sessão não encontrada. Faça login com sua conta Google.")
        st.stop()
    if not can_access_module(user["perfil"], module_key):
        st.error(
            f"Acesso restrito: seu perfil (`{user['perfil']}`) não tem permissão "
            f"para acessar este módulo."
        )
        st.stop()
    return user


def user_can(user: dict[str, Any], action: str) -> bool:
    return has_permission(user["perfil"], action)


def render_page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)
    st.divider()
