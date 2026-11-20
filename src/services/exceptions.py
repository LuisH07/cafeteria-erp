"""Exceções de domínio da camada de serviços do ERP."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Erro base de regra de negócio do ERP."""


class ValidationError(DomainError):
    """Dados de entrada inválidos."""


class NotFoundError(DomainError):
    """Registro não encontrado."""


class BusinessRuleError(DomainError):
    """Violação de regra de negócio do domínio da cafeteria."""


class InsufficientStockError(BusinessRuleError):
    """Estoque insuficiente para um ou mais insumos da operação."""

    def __init__(self, message: str, missing_items: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.missing_items = missing_items or []


class AuthorizationError(DomainError):
    """Usuário sem permissão para executar a ação solicitada."""
