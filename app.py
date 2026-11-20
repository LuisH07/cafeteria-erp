"""Entrypoint principal — Cafeteria Grão do Agreste (ERP + Dashboard BI)."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Cafeteria Grão do Agreste — ERP & BI",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.auth.google_auth import render_login_gate
from src.auth.permissions import can_access_module
from src.ui.components.layout import render_sidebar_user_card

user = render_login_gate()
if not user:
    st.stop()

perfil = user["perfil"]

with st.sidebar:
    st.markdown("## ☕ Grão do Agreste")
    st.caption("ERP & Dashboard BI — UFAPE 2026.2")

erp_pages = []
page_specs = [
    ("visao_geral", "src/ui/pages/01_visao_geral.py", "Visão Geral", "🏠"),
    ("cadastros", "src/ui/pages/02_cadastros.py", "Cadastros & Ficha Técnica", "📋"),
    ("compras", "src/ui/pages/03_compras.py", "Compras", "🛒"),
    ("estoque", "src/ui/pages/04_estoque.py", "Estoque & Inventário", "📦"),
    ("vendas", "src/ui/pages/05_vendas_pdv.py", "Vendas / PDV", "💳"),
    ("operacional", "src/ui/pages/06_operacional.py", "Operacional (Barista)", "☕"),
    ("financeiro", "src/ui/pages/07_financeiro.py", "Financeiro", "💰"),
]

for key, path, title, icon in page_specs:
    if can_access_module(perfil, key):
        erp_pages.append(st.Page(path, title=title, icon=icon, url_path=key))

bi_pages = []
if can_access_module(perfil, "dashboard_bi"):
    bi_pages.append(
        st.Page(
            "src/ui/pages/08_dashboard_bi.py",
            title="Dashboard BI (2ª VA)",
            icon="📊",
            url_path="dashboard_bi",
        )
    )

nav_sections: dict[str, list[st.Page]] = {"Operação ERP (1ª VA)": erp_pages}
if bi_pages:
    nav_sections["Inteligência Gerencial (2ª VA)"] = bi_pages

render_sidebar_user_card(user)

current_page = st.navigation(nav_sections)
current_page.run()
