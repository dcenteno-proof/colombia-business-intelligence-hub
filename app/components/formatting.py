"""Formatos de presentación para Colombia: miles con punto, decimales con coma."""
from __future__ import annotations

import math

import pandas as pd

NA = "N/D"


def _missing(v) -> bool:
    if v is None:
        return True
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _co(number_str: str) -> str:
    """Convierte '1,234,567.8' (formato US) a '1.234.567,8'."""
    return number_str.replace(",", "§").replace(".", ",").replace("§", ".")


def cop(v, decimals: int = 0) -> str:
    if _missing(v):
        return NA
    sign = "-" if v < 0 else ""
    return f"{sign}$ {_co(f'{abs(v):,.{decimals}f}')}"


def cop_short(v) -> str:
    """Importes grandes en millones (M) — convención usual en reportes gerenciales en Colombia."""
    if _missing(v):
        return NA
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1_000_000:
        return f"{sign}$ {_co(f'{a / 1_000_000:,.1f}')} M"
    if a >= 1_000:
        return f"{sign}$ {_co(f'{a / 1_000:,.1f}')} mil"
    return cop(v)


def pct(v, decimals: int = 1, signed: bool = False) -> str:
    if _missing(v) or (isinstance(v, float) and not math.isfinite(v)):
        return NA
    fmt = f"{{:{'+' if signed else ''},.{decimals}f}}"
    return f"{_co(fmt.format(v))} %"


def pp(v, decimals: int = 1) -> str:
    if _missing(v):
        return NA
    return f"{_co(f'{v:+,.{decimals}f}')} pp"


def num(v, decimals: int = 0) -> str:
    if _missing(v):
        return NA
    return _co(f"{v:,.{decimals}f}")


def times(v) -> str:
    return NA if _missing(v) else f"{num(v, 2)} veces"


def days(v) -> str:
    return NA if _missing(v) else f"{num(v, 0)} días"
