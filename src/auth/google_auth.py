"""Integração de autenticação Google (OIDC nativo do Streamlit) com a tabela `usuarios`."""

from __future__ import annotations

from typing import Any

import streamlit as st
from sqlalchemy import text

from src.config.settings import has_google_oauth_config, load_settings
from src.db.connection import get_transaction
from src.db.queries import fetch_all, fetch_one
from src.services.audit_service import log_audit_event
from src.services.exceptions import AuthorizationError, ValidationError


def _extract_user_field(user_obj: Any, key: str, default: str = "") -> str:
    """Lê atributos de st.user de forma resiliente entre versões do Streamlit."""
    if user_obj is None:
        return default
    try:
        if key in user_obj:
            val = user_obj[key]
            return str(val) if val is not None else default
    except Exception:
        pass
    val = getattr(user_obj, key, default)
    return str(val) if val is not None else default


def _is_logged_in() -> bool:
    try:
        return bool(getattr(st.user, "is_logged_in", False))
    except Exception:
        return False


def sync_google_user(
    *,
    google_sub: str,
    email: str,
    nome: str,
    avatar_url: str | None = None,
) -> dict[str, Any]:
    """Faz UPSERT do usuário autenticado pelo Google no PostgreSQL e aplica política de perfil."""
    normalized_email = email.strip().lower()
    if not normalized_email or not google_sub.strip():
        raise ValidationError("Dados de identidade Google incompletos (email/sub).")

    settings = load_settings()
    if settings.allowed_domains:
        domain = normalized_email.split("@")[-1]
        if domain not in settings.allowed_domains and normalized_email not in settings.admin_emails:
            raise AuthorizationError(
                f"Domínio '@{domain}' não autorizado. Utilize uma conta permitida."
            )

    is_configured_admin = normalized_email in settings.admin_emails

    with get_transaction() as conn:
        existing = fetch_one(
            """
            SELECT id, google_sub, email, nome, avatar_url, perfil, ativo
            FROM usuarios
            WHERE google_sub = :google_sub OR LOWER(email) = :email
            LIMIT 1
            """,
            {"google_sub": google_sub, "email": normalized_email},
            conn=conn,
        )

        if existing:
            if not existing["ativo"]:
                raise AuthorizationError(
                    "Sua conta está inativada no sistema. Contate um administrador."
                )

            target_role = "ADMIN" if is_configured_admin else existing["perfil"]
            row = conn.execute(
                text(
                    """
                    UPDATE usuarios
                    SET google_sub = :google_sub,
                        email = :email,
                        nome = :nome,
                        avatar_url = :avatar_url,
                        perfil = :perfil,
                        ultimo_login_em = NOW(),
                        atualizado_em = NOW()
                    WHERE id = :id
                    RETURNING id, google_sub, email, nome, avatar_url, perfil, ativo, ultimo_login_em
                    """
                ),
                {
                    "id": existing["id"],
                    "google_sub": google_sub,
                    "email": normalized_email,
                    "nome": nome.strip() or normalized_email.split("@")[0],
                    "avatar_url": avatar_url,
                    "perfil": target_role,
                },
            ).mappings().first()
            user_record = dict(row)
        else:
            # Se for o primeiro usuário real ou estiver em admin_emails, promove para ADMIN
            existing_admins = conn.execute(
                text("SELECT COUNT(*) FROM usuarios WHERE perfil = 'ADMIN' AND ativo = TRUE")
            ).scalar()
            assigned_role = (
                "ADMIN"
                if (is_configured_admin or (existing_admins or 0) == 0)
                else settings.default_role
            )

            row = conn.execute(
                text(
                    """
                    INSERT INTO usuarios (
                        google_sub, email, nome, avatar_url, perfil, ativo, ultimo_login_em
                    )
                    VALUES (
                        :google_sub, :email, :nome, :avatar_url, :perfil, TRUE, NOW()
                    )
                    RETURNING id, google_sub, email, nome, avatar_url, perfil, ativo, ultimo_login_em
                    """
                ),
                {
                    "google_sub": google_sub,
                    "email": normalized_email,
                    "nome": nome.strip() or normalized_email.split("@")[0],
                    "avatar_url": avatar_url,
                    "perfil": assigned_role,
                },
            ).mappings().first()
            user_record = dict(row)

        log_audit_event(
            usuario_id=user_record["id"],
            modulo="AUTH",
            entidade="usuarios",
            entidade_id=user_record["id"],
            acao="LOGIN_GOOGLE",
            detalhes={"email": user_record["email"], "perfil": user_record["perfil"]},
            conn=conn,
        )
        return user_record


