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
from src.ui.components.assets import get_asset_data_uri


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
        st.title(":material/local_cafe: Cafeteria Grão do Agreste - Gestão Integrada")
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

        bg_uri = get_asset_data_uri("login-background.jpg")
        google_svg_uri = get_asset_data_uri("google-logo.svg")

        bg_css = (
            f"""
            background-color: #FFFFFF !important;
            background-image: url("{bg_uri}") !important;
            background-repeat: no-repeat !important;
            background-position: center bottom !important;
            background-size: cover !important;
            background-attachment: fixed !important;
            min-height: 100vh !important;
            """
            if bg_uri
            else "background: linear-gradient(180deg, #FAF7F2 0%, #EFE4D4 100%) !important;"
        )

        google_icon_css = (
            f"""
            .st-key-btn_google_login button::before {{
                content: "";
                display: inline-block;
                width: 20px;
                height: 20px;
                margin-right: 12px;
                background-image: url("{google_svg_uri}");
                background-size: contain;
                background-repeat: no-repeat;
                background-position: center;
                flex-shrink: 0;
            }}
            """
            if google_svg_uri
            else ""
        )

        st.markdown(
            f"""
            <style>
            .stApp,
            [data-testid="stAppViewContainer"] {{
                {bg_css}
            }}
            [data-testid="stMain"],
            [data-testid="stMainBlockContainer"] {{
                background: transparent !important;
            }}
            [data-testid="stHeader"] {{
                background: transparent !important;
            }}
            [data-testid="stSidebar"] {{
                display: none;
            }}
            .login-card-wrap {{
                background: rgba(255, 255, 255, 0.94);
                backdrop-filter: blur(6px);
                border: 1px solid #E6D8C8;
                border-radius: 18px;
                padding: 2.2rem 2rem 1.75rem 2rem;
                box-shadow: 0 12px 34px rgba(59, 40, 30, 0.10);
                text-align: center;
                margin-top: 3rem;
            }}
            .login-title {{
                font-size: 1.9rem;
                font-weight: 800;
                color: #2C1E16;
                margin: 0 0 0.3rem 0;
            }}
            .login-subtitle {{
                font-size: 0.98rem;
                font-weight: 600;
                color: #6B4F3F;
                margin-bottom: 0.35rem;
            }}
            .login-meta {{
                font-size: 0.80rem;
                font-weight: 500;
                color: #8C7466;
                margin-bottom: 1.25rem;
            }}
            .st-key-btn_google_login button {{
                background-color: #FFFFFF !important;
                color: #1F1F1F !important;
                border: 1px solid #DADCE0 !important;
                border-radius: 999px !important;
                min-height: 46px !important;
                padding: 0.55rem 1.4rem !important;
                font-family: "Roboto", "Segoe UI", Arial, sans-serif !important;
                font-size: 0.96rem !important;
                font-weight: 600 !important;
                letter-spacing: 0.01em !important;
                box-shadow: 0 1px 3px rgba(60, 64, 67, 0.12) !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                transition: background-color 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease !important;
            }}
            .st-key-btn_google_login button:hover {{
                background-color: #F8FAFF !important;
                border-color: #D2E3FC !important;
                box-shadow: 0 2px 6px rgba(60, 64, 67, 0.18) !important;
            }}
            .st-key-btn_google_login button:active {{
                background-color: #EEF3FD !important;
            }}
            .st-key-btn_google_login button p {{
                margin: 0 !important;
                font-weight: 600 !important;
                color: #1F1F1F !important;
            }}
            {google_icon_css}
            </style>
            """,
            unsafe_allow_html=True,
        )

        col_left, col_center, col_right = st.columns([1.2, 1.8, 1.2])
        with col_center:
            st.markdown(
                """
                <div class="login-card-wrap">
                    <div class="login-title">Cafeteria Grão do Agreste</div>
                    <div class="login-subtitle">Sistema Integrado de Gestão e Inteligência de Negócios</div>
                    <div class="login-meta">Sistemas de Informação e Tecnologias - UFAPE (2026.2)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            if st.button(
                "Continuar com o Google",
                key="btn_google_login",
                use_container_width=True,
            ):
                st.login("google")
            st.markdown(
                "<p style='text-align:center; font-size:0.78rem; color:#7A6558; margin-top:0.6rem;'>"
                "Acesso autenticado com rastreabilidade completa das operações."
                "</p>",
                unsafe_allow_html=True,
            )
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
