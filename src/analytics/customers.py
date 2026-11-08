"""Inteligencia de clientes: métricas por cliente, actividad y segmentación RFM.

Metodología RFM (básica, por quintiles):
  * R (recencia): días entre la última compra y la fecha de referencia
    (día siguiente al cierre del periodo). Menos días = mejor puntaje.
  * F (frecuencia): número de facturas en el periodo.
  * M (valor monetario): ventas netas en el periodo (COP).
  Cada dimensión se puntúa de 1 a 5 por quintiles sobre el rango (``rank``),
  lo que evita fallas cuando hay muchos empates. FM = promedio de F y M.
  Las reglas de segmento se evalúan en orden (ver ``segment_for``).
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.analytics.metrics import safe_divide

MIN_CUSTOMERS_RFM = 10

SEGMENT_ACTIONS = {
    "Campeones": "Fidelizar: beneficios por volumen, acceso prioritario a lanzamientos.",
    "Leales": "Venta cruzada de categorías complementarias y acuerdos anuales.",
    "Nuevos": "Acompañamiento en primeras compras y visitas de seguimiento.",
    "Potenciales leales": "Aumentar frecuencia con promociones escalonadas.",
    "En riesgo": "Contacto comercial inmediato: eran clientes valiosos y llevan tiempo sin comprar.",
    "Hibernando": "Campaña de reactivación con oferta específica.",
    "Perdidos": "Reactivación de bajo costo (televenta) o depurar de la cartera activa.",
}


class InsufficientDataError(ValueError):
    """No hay datos suficientes para producir un resultado confiable."""


def customer_metrics(lines: pd.DataFrame, reference: date) -> pd.DataFrame:
    """Recencia, frecuencia, valor y ticket por cliente."""
    cols = ["cliente_id", "cliente", "tipo_cliente", "region", "primera_compra", "ultima_compra", "recencia_dias",
            "frecuencia", "valor", "ticket_promedio", "dias_entre_compras"]
    if lines.empty:
        return pd.DataFrame(columns=cols)
    inv = lines.groupby(["cliente_id", "venta_id"]).agg(fecha=("fecha", "first"), neto=("ventas_netas", "sum"))
    inv = inv.reset_index()
    g = inv.groupby("cliente_id").agg(primera_compra=("fecha", "min"), ultima_compra=("fecha", "max"),
                                      frecuencia=("venta_id", "nunique"), valor=("neto", "sum"))
    attrs = lines.groupby("cliente_id")[["cliente", "tipo_cliente", "region"]].first()
    g = attrs.join(g).reset_index()
    ref = pd.Timestamp(reference)
    g["recencia_dias"] = (ref - g["ultima_compra"]).dt.days
    g["ticket_promedio"] = [safe_divide(v, f) for v, f in zip(g["valor"], g["frecuencia"])]
    g["dias_entre_compras"] = [
        (u - p).days / (f - 1) if f > 1 else None
        for p, u, f in zip(g["primera_compra"], g["ultima_compra"], g["frecuencia"])]
    return g[cols].sort_values("valor", ascending=False).reset_index(drop=True)


def _quintile_score(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    ranks = values.rank(method="first", ascending=higher_is_better)
    return pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int)


def segment_for(r: int, f: int, m: int) -> str:
    fm = (f + m) / 2
    if r >= 4 and fm >= 4:
        return "Campeones"
    if r >= 3 and fm >= 3.5:
        return "Leales"
    if r >= 4 and f <= 2:
        return "Nuevos"
    if r >= 3:
        return "Potenciales leales"
    if fm >= 3.5:
        return "En riesgo"
    if r == 2:
        return "Hibernando"
    return "Perdidos"


def rfm(lines: pd.DataFrame, reference: date, min_customers: int = MIN_CUSTOMERS_RFM) -> pd.DataFrame:
    """Calcula puntajes R, F, M y el segmento por cliente.

    Lanza ``InsufficientDataError`` si hay menos de ``min_customers`` clientes,
    porque los quintiles no serían representativos.
    """
    cm = customer_metrics(lines, reference)
    if len(cm) < min_customers:
        raise InsufficientDataError(
            f"Se requieren al menos {min_customers} clientes con compras para la segmentación RFM "
            f"(hay {len(cm)}).")
    cm["R"] = _quintile_score(cm["recencia_dias"], higher_is_better=False)
    cm["F"] = _quintile_score(cm["frecuencia"])
    cm["M"] = _quintile_score(cm["valor"])
    cm["RFM"] = cm["R"].astype(str) + cm["F"].astype(str) + cm["M"].astype(str)
    cm["segmento"] = [segment_for(r, f, m) for r, f, m in zip(cm["R"], cm["F"], cm["M"])]
    cm["accion_sugerida"] = cm["segmento"].map(SEGMENT_ACTIONS)
    return cm


def segment_summary(rfm_df: pd.DataFrame) -> pd.DataFrame:
    if rfm_df.empty:
        return pd.DataFrame()
    total = rfm_df["valor"].sum()
    g = rfm_df.groupby("segmento").agg(clientes=("cliente_id", "count"), valor=("valor", "sum"),
                                       recencia_promedio=("recencia_dias", "mean"),
                                       frecuencia_promedio=("frecuencia", "mean")).reset_index()
    g["participacion_valor"] = g["valor"] / total * 100 if total else None
    g["accion_sugerida"] = g["segmento"].map(SEGMENT_ACTIONS)
    order = list(SEGMENT_ACTIONS)
    g["orden"] = g["segmento"].map(order.index)
    return g.sort_values("orden").drop(columns="orden").reset_index(drop=True)


def activity_status(history_lines: pd.DataFrame, customers: pd.DataFrame, reference: date,
                    active_days: int = 90) -> pd.DataFrame:
    """Clasifica cada cliente registrado a la fecha de referencia como Activo / Inactivo / Sin compras.

    Usa todo el historial hasta la fecha de referencia (no sólo el periodo filtrado).
    """
    ref = pd.Timestamp(reference)
    reg = customers[customers["fecha_registro"] <= ref].copy()
    hist = history_lines[history_lines["fecha"] <= ref]
    last = hist.groupby("cliente_id").fecha.max()
    reg["ultima_compra"] = reg["cliente_id"].map(last)
    reg["dias_sin_compra"] = (ref - reg["ultima_compra"]).dt.days
    reg["estado"] = [
        "Sin compras" if pd.isna(d) else ("Activo" if d <= active_days else "Inactivo")
        for d in reg["dias_sin_compra"]]
    return reg


def reference_for_period(end: date) -> date:
    return end + timedelta(days=1)
