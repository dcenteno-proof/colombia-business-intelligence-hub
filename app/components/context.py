"""Contexto común de cada página: datos filtrados del periodo actual y del anterior."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

from app.components import state
from src.analytics.dataset import Dataset
from src.analytics.filters import Filters, apply_expenses, apply_sales


@dataclass
class PageContext:
    ds: Dataset
    f: Filters
    lines: pd.DataFrame
    expenses: pd.DataFrame | None
    prev_f: Filters | None
    prev_lines: pd.DataFrame | None
    prev_expenses: pd.DataFrame | None
    start: date
    end: date

    @property
    def opex(self) -> int | None:
        return int(self.expenses["monto"].sum()) if self.expenses is not None else None

    @property
    def prev_opex(self) -> int | None:
        if self.prev_expenses is None or self.prev_lines is None or self.prev_lines.empty:
            return None
        return int(self.prev_expenses["monto"].sum())

    @property
    def has_previous(self) -> bool:
        return self.prev_lines is not None and not self.prev_lines.empty


def get_context() -> PageContext:
    ds = state.dataset()
    f = state.current_filters()
    if ds.is_empty:
        st.warning("La base de datos no tiene ventas. Cargue información desde el Centro de datos.")
        st.stop()
    lines = apply_sales(ds.lines, f)
    prev_f = f.previous_period()
    prev_lines = apply_sales(ds.lines, prev_f) if prev_f else None
    # Si el periodo anterior queda parcialmente fuera del histórico, no es comparable.
    if prev_f and prev_lines is not None and ds.months and prev_f.start_month < ds.months[0]:
        prev_lines = None
    start, end = f.bounds()
    start = start or ds.lines["fecha"].min().date()
    end = min(end or ds.lines["fecha"].max().date(), ds.lines["fecha"].max().date())
    return PageContext(ds=ds, f=f, lines=lines, expenses=apply_expenses(ds.expenses, f), prev_f=prev_f,
                       prev_lines=prev_lines, prev_expenses=apply_expenses(ds.expenses, prev_f) if prev_f else None,
                       start=start, end=end)
