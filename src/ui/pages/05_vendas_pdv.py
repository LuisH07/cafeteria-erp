"""Página 05 — Módulo de Vendas / PDV integrado a Estoque, Operacional e Financeiro."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.services.cadastros_service import list_clientes, list_produtos
from src.services.exceptions import DomainError, InsufficientStockError
from src.services.vendas_service import (
    cancelar_venda,
    get_venda_detalhes,
    list_vendas,
    registrar_venda,
    verificar_disponibilidade_carrinho,
)
from src.ui.components.layout import (
    ensure_page_access,
    fmt_brl,
    fmt_datetime,
    render_page_header,
    user_can,
)
from src.ui.components.receipt import render_receipt_card

user = ensure_page_access("vendas")
can_create = user_can(user, "vendas:create")
can_cancel = user_can(user, "vendas:cancel")

render_page_header(
    "Vendas e Frente de Caixa",
    "Registro de pedidos com baixa automática de insumos via ficha técnica, envio à fila do barista e lançamento financeiro.",
    icon_name="credit-card",
)

if "pdv_cart" not in st.session_state:
    st.session_state["pdv_cart"] = []
if "last_venda_id" not in st.session_state:
    st.session_state["last_venda_id"] = None

tab_pdv, tab_hist = st.tabs(
    [":material/point_of_sale: Frente de Caixa (PDV)", ":material/receipt_long: Histórico, Comprovantes e Cancelamentos"]
)

# -----------------------------------------------------------------------------
# ABA 1: PDV
# -----------------------------------------------------------------------------
with tab_pdv:
    if not can_create:
        st.info("Seu perfil possui permissão apenas de consulta neste módulo.")
    else:
        produtos = [p for p in list_produtos(apenas_ativos=True) if int(p["qtd_insumos_ficha"]) > 0]
        clientes = list_clientes(apenas_ativos=True)

        if not produtos or not clientes:
            st.warning(
                "Certifique-se de ter ao menos um cliente ativo e produtos com Ficha Técnica cadastrada."
            )
        else:
            col_prod, col_cart = st.columns([1.15, 1])

            with col_prod:
                st.subheader("1. Selecionar Produtos do Cardápio")
                categorias = ["Todas"] + sorted({p["categoria_nome"] for p in produtos})
                cat_f = st.selectbox("Filtrar Categoria", categorias)
                prods_filtrados = [
                    p for p in produtos if cat_f == "Todas" or p["categoria_nome"] == cat_f
                ]
                prod_map = {
                    f"{p['nome']} - {fmt_brl(p['preco_venda'])} ({p['categoria_nome']})": p
                    for p in prods_filtrados
                }
                with st.form("form_add_pdv"):
                    sel_p = prod_map[st.selectbox("Produto", list(prod_map.keys()))]
                    qtd = st.number_input("Quantidade", min_value=1, value=1, step=1)
                    if st.form_submit_button("Adicionar ao Carrinho", icon=":material/add_shopping_cart:", use_container_width=True):
                        cart = st.session_state["pdv_cart"]
                        encontrado = False
                        for item in cart:
                            if item["produto_id"] == int(sel_p["id"]):
                                item["quantidade"] += int(qtd)
                                item["subtotal"] = round(
                                    item["quantidade"] * item["preco_unitario"], 2
                                )
                                encontrado = True
                                break
                        if not encontrado:
                            preco = float(sel_p["preco_venda"])
                            cart.append(
                                {
                                    "produto_id": int(sel_p["id"]),
                                    "nome": sel_p["nome"],
                                    "preco_unitario": preco,
                                    "quantidade": int(qtd),
                                    "subtotal": round(preco * int(qtd), 2),
                                }
                            )
                        st.rerun()

                if st.session_state.get("last_venda_id"):
                    try:
                        det_last = get_venda_detalhes(int(st.session_state["last_venda_id"]))
                        render_receipt_card(det_last, key_prefix="pdv_last")
                    except DomainError:
                        pass

            with col_cart:
                st.subheader("2. Carrinho e Fechamento")
                cart = st.session_state["pdv_cart"]
                if not cart:
                    st.info("Carrinho vazio. Adicione itens ao lado para iniciar a venda.")
                else:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Produto": it["nome"],
                                    "Qtd.": it["quantidade"],
                                    "Unit.": fmt_brl(it["preco_unitario"]),
                                    "Subtotal": fmt_brl(it["subtotal"]),
                                }
                                for it in cart
                            ]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    # Pré-checagem de disponibilidade de insumos
                    check = verificar_disponibilidade_carrinho(cart)
                    if not check["disponivel"]:
                        if check["faltantes"]:
                            falt_msg = "\n".join(
                                f"- **{f['nome']}**: precisa `{f['necessario']} {f['unidade_medida']}`, "
                                f"disponível `{f['disponivel']} {f['unidade_medida']}`"
                                for f in check["faltantes"]
                            )
                            st.error(f"Estoque insuficiente para este carrinho:\n{falt_msg}")
                        if check["sem_ficha"]:
                            st.error(f"Produtos sem Ficha Técnica: {', '.join(check['sem_ficha'])}")
                    else:
                        st.success("Todos os insumos da ficha técnica estão disponíveis em estoque.")

                    subtotal = round(sum(it["subtotal"] for it in cart), 2)
                    if st.button("Limpar Carrinho", icon=":material/delete:", use_container_width=True):
                        st.session_state["pdv_cart"] = []
                        st.rerun()

                    with st.form("form_finalizar_venda"):
                        cli_map = {f"{c['nome']} ({c['tipo_cliente']})": int(c["id"]) for c in clientes}
                        cli_sel = st.selectbox("Cliente*", list(cli_map.keys()))
                        c_ch, c_pg = st.columns(2)
                        canal = c_ch.selectbox("Canal de Venda*", ["BALCAO", "MESA", "RETIRADA", "DELIVERY"])
                        forma = c_pg.selectbox(
                            "Forma de Pagamento*",
                            ["PIX", "DEBITO", "CREDITO", "DINHEIRO", "FATURADO"],
                        )
                        c_desc, c_prio = st.columns(2)
                        desconto = c_desc.number_input(
                            "Desconto (R$)",
                            min_value=0.0,
                            max_value=max(0.0, subtotal - 0.01),
                            value=0.0,
                            step=0.50,
                        )
                        prioridade = c_prio.selectbox("Prioridade Preparo", ["NORMAL", "ALTA"])
                        obs_prep = st.text_input(
                            "Observações para o Barista",
                            placeholder="Ex.: Sem açúcar, leite bem quente",
                        )

                        total_liq = round(subtotal - desconto, 2)
                        st.markdown(f"### Total a Pagar: **{fmt_brl(total_liq)}**")

                        submitted = st.form_submit_button(
                            "Finalizar Venda",
                            icon=":material/check_circle:",
                            type="primary",
                            use_container_width=True,
                            disabled=not check["disponivel"],
                        )
                        if submitted:
                            try:
                                venda = registrar_venda(
                                    cliente_id=cli_map[cli_sel],
                                    canal_venda=canal,
                                    forma_pagamento=forma,
                                    itens=cart,
                                    usuario_id=int(user["id"]),
                                    desconto=desconto,
                                    observacoes_preparo=obs_prep,
                                    prioridade=prioridade,
                                )
                                st.session_state["pdv_cart"] = []
                                st.session_state["last_venda_id"] = int(venda["id"])
                                st.success(
                                    f"Venda **{venda['numero_venda']}** concluída ({fmt_brl(venda['valor_total'])})! "
                                    "Insumos baixados, ordem enviada ao barista e financeiro atualizado."
                                )
                                st.rerun()
                            except InsufficientStockError as exc:
                                st.error(str(exc))
                            except DomainError as exc:
                                st.error(str(exc))

# -----------------------------------------------------------------------------
# ABA 2: HISTÓRICO, COMPROVANTES E CANCELAMENTO
# -----------------------------------------------------------------------------
with tab_hist:
    f1, f2 = st.columns(2)
    st_f = f1.selectbox("Status", ["Todos", "CONCLUIDA", "CANCELADA"])
    ch_f = f2.selectbox("Canal", ["Todos", "BALCAO", "MESA", "RETIRADA", "DELIVERY"])

    vendas = list_vendas(status=st_f, canal_venda=ch_f, limit=120)
    if vendas:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Pedido": v["numero_venda"],
                        "Data e Hora": fmt_datetime(v["data_venda"]),
                        "Cliente": v["cliente_nome"],
                        "Canal": v["canal_venda"],
                        "Pagamento": v["forma_pagamento"],
                        "Total": fmt_brl(v["valor_total"]),
                        "CMV": fmt_brl(v["custo_total_cmv"]),
                        "Margem": fmt_brl(v["margem_bruta"]),
                        "Preparo": v["status_preparo"],
                        "Status": v["status"],
                    }
                    for v in vendas
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        v_map = {
            f"{v['numero_venda']} - {v['cliente_nome']} ({fmt_brl(v['valor_total'])} | {v['status']})": int(v["id"])
            for v in vendas
        }
        sel_vid = v_map[st.selectbox("Selecionar Venda", list(v_map.keys()))]
        det = get_venda_detalhes(sel_vid)

        col_rec, col_act = st.columns([1.2, 1])
        with col_rec:
            render_receipt_card(det, key_prefix="hist_receipt")

        with col_act:
            st.subheader("Detalhes do Pedido")
            st.write(f"- **Custo dos Insumos (CMV):** {fmt_brl(det['custo_total_cmv'])}")
            st.write(f"- **Status do Preparo:** `{det.get('status_preparo', '-')}`")
            st.write(f"- **Situação Financeira:** `{det.get('status_financeiro', '-')}`")

            if det["status"] == "CONCLUIDA" and can_cancel:
                st.divider()
                st.warning(
                    "O cancelamento preserva o histórico: devolve os insumos ao estoque se o pedido "
                    "ainda estiver na fila (ou contabiliza como perda se já estiver em preparo) "
                    "e estorna o lançamento financeiro."
                )
                with st.form("form_cancelar_venda"):
                    motivo = st.text_input("Motivo do Cancelamento*", placeholder="Ex.: Erro de lançamento no caixa")
                    if st.form_submit_button("Confirmar Cancelamento", icon=":material/cancel:", use_container_width=True):
                        try:
                            res = cancelar_venda(
                                venda_id=sel_vid,
                                motivo=motivo,
                                usuario_id=int(user["id"]),
                            )
                            acao_est = (
                                "Insumos estornados ao estoque."
                                if res["estoque_estornado"]
                                else "Pedido já havia iniciado preparo; insumos registrados como perda operacional."
                            )
                            st.success(f"Venda {res['numero_venda']} cancelada. {acao_est}")
                            st.rerun()
                        except DomainError as exc:
                            st.error(str(exc))
            elif det["status"] == "CANCELADA":
                st.info(
                    f"Cancelada em {fmt_datetime(det['cancelada_em'])}. "
                    f"Motivo: {det.get('motivo_cancelamento') or '-'}"
                )
    else:
        st.info("Nenhuma venda encontrada para os filtros selecionados.")
