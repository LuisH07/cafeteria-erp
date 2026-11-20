"""Entrypoint principal — Cafeteria Grão do Agreste (ERP + Dashboard BI)."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Cafeteria Grão do Agreste - Gestão Integrada",
    page_icon=":material/local_cafe:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.auth.google_auth import render_login_gate
from src.auth.permissions import can_access_module
from src.ui.components.layout import (
    inject_sidebar_theme,
    render_sidebar_brand,
    render_sidebar_user_card,
)

user = render_login_gate()
if not user:
    st.stop()

inject_sidebar_theme()
render_sidebar_brand()

perfil = user["perfil"]

erp_pages = []
page_specs = [
    ("visao_geral", "src/ui/pages/01_visao_geral.py", "Visão Geral", ":material/dashboard:"),
    ("cadastros", "src/ui/pages/02_cadastros.py", "Catálogo e Cadastros", ":material/list_alt:"),
    ("compras", "src/ui/pages/03_compras.py", "Compras", ":material/shopping_cart:"),
    ("estoque", "src/ui/pages/04_estoque.py", "Estoque", ":material/inventory_2:"),
    ("vendas", "src/ui/pages/05_vendas_pdv.py", "Vendas", ":material/point_of_sale:"),
    ("operacional", "src/ui/pages/06_operacional.py", "Operação do Barista", ":material/local_cafe:"),
    ("financeiro", "src/ui/pages/07_financeiro.py", "Financeiro", ":material/account_balance_wallet:"),
]

for key, path, title, icon in page_specs:
    if can_access_module(perfil, key):
        erp_pages.append(st.Page(path, title=title, icon=icon, url_path=key))

bi_pages = []
if can_access_module(perfil, "dashboard_bi"):
    bi_pages.append(
        st.Page(
            "src/ui/pages/08_dashboard_bi.py",
            title="Dashboard BI",
            icon=":material/bar_chart:",
            url_path="dashboard_bi",
        )
    )

nav_sections: dict[str, list[st.Page]] = {"Operação ERP": erp_pages}
if bi_pages:
    nav_sections["Inteligência Gerencial"] = bi_pages

render_sidebar_user_card(user)

current_page = st.navigation(nav_sections)
current_page.run()
