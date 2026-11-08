"""Filtros globales (periodo, región, categoría, producto) aplicables a los hechos."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class Filters:
    start_month: str | None = None   # 'AAAA-MM'
    end_month: str | None = None     # 'AAAA-MM' (inclusive)
    regions: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    products: tuple[str, ...] = ()

    @property
    def dimension_filtered(self) -> bool:
        return bool(self.regions or self.categories or self.products)

    @property
    def n_months(self) -> int | None:
        if not self.start_month or not self.end_month:
            return None
        return (pd.Period(self.end_month, "M") - pd.Period(self.start_month, "M")).n + 1

    def bounds(self) -> tuple[date | None, date | None]:
        start = pd.Period(self.start_month, "M").start_time.date() if self.start_month else None
        end = pd.Period(self.end_month, "M").end_time.date() if self.end_month else None
        return start, end

    def previous_period(self) -> "Filters | None":
        """Periodo inmediatamente anterior de igual duración (para comparaciones)."""
        n = self.n_months
        if n is None:
            return None
        start = pd.Period(self.start_month, "M") - n
        end = pd.Period(self.start_month, "M") - 1
        return replace(self, start_month=str(start), end_month=str(end))

    def label(self) -> str:
        if not self.start_month:
            return "Todo el periodo"
        return self.start_month if self.start_month == self.end_month else f"{self.start_month} a {self.end_month}"


def apply_dimensions(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if f.regions and "region" in df:
        mask &= df["region"].isin(f.regions)
    if f.categories and "categoria" in df:
        mask &= df["categoria"].isin(f.categories)
    if f.products and "producto" in df:
        mask &= df["producto"].isin(f.products)
    return df[mask]


def apply_period(df: pd.DataFrame, f: Filters, month_col: str = "mes") -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if f.start_month:
        mask &= df[month_col] >= f.start_month
    if f.end_month:
        mask &= df[month_col] <= f.end_month
    return df[mask]


def apply_sales(lines: pd.DataFrame, f: Filters) -> pd.DataFrame:
    return apply_period(apply_dimensions(lines, f), f)


def apply_expenses(expenses: pd.DataFrame, f: Filters) -> pd.DataFrame | None:
    """Los gastos no se asignan por región/categoría/producto: con filtros de dimensión
    se devuelve ``None`` (no atribuible) para no mostrar una utilidad operacional engañosa."""
    if f.dimension_filtered:
        return None
    return apply_period(expenses, f)


def add_month(df: pd.DataFrame, date_col: str = "fecha") -> pd.DataFrame:
    out = df.copy()
    out["mes"] = pd.to_datetime(out[date_col]).dt.to_period("M").astype(str) if not out.empty else pd.Series(
        dtype="object")
    return out
