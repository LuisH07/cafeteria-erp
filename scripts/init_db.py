"""Inicializa o banco PostgreSQL/Supabase aplicando schema, índices e views BI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db.connection import check_database_health, get_engine

SQL_FILES = (
    ROOT_DIR / "sql" / "001_schema.sql",
    ROOT_DIR / "sql" / "003_indexes_and_constraints.sql",
    ROOT_DIR / "sql" / "002_views_bi.sql",
)


def apply_sql_migrations() -> None:
    """Executa os scripts SQL de DDL, índices e views analíticas de forma idempotente."""
    health = check_database_health()
    if not health.get("ok"):
        raise RuntimeError(f"Falha ao conectar no PostgreSQL/Supabase: {health.get('error')}")

    print(f"[OK] Conectado ao banco '{health['database']}' ({health['version'].split(',')[0]})")

    engine = get_engine()
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            for sql_file in SQL_FILES:
                sql_content = sql_file.read_text(encoding="utf-8")
                cur.execute(sql_content)
                print(f"[OK] Script aplicado: {sql_file.relative_to(ROOT_DIR)}")
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()

    print("[CONCLUÍDO] Schema, índices e views analíticas aplicados com sucesso.")


if __name__ == "__main__":
    apply_sql_migrations()
