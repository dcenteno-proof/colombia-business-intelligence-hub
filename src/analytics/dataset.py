"""Carga y preparación del conjunto de datos analítico (una sola lectura de la base)."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Engine

from src.analytics.filters import add_month
from src.analytics.metrics import enrich_sales_lines
from src.database import repository as repo


@dataclass
class Dataset:
    lines: pd.DataFrame          # líneas de venta enriquecidas (montos COP enteros)
    expenses: pd.DataFrame       # gastos operativos con columna 'mes'
    purchases: pd.DataFrame      # líneas de compra
    snapshots: pd.DataFrame      # fotos de inventario de fin de mes
    movements: pd.DataFrame      # resumen del kardex por producto
    costs: pd.DataFrame          # historial de costos
    products: pd.DataFrame
    customers: pd.DataFrame

    @property
    def months(self) -> list[str]:
        return sorted(self.lines["mes"].unique().tolist()) if not self.lines.empty else []

    @property
    def is_empty(self) -> bool:
        return self.lines.empty


def load_dataset(engine: Engine | None = None) -> Dataset:
    return Dataset(
        lines=enrich_sales_lines(repo.sales_lines(engine)),
        expenses=add_month(repo.expenses(engine)),
        purchases=repo.purchase_lines(engine),
        snapshots=repo.inventory_snapshots(engine),
        movements=repo.movements_summary(engine),
        costs=repo.cost_history(engine),
        products=repo.products(engine),
        customers=repo.customers(engine),
    )
