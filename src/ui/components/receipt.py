"""Componente de emissão e download de comprovante de venda (PDV)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.ui.components.layout import fmt_brl, fmt_datetime


def build_receipt_text(venda: dict[str, Any]) -> str:
    """Gera comprovante de venda em texto estruturado pronto para download/impressão."""
    lines = [
        "================================================",
        "         CAFETERIA GRÃO DO AGRESTE              ",
        "       Comprovante Não Fiscal de Venda          ",
        "================================================",
        f"Pedido    : {venda['numero_venda']}",
        f"Data      : {fmt_datetime(venda['data_venda'])}",
        f"Cliente   : {venda['cliente_nome']}",
        f"Canal     : {venda['canal_venda']}",
        f"Pagamento : {venda['forma_pagamento']}",
        f"Operador  : {venda['operador_nome']}",
        f"Status    : {venda['status']} (Preparo: {venda.get('status_preparo', '-')})",
        "------------------------------------------------",
        "ITENS DO PEDIDO:",
    ]
    for it in venda.get("itens", []):
        lines.append(
            f"  {it['quantidade']}x {it['produto_nome']} "
            f"({fmt_brl(it['preco_unitario_snapshot'])}) = {fmt_brl(it['subtotal'])}"
        )
    lines.extend(
        [
            "------------------------------------------------",
            f"Subtotal  : {fmt_brl(venda['subtotal'])}",
            f"Desconto  : {fmt_brl(venda['desconto'])}",
            f"TOTAL     : {fmt_brl(venda['valor_total'])}",
            "================================================",
            "Obrigado pela preferência! Volte sempre.",
        ]
    )
    return "\n".join(lines)


def render_receipt_card(venda: dict[str, Any], key_prefix: str = "receipt") -> None:
    """Renderiza comprovante visual e botão de download .txt."""
    receipt_txt = build_receipt_text(venda)
    with st.container(border=True):
        st.subheader(f":material/receipt_long: Comprovante - {venda['numero_venda']}")
        st.code(receipt_txt, language="text")
        st.download_button(
            label="Baixar Comprovante (.txt)",
            icon=":material/download:",
            data=receipt_txt.encode("utf-8"),
            file_name=f"comprovante_{venda['numero_venda']}.txt",
            mime="text/plain",
            key=f"{key_prefix}_{venda['id']}",
            use_container_width=True,
        )
