"""Inteligencia financiera: estado de resultados simplificado, variaciones y rentabilidad.

Importante: las cifras son de GESTIÓN, calculadas a partir de transacciones
operativas (facturas, costos estándar por línea y gastos registrados). No
sustituyen los estados financieros contables (no incluyen depreciaciones,
provisiones, impuestos, gastos financieros ni ajustes de cierre).
"""
from __future__ import annotations

import pandas as pd

from src.analytics.metrics import change_pp, growth_pct, pct, summarize

PNL_ROWS = [
    ("ventas_brutas", "Ventas brutas"),
    ("descuentos", "(-) Descuentos"),
    ("devoluciones", "(-) Devoluciones"),
    ("ventas_netas", "Ventas netas"),
    ("costo_ventas", "(-) Costo de ventas"),
    ("utilidad_bruta", "Utilidad bruta"),
    ("gastos_operativos", "(-) Gastos operativos"),
    ("utilidad_operacional", "Utilidad operacional"),
]


def income_statement(current_lines: pd.DataFrame, current_opex: int | None,
                     previous_lines: pd.DataFrame | None = None, previous_opex: int | None = None) -> pd.DataFrame:
    """Estado de resultados del periodo, con % sobre ventas netas y variación vs periodo anterior."""
    cur = summarize(current_lines, current_opex)
    prev = summarize(previous_lines, previous_opex) if previous_lines is not None and not previous_lines.empty \
        else None
    rows = []
    for key, label in PNL_ROWS:
        v = cur[key]
        p = prev[key] if prev else None
        rows.append({
            "concepto": label, "clave": key, "valor": v,
            "pct_ventas_netas": pct(v, cur["ventas_netas"]) if v is not None else None,
            "periodo_anterior": p,
            "variacion": (v - p) if v is not None and p is not None else None,
            "variacion_pct": growth_pct(v, p) if v is not None and p is not None else None,
        })
    return pd.DataFrame(rows)


def monthly_pnl(lines: pd.DataFrame, expenses: pd.DataFrame | None) -> pd.DataFrame:
    """Estado de resultados mensual con márgenes y variaciones mes a mes.

    ``expenses=None`` significa que los gastos no son atribuibles al filtro actual.
    """
    if lines.empty:
        return pd.DataFrame()
    g = lines.groupby("mes").agg(ventas_brutas=("ventas_brutas", "sum"), descuentos=("descuento", "sum"),
                                 devoluciones=("devoluciones", "sum"), ventas_netas=("ventas_netas", "sum"),
                                 costo_ventas=("costo_ventas", "sum"), utilidad_bruta=("utilidad_bruta", "sum"),
                                 transacciones=("venta_id", "nunique"))
    if expenses is not None:
        opex = expenses.groupby("mes").monto.sum() if not expenses.empty else pd.Series(dtype="int64")
        g["gastos_operativos"] = opex.reindex(g.index)
        g["utilidad_operacional"] = g["utilidad_bruta"] - g["gastos_operativos"]
    else:
        g["gastos_operativos"] = None
        g["utilidad_operacional"] = None
    g = g.reset_index().sort_values("mes").reset_index(drop=True)
    g["margen_bruto"] = [pct(u, v) for u, v in zip(g["utilidad_bruta"], g["ventas_netas"])]
    g["margen_operacional"] = [pct(u, v) if u is not None and pd.notna(u) else None
                               for u, v in zip(g["utilidad_operacional"], g["ventas_netas"])]
    g["gastos_sobre_ventas"] = [pct(o, v) if o is not None and pd.notna(o) else None
                                for o, v in zip(g["gastos_operativos"], g["ventas_netas"])]
    g["var_ventas_netas_pct"] = [None] + [growth_pct(c, p) for c, p in zip(g["ventas_netas"][1:], g["ventas_netas"][:-1])]
    g["var_utilidad_bruta_pct"] = [None] + [growth_pct(c, p) for c, p in
                                            zip(g["utilidad_bruta"][1:], g["utilidad_bruta"][:-1])]
    g["var_margen_bruto_pp"] = [None] + [change_pp(c, p) for c, p in zip(g["margen_bruto"][1:], g["margen_bruto"][:-1])]
    return g


def profitability_by(lines: pd.DataFrame, dim: str) -> pd.DataFrame:
    if lines.empty:
        return pd.DataFrame(columns=[dim, "ventas_netas", "costo_ventas", "utilidad_bruta", "margen_bruto",
                                     "participacion_utilidad"])
    g = lines.groupby(dim).agg(ventas_netas=("ventas_netas", "sum"), costo_ventas=("costo_ventas", "sum"),
                               utilidad_bruta=("utilidad_bruta", "sum")).reset_index()
    total_gp = g["utilidad_bruta"].sum()
    g["margen_bruto"] = [pct(u, v) for u, v in zip(g["utilidad_bruta"], g["ventas_netas"])]
    g["participacion_utilidad"] = [pct(u, total_gp) for u in g["utilidad_bruta"]]
    return g.sort_values("utilidad_bruta", ascending=False).reset_index(drop=True)


def financial_indicators(lines: pd.DataFrame, opex: int | None) -> list[dict]:
    """Indicadores de gestión con su fórmula, para mostrarse junto a la cifra."""
    s = summarize(lines, opex)
    return [
        {"indicador": "Margen bruto", "valor": s["margen_bruto"], "unidad": "%",
         "formula": "Utilidad bruta / Ventas netas × 100"},
        {"indicador": "Margen operacional", "valor": s["margen_operacional"], "unidad": "%",
         "formula": "Utilidad operacional / Ventas netas × 100"},
        {"indicador": "Costo de ventas sobre ventas", "valor": pct(s["costo_ventas"], s["ventas_netas"]), "unidad": "%",
         "formula": "Costo de ventas / Ventas netas × 100"},
        {"indicador": "Gastos operativos sobre ventas",
         "valor": pct(opex, s["ventas_netas"]) if opex is not None else None, "unidad": "%",
         "formula": "Gastos operativos / Ventas netas × 100"},
        {"indicador": "Tasa de descuento", "valor": pct(s["descuentos"], s["ventas_brutas"]), "unidad": "%",
         "formula": "Descuentos / Ventas brutas × 100"},
        {"indicador": "Tasa de devolución", "valor": pct(s["devoluciones"], s["ventas_brutas"]), "unidad": "%",
         "formula": "Devoluciones / Ventas brutas × 100"},
        {"indicador": "Ticket promedio", "valor": s["ticket_promedio"], "unidad": "COP",
         "formula": "Ventas netas / Número de facturas"},
    ]