def list_users() -> list[dict[str, Any]]:
    """Lista todos os usuários cadastrados para gestão de perfis pelo ADMIN."""
    return fetch_all(
        """
        SELECT id, email, nome, perfil, ativo, ultimo_login_em, criado_em
        FROM usuarios
        ORDER BY ativo DESC, nome ASC
        """
    )


def update_user_role_or_status(
    *,
    target_user_id: int,
    perfil: str,
    ativo: bool,
    actor_user_id: int,
) -> dict[str, Any]:
    """Atualiza perfil e status de um usuário (ação restrita a ADMIN)."""
    valid_roles = {"ADMIN", "GERENTE", "CAIXA", "BARISTA", "ESTOQUISTA"}
    if perfil not in valid_roles:
        raise ValidationError(f"Perfil inválido: {perfil}")

    with get_transaction() as conn:
        row = conn.execute(
            text(
                """
                UPDATE usuarios
                SET perfil = :perfil,
                    ativo = :ativo,
                    atualizado_em = NOW()
                WHERE id = :id
                RETURNING id, email, nome, perfil, ativo
                """
            ),
            {"id": target_user_id, "perfil": perfil, "ativo": ativo},
        ).mappings().first()
        if not row:
            raise ValidationError("Usuário não encontrado.")
        result = dict(row)
        log_audit_event(
            usuario_id=actor_user_id,
            modulo="AUTH",
            entidade="usuarios",
            entidade_id=target_user_id,
            acao="ATUALIZAR_PERFIL",
            detalhes={"perfil": perfil, "ativo": ativo},
            conn=conn,
        )
        return result


def get_current_user() -> dict[str, Any] | None:
    """Retorna o usuário autenticado salvo em st.session_state."""
    return st.session_state.get("current_user")


def render_login_gate() -> dict[str, Any] | None:
    """Controla o acesso à aplicação exigindo autenticação Google (OIDC)."""
    if not has_google_oauth_config():
        st.title("☕ Cafeteria Grão do Agreste — ERP & BI")
        st.error(
            "Autenticação Google (OIDC) ainda não configurada neste ambiente. "
            "Configure `[auth]` e `[auth.google]` em `.streamlit/secrets.toml` "
            "(ou em App Settings → Secrets no Streamlit Community Cloud)."
        )
        st.info(
            "Consulte o passo a passo completo em `docs/GUIA_DEPLOY_SUPABASE_GOOGLE.md` "
            "e o modelo em `.streamlit/secrets.toml.example`."
        )
        return None

    if not _is_logged_in():
        st.session_state.pop("current_user", None)
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            st.markdown(
                """
                <div style="text-align:center; padding: 2rem 1rem 1rem 1rem;">
                    <h1>☕ Cafeteria Grão do Agreste</h1>
                    <p style="font-size: 1.05rem; color: #5C4033;">
                        Sistema Integrado de Gestão (ERP) &amp; Inteligência de Negócios (BI)<br/>
                        <small>Sistemas de Informação e Tecnologias — UFAPE (2026.2)</small>
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                st.subheader("Acesso Seguro com Conta Google")
                st.write(
                    "Faça login com sua conta Google institucional ou pessoal para acessar os "
                    "módulos do ERP e o Dashboard BI com rastreabilidade completa das operações."
                )
                if st.button(
                    "🔐 Entrar com Google",
                    type="primary",
                    use_container_width=True,
                ):
                    st.login("google")
        return None

    # Usuário autenticado via Google -> sincroniza com PostgreSQL uma vez por sessão
    email = _extract_user_field(st.user, "email")
    sub = _extract_user_field(st.user, "sub") or email
    name = _extract_user_field(st.user, "name", default=email.split("@")[0])
    picture = _extract_user_field(st.user, "picture", default="")

    cached_user = st.session_state.get("current_user")
    if cached_user and cached_user.get("email") == email.strip().lower():
        return cached_user

    try:
        user_record = sync_google_user(
            google_sub=sub,
            email=email,
            nome=name,
            avatar_url=picture or None,
        )
        st.session_state["current_user"] = user_record
        return user_record
    except Exception as exc:
        st.error(f"Não foi possível concluir o login: {exc}")
        if st.button("Sair da conta Google"):
            st.session_state.pop("current_user", None)
            st.logout()
        return None
