"""Configuración central del proyecto.

Lee variables de entorno (opcionalmente desde un archivo ``.env``) y expone
valores tipados. Ningún secreto se escribe en el código: si en el futuro se
conecta una base de datos con credenciales, éstas deben ir en ``.env``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
DOCS_DIR = PROJECT_ROOT / "docs"

COMPANY_NAME = "Distribuidora Andina DEMO S.A.S."
DEMO_LABEL = "DEMO"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:  # configuración inválida: fallar con mensaje claro
        raise ValueError(f"La variable {name} debe ser numérica, se recibió {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, default))


def database_url() -> str:
    """URL de conexión. Por defecto un archivo SQLite dentro de data/processed."""
    url = os.getenv("CBH_DATABASE_URL", "").strip()
    if url:
        return url
    return f"sqlite:///{(PROCESSED_DIR / 'cbh_demo.db').as_posix()}"


@dataclass(frozen=True)
class AlertThresholds:
    """Umbrales de las reglas de negocio del centro de alertas (configurables por .env)."""

    sales_drop_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_SALES_DROP_PCT", 15.0))
    region_sales_drop_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_REGION_DROP_PCT", 20.0))
    margin_drop_pp: float = field(default_factory=lambda: _env_float("CBH_ALERT_MARGIN_DROP_PP", 2.0))
    category_margin_drop_pp: float = field(default_factory=lambda: _env_float("CBH_ALERT_CAT_MARGIN_DROP_PP", 3.0))
    top_customer_share_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_TOP1_SHARE_PCT", 10.0))
    top10_customer_share_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_TOP10_SHARE_PCT", 50.0))
    cost_increase_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_COST_INCREASE_PCT", 8.0))
    opex_ratio_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_OPEX_RATIO_PCT", 24.0))
    opex_increase_pct: float = field(default_factory=lambda: _env_float("CBH_ALERT_OPEX_INCREASE_PCT", 15.0))
    min_months_history: int = field(default_factory=lambda: _env_int("CBH_ALERT_MIN_MONTHS", 3))
    min_customers_concentration: int = field(default_factory=lambda: _env_int("CBH_ALERT_MIN_CUSTOMERS", 20))


ACTIVE_CUSTOMER_DAYS = _env_int("CBH_ACTIVE_CUSTOMER_DAYS", 90)
NO_MOVEMENT_DAYS = _env_int("CBH_NO_MOVEMENT_DAYS", 90)
MAX_UPLOAD_MB = _env_int("CBH_MAX_UPLOAD_MB", 20)
