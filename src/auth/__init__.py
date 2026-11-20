"""Autenticação Google (OIDC) e Controle de Acesso Baseado em Perfis (RBAC)."""

from src.auth.google_auth import get_current_user, render_login_gate, sync_google_user
from src.auth.permissions import (
    MODULE_PERMISSIONS,
    can_access_module,
    has_permission,
    require_permission,
)

__all__ = [
    "MODULE_PERMISSIONS",
    "can_access_module",
    "get_current_user",
    "has_permission",
    "render_login_gate",
    "require_permission",
    "sync_google_user",
]
