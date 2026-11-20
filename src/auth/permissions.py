"""Matriz de permissões (RBAC) por perfil de usuário da cafeteria."""

from __future__ import annotations

from src.services.exceptions import AuthorizationError

ALL_MODULES = (
    "visao_geral",
    "cadastros",
    "compras",
    "estoque",
    "vendas",
    "operacional",
    "financeiro",
    "dashboard_bi",
    "usuarios_admin",
)

MODULE_PERMISSIONS: dict[str, set[str]] = {
    "ADMIN": set(ALL_MODULES),
    "GERENTE": {
        "visao_geral",
        "cadastros",
        "compras",
        "estoque",
        "vendas",
        "operacional",
        "financeiro",
        "dashboard_bi",
    },
    "CAIXA": {
        "visao_geral",
        "cadastros",
        "vendas",
        "operacional",
    },
    "BARISTA": {
        "visao_geral",
        "estoque",
        "operacional",
    },
    "ESTOQUISTA": {
        "visao_geral",
        "cadastros",
        "compras",
        "estoque",
        "operacional",
    },
}

ACTION_PERMISSIONS: dict[str, set[str]] = {
    "cadastros:write": {"ADMIN", "GERENTE", "ESTOQUISTA"},
    "compras:write": {"ADMIN", "GERENTE", "ESTOQUISTA"},
    "estoque:adjust": {"ADMIN", "GERENTE", "ESTOQUISTA"},
    "vendas:create": {"ADMIN", "GERENTE", "CAIXA"},
    "vendas:cancel": {"ADMIN", "GERENTE"},
    "operacional:prepare": {"ADMIN", "GERENTE", "BARISTA", "CAIXA"},
    "operacional:loss": {"ADMIN", "GERENTE", "BARISTA", "ESTOQUISTA"},
    "financeiro:write": {"ADMIN", "GERENTE"},
    "usuarios:manage": {"ADMIN"},
}


def can_access_module(perfil: str, module_key: str) -> bool:
    """Retorna True se o perfil tem acesso ao módulo informado."""
    allowed = MODULE_PERMISSIONS.get(perfil.upper(), set())
    return module_key in allowed


def has_permission(perfil: str, action: str) -> bool:
    """Retorna True se o perfil pode executar a ação informada."""
    allowed = ACTION_PERMISSIONS.get(action, set())
    return perfil.upper() in allowed


def require_permission(perfil: str, action: str) -> None:
    """Lança AuthorizationError caso o perfil não possa executar a ação."""
    if not has_permission(perfil, action):
        raise AuthorizationError(
            f"Perfil '{perfil}' não possui permissão para a operação '{action}'."
        )
