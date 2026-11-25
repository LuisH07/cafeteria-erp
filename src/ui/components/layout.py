"""Helpers de layout, formatação brasileira, barra lateral e controle de acesso nas páginas."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.auth.google_auth import get_current_user
from src.auth.permissions import can_access_module, has_permission
from src.ui.components.assets import get_asset_data_uri
from src.ui.components.icons import load_lucide_svg

TZ_SP = ZoneInfo("America/Sao_Paulo")


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def fmt_brl(value: float | int | Decimal | None) -> str:
    """Formata número como moeda brasileira (R$ 1.234,56)."""
    if _is_missing(value):
        return "R$ 0,00"
    num = float(value)
    if math.isnan(num):
        return "R$ 0,00"
    sinal = "-" if num < 0 else ""
    formatted = f"{abs(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {formatted}"


def fmt_qty(value: float | int | Decimal | None, unidade: str = "") -> str:
    if _is_missing(value):
        return f"0 {unidade}".strip()
    num = float(value)
    if num.is_integer():
        base = f"{int(num):,}".replace(",", ".")
    else:
        base = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{base} {unidade}".strip()


def fmt_datetime(value: datetime | str | None) -> str:
    if _is_missing(value):
        return "-"
    if isinstance(value, str):
        return value
    dt = value.astimezone(TZ_SP) if value.tzinfo else value
    return dt.strftime("%d/%m/%Y %H:%M")


def fmt_date(value: date | datetime | str | None) -> str:
    if _is_missing(value):
        return "-"
    if isinstance(value, datetime):
        return fmt_datetime(value)[:10]
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def fmt_seconds(seconds: float | int | None) -> str:
    if _is_missing(seconds):
        return "-"
    total = int(round(float(seconds)))
    mins, secs = divmod(total, 60)
    if mins == 0:
        return f"{secs}s"
    return f"{mins}m {secs:02d}s"


def inject_sidebar_theme() -> None:
    """Aplica gradiente marrom espresso escuro na sidebar e eleva um nível na escala de peso tipográfico."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400..800&display=swap');

        /* Escala tipográfica elevada (+1 nível: Regular->Medium, Medium->SemiBold, SemiBold->Bold, Bold->ExtraBold) */
        .stApp,
        .stApp p,
        .stApp li,
        .stApp input,
        .stApp textarea,
        .stApp select,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stCaptionContainer"] p,
        [data-testid="stDataFrame"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-weight: 500;
        }
        .stApp label,
        .stApp label p,
        .stApp button,
        .stApp button p,
        [data-baseweb="tab"] p,
        [data-testid="stMetricLabel"] p,
        [data-testid="stExpander"] summary p {
            font-weight: 600 !important;
        }
        .stApp h3,
        .stApp h4,
        .stApp strong,
        .stApp b,
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] > div {
            font-weight: 700 !important;
        }
        .stApp h1,
        .stApp h2 {
            font-weight: 800 !important;
        }

        /* Cards de métricas e containers com fundo branco limpo e borda café suave */
        [data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E6D8C8 !important;
            border-radius: 12px !important;
            padding: 0.85rem 1rem !important;
            box-shadow: 0 2px 8px rgba(44, 30, 22, 0.04) !important;
        }
        [data-testid="stMetricDelta"] {
            background-color: #F4EAE0 !important;
            color: #5C3A21 !important;
            border-radius: 999px !important;
            padding: 2px 8px !important;
        }
        [data-testid="stMetricDelta"] svg {
            fill: #6F4E37 !important;
            color: #6F4E37 !important;
        }
        [data-testid="stMetricDelta"] > div {
            color: #5C3A21 !important;
            font-weight: 600 !important;
        }

        /* Substitui alertas verde/azul pastel por brancos e marrons elegantes */
        [data-testid="stAlert"] > div,
        [data-testid="stAlertContainer"] {
            background-color: #FFFFFF !important;
            color: #2C1E16 !important;
            border: 1px solid #E2D2C0 !important;
            border-left: 4px solid #6F4E37 !important;
            border-radius: 10px !important;
            box-shadow: 0 2px 6px rgba(44, 30, 22, 0.04) !important;
        }
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] li,
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] span {
            color: #2C1E16 !important;
            font-weight: 440 !important;
        }
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] strong,
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] b {
            color: #2C1E16 !important;
            font-weight: 600 !important;
        }
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] code {
            color: #2C1E16 !important;
            font-weight: 500 !important;
        }
        [data-testid="stAlert"] svg {
            color: #6F4E37 !important;
            fill: #6F4E37 !important;
        }
        /* Diferenciação sutil por tipo usando apenas branco, creme e tons de marrom/terracota */
        [data-testid="stAlertContainer"].stAlertSuccess,
        div[data-baseweb="notification"][kind="positive"] {
            background-color: #FBF7F2 !important;
            border-color: #DFCBB5 !important;
            border-left: 4px solid #8C5A34 !important;
        }
        [data-testid="stAlertContainer"].stAlertInfo,
        div[data-baseweb="notification"][kind="info"] {
            background-color: #FFFFFF !important;
            border-color: #E4D6C6 !important;
            border-left: 4px solid #5C3A21 !important;
        }
        [data-testid="stAlertContainer"].stAlertWarning,
        div[data-baseweb="notification"][kind="warning"] {
            background-color: #F8EFE4 !important;
            border-color: #D8BA96 !important;
            border-left: 4px solid #A66E38 !important;
        }
        [data-testid="stAlertContainer"].stAlertError,
        div[data-baseweb="notification"][kind="negative"] {
            background-color: #FAF2EF !important;
            border-color: #DEBDB3 !important;
            border-left: 4px solid #7A2E20 !important;
        }

        /* Sidebar marrom espresso escuro com gradiente */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #2B1810 0%, #3E2419 48%, #1C0F0A 100%) !important;
            border-right: 1px solid rgba(217, 165, 114, 0.20) !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            background: transparent !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
        [data-testid="stSidebar"] label {
            color: #F5ECE4 !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            color: #CBB39E !important;
            font-weight: 500 !important;
        }
        [data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {
            color: #D9A572 !important;
            font-size: 0.76rem !important;
            font-weight: 800 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            margin-top: 0.65rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
            border-radius: 10px !important;
            margin: 2px 0 !important;
            padding: 0.48rem 0.72rem !important;
            transition: background-color 0.16s ease, transform 0.12s ease !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span,
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"] p {
            color: #EFE4D8 !important;
            font-weight: 600 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
            background: rgba(255, 240, 224, 0.10) !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
            background: linear-gradient(90deg, rgba(217, 165, 114, 0.28) 0%, rgba(217, 165, 114, 0.10) 100%) !important;
            border-left: 3px solid #D9A572 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] span {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }
        [data-testid="stSidebar"] .st-key-btn_sidebar_logout button {
            background: rgba(255, 245, 235, 0.08) !important;
            color: #F7EDE4 !important;
            border: 1px solid rgba(217, 165, 114, 0.35) !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            transition: background-color 0.15s ease, border-color 0.15s ease !important;
        }
        [data-testid="stSidebar"] .st-key-btn_sidebar_logout button:hover {
            background: rgba(217, 165, 114, 0.22) !important;
            border-color: #D9A572 !important;
            color: #FFFFFF !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: rgba(217, 165, 114, 0.22) !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg {
            color: #F5E6D3 !important;
            fill: #F5E6D3 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover {
            background-color: rgba(255, 240, 224, 0.14) !important;
            border-radius: 8px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover span,
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button:hover [data-testid="stIconMaterial"] {
            color: #FFFFFF !important;
        }
        .sidebar-brand {
            display: flex;
            align-items: center;
            gap: 11px;
            padding: 0.35rem 0.2rem 0.75rem 0.2rem;
            border-bottom: 1px solid rgba(217, 165, 114, 0.22);
            margin-bottom: 0.65rem;
        }
        .sidebar-brand-icon {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            background: linear-gradient(135deg, #D9A572 0%, #9E683B 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.28);
        }
        .sidebar-brand-title {
            font-size: 1.08rem;
            font-weight: 800;
            color: #FAF3EB;
            line-height: 1.15;
        }
        .sidebar-brand-sub {
            font-size: 0.74rem;
            font-weight: 500;
            color: #CBB39E;
            margin-top: 2px;
        }
        .sidebar-user-card {
            background: rgba(0, 0, 0, 0.22);
            border: 1px solid rgba(217, 165, 114, 0.22);
            border-radius: 12px;
            padding: 0.75rem 0.85rem;
            margin: 0.85rem 0 0.6rem 0;
        }
        .sidebar-user-row {
            display: flex;
            align-items: center;
            gap: 9px;
        }
        .sidebar-user-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: rgba(217, 165, 114, 0.20);
            border: 1px solid rgba(217, 165, 114, 0.45);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .sidebar-user-name {
            font-size: 0.88rem;
            font-weight: 700;
            color: #FAF3EB;
            line-height: 1.2;
        }
        .sidebar-user-email {
            font-size: 0.73rem;
            font-weight: 500;
            color: #CBB39E;
            word-break: break-all;
        }
        .sidebar-role-badge {
            display: inline-block;
            margin-top: 0.45rem;
            padding: 2px 9px;
            border-radius: 999px;
            font-size: 0.69rem;
            font-weight: 800;
            letter-spacing: 0.05em;
            color: #2B1810;
            background: #D9A572;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    """Renderiza a marca da cafeteria com ícone Lucide no topo da barra lateral."""
    icon_svg = load_lucide_svg("coffee", size=20, color="#2B1810")
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-brand">
                <div class="sidebar-brand-icon">{icon_svg}</div>
                <div>
                    <div class="sidebar-brand-title">Grão do Agreste</div>
                    <div class="sidebar-brand-sub">Gestão Integrada - UFAPE</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar_user_card(user: dict[str, Any]) -> None:
    """Exibe informações do usuário autenticado via Google e botão de logout na sidebar."""
    user_svg = load_lucide_svg("user", size=16, color="#E8C9A8")
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-user-card">
                <div class="sidebar-user-row">
                    <div class="sidebar-user-avatar">{user_svg}</div>
                    <div>
                        <div class="sidebar-user-name">{user.get('nome', 'Usuário')}</div>
                        <div class="sidebar-user-email">{user.get('email', '')}</div>
                    </div>
                </div>
                <span class="sidebar-role-badge">{user.get('perfil', 'GERENTE')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "Sair da conta",
            icon=":material/logout:",
            use_container_width=True,
            key="btn_sidebar_logout",
        ):
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


def render_page_header(title: str, subtitle: str, icon_name: str = "coffee") -> None:
    beans_uri = get_asset_data_uri("raw-coffee-units.png")
    icon_svg = load_lucide_svg(icon_name, size=22, color="#FAF7F2")
    beans_html = (
        f'<img src="{beans_uri}" alt="" style="position:absolute; right:18px; top:50%; '
        f'transform:translateY(-50%); height:66px; opacity:0.88; pointer-events:none; '
        f'filter:drop-shadow(0 3px 6px rgba(44,30,22,0.16));" />'
        if beans_uri
        else ""
    )
    icon_html = (
        f'<div style="width:44px; height:44px; border-radius:12px; '
        f'background:linear-gradient(135deg, #6F4E37 0%, #432818 100%); '
        f'display:flex; align-items:center; justify-content:center; flex-shrink:0; '
        f'box-shadow:0 4px 10px rgba(67,40,24,0.22);">{icon_svg}</div>'
        if icon_svg
        else ""
    )
    st.markdown(
        f"""
        <div style="position:relative; overflow:hidden; border-radius:14px;
                    background:linear-gradient(135deg, #FAF7F2 0%, #F2E7D8 100%);
                    border:1px solid #E6D8C8; padding:1.1rem 1.35rem; margin-bottom:1.1rem;">
            {beans_html}
            <div style="position:relative; z-index:1; display:flex; align-items:center;
                        gap:14px; padding-right:130px;">
                {icon_html}
                <div>
                    <div style="font-size:1.65rem; font-weight:800; color:#2C1E16; line-height:1.2;">{title}</div>
                    <div style="font-size:0.92rem; font-weight:500; color:#6B4F3F; margin-top:0.2rem;">{subtitle}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
