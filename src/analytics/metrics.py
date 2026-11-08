"""Fórmulas financieras y comerciales (funciones puras y verificables).

Convenciones:
  * Los importes llegan como enteros COP; las funciones de ratio devuelven ``float``.
  * Cuando un indicador no puede calcularse (denominador cero, nulo o datos
    faltantes) se devuelve ``None`` en lugar de 0, infinito o NaN, para que la
    interfaz muestre "N/D" con una explicación y no una cifra engañosa.
  * Los porcentajes se devuelven en escala 0-100 (p. ej. 23.5 = 23,5 %).
"""
from __future__ import annotations

import math
from numbers import Number

import pandas as pd


def _is_missing(x) -> bool:
    if x is None:
        return True
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def safe_divide(numerator, denominator) -> float | None:
    """División protegida: ``None`` si algún término falta o el denominador es 0."""
    if _is_missing(numerator) or _is_missing(denominator):
        return None
    if denominator == 0:
        return None
    result = float(numerator) / float(denominator)
    return result if math.isfinite(result) else None


def pct(numerator, denominator) -> float | None:
    r = safe_divide(numerator, denominator)
    return None if r is None else r * 100.0


# --------------------------------------------------------------- fórmulas base
def net_sales(gross_sales: Number, discounts: Number = 0, returns: Number = 0) -> Number:
    """Ventas netas = ventas brutas - descuentos - devoluciones."""
    if _is_missing(gross_sales):
        raise ValueError("Las ventas brutas son obligatorias")
    if discounts is not None and discounts < 0 or returns is not None and returns < 0:
        raise ValueError("Descuentos y devoluciones deben ser valores no negativos")
    return gross_sales - (discounts or 0) - (returns or 0)


def gross_profit(net: Number, cost_of_sales: Number) -> Number:
    """Utilidad bruta = ventas netas - costo de ventas."""
    return net - cost_of_sales


def gross_margin_pct(gross_profit_value: Number, net: Number) -> float | None:
    """Margen bruto = utilidad bruta / ventas netas × 100."""
    return pct(gross_profit_value, net)


def operating_profit(gross_profit_value: Number, operating_expenses: Number) -> Number:
    """Utilidad operacional = utilidad bruta - gastos operativos."""
    return gross_profit_value - operating_expenses


def operating_margin_pct(operating_profit_value: Number, net: Number) -> float | None:
    """Margen operacional = utilidad operacional / ventas netas × 100."""
    return pct(operating_profit_value, net)


def average_ticket(net: Number, transactions: int) -> float | None:
    """Ticket promedio = ventas netas / número de transacciones."""
    return safe_divide(net, transactions)


def growth_pct(current, previous) -> float | None:
    """Crecimiento % = (actual - anterior) / anterior × 100.

    No se calcula si el valor anterior falta, es cero o negativo: con una base
    negativa el signo del crecimiento pierde interpretación económica.
    """
    if _is_missing(current) or _is_missing(previous) or previous <= 0:
        return None
    return (float(current) - float(previous)) / float(previous) * 100.0


def inventory_turnover(cost_of_sales: Number, average_inventory: Number) -> float | None:
    """Rotación de inventario = costo de ventas / inventario promedio (veces en el periodo)."""
    if _is_missing(average_inventory) or average_inventory <= 0:
        return None
    return safe_divide(cost_of_sales, average_inventory)


def days_of_inventory(turnover: float | None, days_in_period: int) -> float | None:
    """Días de inventario = días del periodo / rotación."""
    if turnover is None or turnover <= 0:
        return None
    return days_in_period / turnover


def change_pp(current: float | None, previous: float | None) -> float | None:
    """Variación en puntos porcentuales entre dos porcentajes."""
    if current is None or previous is None:
        return None
    return current - previous


# ------------------------------------------------- cálculo vectorizado de líneas
def enrich_sales_lines(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas monetarias por línea, en enteros COP.

    * ``ventas_brutas`` = cantidad × precio_unitario
    * ``devoluciones`` = cantidad_devuelta × precio neto de descuento por unidad
      (las devoluciones se valoran al precio efectivamente facturado)
    * ``ventas_netas`` = ventas_brutas - descuento - devoluciones
    * ``costo_ventas`` = (cantidad - cantidad_devuelta) × costo_unitario
      (las unidades devueltas regresan al inventario y no generan costo)
    """
    out = df.copy()
    if out.empty:
        for col in ["ventas_brutas", "devoluciones", "ventas_netas", "costo_ventas", "utilidad_bruta",
                    "unidades_netas"]:
            out[col] = pd.Series(dtype="int64")
        out["mes"] = pd.Series(dtype="object")
        return out
    qty = out["cantidad"].astype("int64")
    ret = out["cantidad_devuelta"].fillna(0).astype("int64")
    price = out["precio_unitario"].astype("int64")
    disc = out["descuento"].fillna(0).astype("int64")
    gross = qty * price
    net_before_returns = gross - disc
    # redondeo entero "half-up" de ret * (bruto - desc) / qty, sin pasar por float
    returns_value = (2 * ret * net_before_returns + qty) // (2 * qty)
    out["ventas_brutas"] = gross
    out["devoluciones"] = returns_value
    out["ventas_netas"] = gross - disc - returns_value
    out["costo_ventas"] = (qty - ret) * out["costo_unitario"].astype("int64")
    out["utilidad_bruta"] = out["ventas_netas"] - out["costo_ventas"]
    out["unidades_netas"] = qty - ret
    out["mes"] = pd.to_datetime(out["fecha"]).dt.to_period("M").astype(str)
    return out


def summarize(lines: pd.DataFrame, opex_total: int | None) -> dict:
    """KPIs de un conjunto de líneas de venta ya enriquecidas.

    ``opex_total=None`` indica que los gastos no son atribuibles al filtro
    actual; en ese caso la utilidad y el margen operacional quedan en ``None``.
    """
    gross = int(lines["ventas_brutas"].sum()) if not lines.empty else 0
    disc = int(lines["descuento"].sum()) if not lines.empty else 0
    rets = int(lines["devoluciones"].sum()) if not lines.empty else 0
    net = net_sales(gross, disc, rets)
    cogs = int(lines["costo_ventas"].sum()) if not lines.empty else 0
    gp = gross_profit(net, cogs)
    tx = int(lines["venta_id"].nunique()) if not lines.empty else 0
    op = operating_profit(gp, opex_total) if opex_total is not None else None
    return {
        "ventas_brutas": gross,
        "descuentos": disc,
        "devoluciones": rets,
        "ventas_netas": net,
        "costo_ventas": cogs,
        "utilidad_bruta": gp,
        "margen_bruto": gross_margin_pct(gp, net),
        "gastos_operativos": opex_total,
        "utilidad_operacional": op,
        "margen_operacional": operating_margin_pct(op, net) if op is not None else None,
        "transacciones": tx,
        "ticket_promedio": average_ticket(net, tx),
        "clientes_activos": int(lines["cliente_id"].nunique()) if not lines.empty else 0,
        "unidades": int(lines["unidades_netas"].sum()) if not lines.empty else 0,
    }
