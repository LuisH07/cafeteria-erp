"""Página 01 — Visão Geral Operacional e Administração de Usuários."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth.google_auth import list_users, update_user_role_or_status
from src.db.connection import check_database_health
from src.db.queries import fetch_one
from src.services.audit_service import list_recent_audit_logs
from src.services.estoque_service import get_estoque_position
from src.services.exceptions import DomainError
from src.services.financeiro_service import get_resumo_financeiro, list_titulos_financeiros
from src.services.operacional_service import list_ordens_preparo
from src.ui.components.layout import (
    ensure_page_access,
    fmt_brl,
    fmt_date,
    fmt_datetime,
    render_page_header,
    user_can,
)

user = ensure_page_access("visao_geral")
render_page_header(
    "☕ Visão Geral Operacional",
    "Painel de acompanhamento diário integrado entre Vendas, Estoque, Barista e Financeiro.",
)

# Resumo do dia
hoje = fetch_one(
    """
    SELECT
        COUNT(*) FILTER (WHERE status = 'CONCLUIDA')::INT AS qtd_vendas,
        COALESCE(SUM(valor_total) FILTER (WHERE status = 'CONCLUIDA'), 0)::NUMERIC(14,2) AS faturamento,
        COALESCE(SUM(valor_total - custo_total_cmv) FILTER (WHERE status = 'CONCLUIDA'), 0)::NUMERIC(14,2) AS margem
    FROM vendas
    WHERE DATE(data_venda AT TIME ZONE 'America/Sao_Paulo') = CURRENT_DATE
    """
) or {"qtd_vendas": 0, "faturamento": 0, "margem": 0}

criticos = get_estoque_position(apenas_criticos=True)
fila_aberta = list_ordens_preparo(apenas_abertas=True)
resumo_fin = get_resumo_financeiro()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Faturamento Hoje", fmt_brl(hoje["faturamento"]), f"{hoje['qtd_vendas']} venda(s)")
c2.metric("Fila do Barista", f"{len(fila_aberta)} pedido(s)", "Em aberto")
c3.metric(
    "Insumos Críticos",
    f"{len(criticos)} item(ns)",
    "Abaixo do mínimo" if criticos else "Estoque saudável",
    delta_color="inverse" if criticos else "normal",
)
c4.metric(
    "Saldo em Caixa",
    fmt_brl(resumo_fin["saldo_caixa"]),
    f"A pagar atrasado: {fmt_brl(resumo_fin['a_pagar_atrasado'])}"
    if resumo_fin["a_pagar_atrasado"] > 0
    else "Sem atrasos a pagar",
    delta_color="inverse" if resumo_fin["a_pagar_atrasado"] > 0 else "normal",
)

st.divider()
col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("🚨 Alertas de Reposição de Estoque")
    if criticos:
        df_crit = pd.DataFrame(criticos)[
            ["sku", "nome", "estoque_atual", "estoque_minimo", "unidade_medida", "localizacao"]
        ]
        df_crit.columns = ["SKU", "Insumo", "Saldo Atual", "Mínimo", "Un.", "Localização"]
        st.dataframe(df_crit, use_container_width=True, hide_index=True)
    else:
        st.success("Nenhum insumo abaixo do estoque mínimo no momento.")

    st.subheader("☕ Pedidos em Aberto no Operacional (Barista)")
    if fila_aberta:
        for ordem in fila_aberta[:6]:
            badge = {"NA_FILA": "🟡 Na Fila", "EM_PREPARO": "🟠 Em Preparo", "PRONTO": "🟢 Pronto"}.get(
                ordem["status"], ordem["status"]
            )
            st.info(
                f"**{ordem['numero_venda']}** ({ordem['canal_venda']}) — {badge}\n\n"
                f"Cliente: {ordem['cliente_nome']} | Itens: {ordem['itens_resumo']}"
            )
    else:
        st.success("Fila de preparo zerada no momento.")

with col_dir:
    st.subheader("💰 Contas Atrasadas ou Vencendo")
    titulos_alerta = [
        t
        for t in list_titulos_financeiros(situacao="Todos", limit=50)
        if t["situacao"] in {"ATRASADO", "ABERTO"}
    ][:8]
    if titulos_alerta:
        rows_fin = [
            {
                "Tipo": t["tipo"],
                "Situação": "🔴 ATRASADO" if t["situacao"] == "ATRASADO" else "🟡 ABERTO",
                "Vencimento": fmt_date(t["data_vencimento"]),
                "Descrição": t["descricao"],
                "Valor": fmt_brl(t["valor_original"]),
            }
            for t in titulos_alerta
        ]
        st.dataframe(pd.DataFrame(rows_fin), use_container_width=True, hide_index=True)
    else:
        st.success("Não há títulos pendentes ou atrasados.")

    st.subheader("🔌 Status da Infraestrutura")
    health = check_database_health()
    if health.get("ok"):
        st.success(
            f"PostgreSQL/Supabase conectado (`{health['database']}`). "
            f"Última verificação: {fmt_datetime(health['server_time'])}"
        )
    else:
        st.error(f"Erro na conexão com o banco: {health.get('error')}")

# Seção exclusiva de ADMIN: Gestão de Perfis e Trilha de Auditoria
if user_can(user, "usuarios:manage"):
    st.divider()
    st.subheader("🛡️ Administração — Controle de Acesso (RBAC) e Auditoria")
    tab_usr, tab_aud = st.tabs(["Usuários e Perfis", "Trilha de Auditoria Recente"])

    with tab_usr:
        usuarios = list_users()
        if usuarios:
            df_u = pd.DataFrame(usuarios)
            df_u["ultimo_login_em"] = df_u["ultimo_login_em"].apply(fmt_datetime)
            st.dataframe(
                df_u[["id", "nome", "email", "perfil", "ativo", "ultimo_login_em"]],
                use_container_width=True,
                hide_index=True,
            )

            with st.form("form_atualizar_perfil_usuario"):
                st.markdown("**Alterar perfil ou status de um usuário**")
                opcoes_u = {f"{u['nome']} ({u['email']})": u for u in usuarios}
                sel_label = st.selectbox("Usuário", list(opcoes_u.keys()))
                sel_u = opcoes_u[sel_label]
                c_p, c_a = st.columns(2)
                novo_perfil = c_p.selectbox(
                    "Perfil RBAC",
                    ["ADMIN", "GERENTE", "CAIXA", "BARISTA", "ESTOQUISTA"],
                    index=["ADMIN", "GERENTE", "CAIXA", "BARISTA", "ESTOQUISTA"].index(sel_u["perfil"]),
                )
                novo_ativo = c_a.checkbox("Conta Ativa", value=bool(sel_u["ativo"]))
                if st.form_submit_button("Salvar Alteração", type="primary"):
                    try:
                        update_user_role_or_status(
                            target_user_id=int(sel_u["id"]),
                            perfil=novo_perfil,
                            ativo=novo_ativo,
                            actor_user_id=int(user["id"]),
                        )
                        st.success("Perfil do usuário atualizado com sucesso.")
                        st.rerun()
                    except DomainError as exc:
                        st.error(str(exc))

    with tab_aud:
        logs = list_recent_audit_logs(limit=40)
        if logs:
            rows_log = [
                {
                    "Data/Hora": fmt_datetime(l["criado_em"]),
                    "Usuário": l["usuario_nome"],
                    "Módulo": l["modulo"],
                    "Entidade": l["entidade"],
                    "Ação": l["acao"],
                    "Detalhes": str(l["detalhes_json"]),
                }
                for l in logs
            ]
            st.dataframe(pd.DataFrame(rows_log), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum evento de auditoria registrado ainda.")
