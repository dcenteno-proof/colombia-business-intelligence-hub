"""Fixtures compartidas. Cada prueba usa una base SQLite temporal (nunca la base real)."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analytics.dataset import load_dataset  # noqa: E402
from src.analytics.metrics import enrich_sales_lines  # noqa: E402
from src.data.demo_generator import DemoConfig, load_demo  # noqa: E402
from src.database.connection import dispose_engine, get_engine, init_db  # noqa: E402

SMALL = DemoConfig(start=date(2025, 1, 1), end=date(2025, 8, 31), n_customers=60, invoices_per_month=60, seed=7)


@pytest.fixture()
def engine(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    eng = get_engine(url)
    init_db(eng)
    yield eng
    dispose_engine(url)


@pytest.fixture(scope="session")
def demo_engine(tmp_path_factory):
    path = tmp_path_factory.mktemp("demo") / "demo.db"
    url = f"sqlite:///{path.as_posix()}"
    eng = get_engine(url)
    load_demo(eng, SMALL)
    yield eng
    dispose_engine(url)


@pytest.fixture(scope="session")
def demo_dataset(demo_engine):
    return load_dataset(demo_engine)


@pytest.fixture()
def seeded_engine(tmp_path):
    """Base pequeña y aislada para pruebas que escriben (ETL)."""
    url = f"sqlite:///{(tmp_path / 'etl.db').as_posix()}"
    eng = get_engine(url)
    load_demo(eng, DemoConfig(start=date(2025, 1, 1), end=date(2025, 3, 31), n_customers=80,
                              invoices_per_month=30, seed=11))
    yield eng
    dispose_engine(url)


def make_lines(rows: list[dict]) -> pd.DataFrame:
    """Construye líneas de venta mínimas para pruebas de analítica."""
    defaults = {"cantidad_devuelta": 0, "descuento": 0, "region": "Andina", "categoria": "Abarrotes",
                "producto": "Producto A", "producto_id": 1, "cliente": "Cliente 1", "cliente_id": 1,
                "tipo_cliente": "Tienda de barrio", "vendedor": "V1", "canal": "Preventa", "costo_unitario": 70}
    data = [defaults | r for r in rows]
    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return enrich_sales_lines(df)
