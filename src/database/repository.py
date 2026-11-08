"""Capa de acceso a datos: ejecuta las consultas de ``sql/queries`` y devuelve DataFrames.

Todas las consultas usan parámetros enlazados (``:nombre``) mediante
``sqlalchemy.text``; nunca se concatenan valores de usuario en el SQL.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any

import pandas as pd
from sqlalchemy import Engine, text

from src.config import PROJECT_ROOT
from src.database.connection import get_engine
from src.database.models import ALL_TABLES

QUERIES_DIR = PROJECT_ROOT / "sql" / "queries"
MIN_DATE = date(1900, 1, 1)
MAX_DATE = date(2999, 12, 31)


@lru_cache(maxsize=None)
def load_query(name: str) -> str:
    path = QUERIES_DIR / f"{name}.sql"
    if not path.exists():
        raise FileNotFoundError(f"No existe la consulta {path}")
    # Se eliminan los comentarios de línea: un ":nombre" documentado en un
    # comentario se interpretaría como parámetro enlazado.
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.strip().startswith("--")]
    return "\n".join(lines)


def run_query(name: str, params: dict[str, Any] | None = None, engine: Engine | None = None,
              parse_dates: list[str] | None = None) -> pd.DataFrame:
    params = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in (params or {}).items()}
    with (engine or get_engine()).connect() as conn:
        df = pd.read_sql_query(text(load_query(name)), conn, params=params)
    for col in parse_dates or []:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _range(start: date | None, end: date | None) -> dict[str, date]:
    return {"fecha_inicio": start or MIN_DATE, "fecha_fin": end or MAX_DATE}


def sales_lines(engine: Engine | None = None, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    return run_query("ventas_detalle", _range(start, end), engine, ["fecha"])


def expenses(engine: Engine | None = None, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    return run_query("gastos", _range(start, end), engine, ["fecha"])


def purchase_lines(engine: Engine | None = None, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    return run_query("compras_detalle", _range(start, end), engine,
                     ["fecha_orden", "fecha_esperada", "fecha_recepcion"])


def inventory_snapshots(engine: Engine | None = None) -> pd.DataFrame:
    return run_query("inventario", engine=engine, parse_dates=["fecha_corte"])


def movements_summary(engine: Engine | None = None) -> pd.DataFrame:
    return run_query("movimientos_resumen", engine=engine, parse_dates=["ultima_salida", "ultima_entrada"])


def cost_history(engine: Engine | None = None) -> pd.DataFrame:
    return run_query("costos", engine=engine, parse_dates=["fecha_vigencia"])


def products(engine: Engine | None = None) -> pd.DataFrame:
    return run_query("productos", engine=engine)


def customers(engine: Engine | None = None) -> pd.DataFrame:
    return run_query("clientes", engine=engine, parse_dates=["fecha_registro"])


def date_range(engine: Engine | None = None) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    df = run_query("rango_fechas", engine=engine)
    if df.empty or pd.isna(df.loc[0, "fecha_min"]):
        return None, None
    return pd.Timestamp(df.loc[0, "fecha_min"]), pd.Timestamp(df.loc[0, "fecha_max"])


def read_table(table: str, engine: Engine | None = None, limit: int = 1000) -> pd.DataFrame:
    """Lectura genérica para el Centro de datos. El nombre de tabla se valida contra
    una lista blanca (no puede parametrizarse en SQL) y el límite va como parámetro."""
    if table not in ALL_TABLES:
        raise ValueError(f"Tabla no permitida: {table!r}")
    limit = max(1, min(int(limit), 100_000))
    with (engine or get_engine()).connect() as conn:
        return pd.read_sql_query(text(f'SELECT * FROM "{table}" ORDER BY id DESC LIMIT :limite'), conn,
                                 params={"limite": limit})


def table_counts(engine: Engine | None = None) -> pd.DataFrame:
    rows = []
    with (engine or get_engine()).connect() as conn:
        for table in ALL_TABLES:
            n = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
            rows.append({"tabla": table, "registros": int(n or 0)})
    return pd.DataFrame(rows)


def table_schema(table: str, engine: Engine | None = None) -> pd.DataFrame:
    if table not in ALL_TABLES:
        raise ValueError(f"Tabla no permitida: {table!r}")
    with (engine or get_engine()).connect() as conn:
        cols = pd.read_sql_query(text(f'PRAGMA table_info("{table}")'), conn)
        fks = pd.read_sql_query(text(f'PRAGMA foreign_key_list("{table}")'), conn)
    cols = cols.rename(columns={"name": "columna", "type": "tipo", "notnull": "obligatoria", "pk": "llave_primaria",
                                "dflt_value": "valor_defecto"})[["columna", "tipo", "obligatoria", "llave_primaria",
                                                                 "valor_defecto"]]
    fk_map = {r["from"]: f'{r["table"]}.{r["to"]}' for _, r in fks.iterrows()} if not fks.empty else {}
    cols["llave_foranea"] = cols["columna"].map(fk_map).fillna("")
    cols["obligatoria"] = cols["obligatoria"].astype(bool)
    cols["llave_primaria"] = cols["llave_primaria"].astype(bool)
    return cols


def import_log(engine: Engine | None = None, limit: int = 200) -> pd.DataFrame:
    return read_table("registro_importaciones", engine, limit)
