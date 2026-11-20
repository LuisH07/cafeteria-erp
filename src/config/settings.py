"""Leitura centralizada de configurações a partir de st.secrets e variáveis de ambiente."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import tomllib
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_ADMIN_EMAILS = ("assuero.ximenes@ufape.edu.br",)
VALID_ROLES = ("ADMIN", "GERENTE", "CAIXA", "BARISTA", "ESTOQUISTA")
_SECRETS_FILE = Path(__file__).resolve().parent.parent.parent / ".streamlit" / "secrets.toml"


def _get_streamlit_secrets() -> Mapping[str, Any]:
    """Lê secrets do arquivo local .streamlit/secrets.toml ou de st.secrets (Streamlit Cloud)."""
    if _SECRETS_FILE.exists():
        try:
            return tomllib.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return {}


def _normalize_db_url(raw_url: str) -> str:
    """Garante compatibilidade da URI PostgreSQL com SQLAlchemy + psycopg3 e sslmode."""
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


@dataclass(frozen=True)
class Settings:
    app_name: str = "Cafeteria Grão do Agreste — ERP & BI"
    timezone: str = "America/Sao_Paulo"
    database_url: str = ""
    admin_emails: tuple[str, ...] = field(default_factory=lambda: DEFAULT_ADMIN_EMAILS)
    default_role: str = "GERENTE"
    allowed_domains: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_database_configured(self) -> bool:
        return bool(self.database_url and "SEU_PROJECT_REF" not in self.database_url)


def load_settings() -> Settings:
    """Carrega configurações combinando st.secrets e variáveis de ambiente."""
    secrets = _get_streamlit_secrets()

    db_section = secrets.get("database", {})
    raw_db_url = ""
    if isinstance(db_section, Mapping) and db_section.get("url"):
        raw_db_url = str(db_section["url"])
    elif os.getenv("DATABASE_URL"):
        raw_db_url = str(os.getenv("DATABASE_URL", ""))

    db_url = _normalize_db_url(raw_db_url) if raw_db_url else ""

    auth_policy = secrets.get("auth_policy", {})
    emails_set = {e.strip().lower() for e in DEFAULT_ADMIN_EMAILS}
    if isinstance(auth_policy, Mapping):
        for item in auth_policy.get("admin_emails", []) or []:
            if item and str(item).strip():
                emails_set.add(str(item).strip().lower())

    env_admins = os.getenv("ADMIN_EMAILS", "")
    for item in env_admins.split(","):
        if item.strip():
            emails_set.add(item.strip().lower())

    default_role = "GERENTE"
    if isinstance(auth_policy, Mapping) and auth_policy.get("default_role"):
        candidate = str(auth_policy["default_role"]).strip().upper()
        if candidate in VALID_ROLES:
            default_role = candidate
    elif os.getenv("DEFAULT_ROLE"):
        candidate = os.getenv("DEFAULT_ROLE", "GERENTE").strip().upper()
        if candidate in VALID_ROLES:
            default_role = candidate

    allowed_domains: list[str] = []
    if isinstance(auth_policy, Mapping):
        for dom in auth_policy.get("allowed_domains", []) or []:
            if dom and str(dom).strip():
                allowed_domains.append(str(dom).strip().lower().lstrip("@"))

    return Settings(
        database_url=db_url,
        admin_emails=tuple(sorted(emails_set)),
        default_role=default_role,
        allowed_domains=tuple(allowed_domains),
    )


def has_google_oauth_config() -> bool:
    """Verifica se a seção [auth] / [auth.google] está configurada em st.secrets."""
    secrets = _get_streamlit_secrets()
    auth = secrets.get("auth", {})
    if not isinstance(auth, Mapping):
        return False
    google = auth.get("google", {})
    if not isinstance(google, Mapping):
        return False
    client_id = str(google.get("client_id", ""))
    client_secret = str(google.get("client_secret", ""))
    redirect_uri = str(auth.get("redirect_uri", ""))
    return (
        bool(client_id and client_secret and redirect_uri)
        and "SEU_CLIENT_ID" not in client_id
        and "SEU_CLIENT_SECRET" not in client_secret
    )
