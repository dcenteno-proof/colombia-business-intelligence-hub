"""Inteligencia operacional: rotación, inventario bajo, productos sin movimiento,
abastecimiento por proveedor y evolución de costos."""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.analytics.metrics import days_of_inventory, inventory_turnover, pct, safe_divide


def average_inventory(snapshots: pd.DataFrame, start: date, end: date, by: str | None = None) -> pd.Series | float | None:
    """Inventario promedio valorizado al costo = promedio de las fotos de cierre
    incluidas en el periodo más la foto de apertura (cierre del mes anterior)."""
    if snapshots.empty:
        return None
    opening = pd.Timestamp(start) - pd.Timedelta(days=1)
    s = snapshots[(snapshots["fecha_corte"] >= opening) & (snapshots["fecha_corte"] <= pd.Timestamp(end))]
    if s.empty:
        return None
    if by is None:
        return float(s.groupby("fecha_corte").valor.sum().mean())
    return s.groupby([by, "fecha_corte"]).valor.sum().groupby(level=0).mean()


def turnover_summary(lines: pd.DataFrame, snapshots: pd.DataFrame, start: date, end: date) -> dict:
    days = (end - start).days + 1
    cogs = int(lines["costo_ventas"].sum()) if not lines.empty else 0
    avg_inv = average_inventory(snapshots, start, end)
    t = inventory_turnover(cogs, avg_inv)
    return {"costo_ventas": cogs, "inventario_promedio": avg_inv, "rotacion": t,
            "dias_inventario": days_of_inventory(t, days), "dias_periodo": days}


def turnover_by(lines: pd.DataFrame, snapshots: pd.DataFrame, start: date, end: date, by: str = "producto"
                ) -> pd.DataFrame:
    days = (end - start).days + 1
    avg_inv = average_inventory(snapshots, start, end, by=by)
    cogs = lines.groupby(by).costo_ventas.sum() if not lines.empty else pd.Series(dtype="int64")
    if avg_inv is None:
        return pd.DataFrame(columns=[by, "costo_ventas", "inventario_promedio", "rotacion", "dias_inventario"])
    df = pd.DataFrame({"inventario_promedio": avg_inv}).join(cogs.rename("costo_ventas"), how="outer").fillna(
        {"costo_ventas": 0})
    df["rotacion"] = [inventory_turnover(c, i) for c, i in zip(df["costo_ventas"], df["inventario_promedio"])]
    df["dias_inventario"] = [days_of_inventory(t, days) for t in df["rotacion"]]
    return df.reset_index().rename(columns={"index": by}).sort_values("rotacion", ascending=False, na_position="last")


def latest_stock(snapshots: pd.DataFrame, lines: pd.DataFrame | None = None, demand_days: int = 90) -> pd.DataFrame:
    """Inventario a la última fecha de corte, con días de cobertura según la demanda reciente."""
    if snapshots.empty:
        return pd.DataFrame()
    last_date = snapshots["fecha_corte"].max()
    s = snapshots[snapshots["fecha_corte"] == last_date].copy()
    s["bajo_minimo"] = s["cantidad"] <= s["stock_minimo"]
    if lines is not None and not lines.empty:
        recent = lines[(lines["fecha"] > last_date - pd.Timedelta(days=demand_days)) & (lines["fecha"] <= last_date)]
        daily = recent.groupby("producto_id").unidades_netas.sum() / demand_days
        s["demanda_diaria"] = s["producto_id"].map(daily).fillna(0.0)
        s["dias_cobertura"] = [safe_divide(q, d) if d > 0 else None for q, d in zip(s["cantidad"], s["demanda_diaria"])]
    else:
        s["demanda_diaria"] = None
        s["dias_cobertura"] = None
    return s.sort_values("cantidad").reset_index(drop=True)


def low_stock(snapshots: pd.DataFrame, lines: pd.DataFrame | None = None) -> pd.DataFrame:
    s = latest_stock(snapshots, lines)
    if s.empty:
        return s
    s = s[s["bajo_minimo"] & s["activo"].astype(bool)].copy()
    s["faltante_para_minimo"] = s["stock_minimo"] - s["cantidad"]
    return s


def no_movement(movements: pd.DataFrame, snapshots: pd.DataFrame, reference: date, days: int = 90) -> pd.DataFrame:
    """Productos con existencias y sin salidas por venta en los últimos ``days`` días."""
    if movements.empty or snapshots.empty:
        return pd.DataFrame()
    last = latest_stock(snapshots)
    df = movements.merge(last[["producto_id", "cantidad", "valor"]], on="producto_id", how="inner")
    ref = pd.Timestamp(reference)
    df["dias_sin_venta"] = (ref - df["ultima_salida"]).dt.days
    mask = (df["cantidad"] > 0) & (df["ultima_salida"].isna() | (df["dias_sin_venta"] > days))
    return df[mask].sort_values("valor", ascending=False).reset_index(drop=True)


def supplier_performance(purchases: pd.DataFrame) -> pd.DataFrame:
    """Compras y cumplimiento de abastecimiento por proveedor.

    * Nivel de servicio (fill rate) = unidades recibidas / unidades pedidas, sólo
      sobre órdenes cerradas (RECIBIDA o PARCIAL).
    * Entregas a tiempo = órdenes recibidas en o antes de la fecha esperada /
      órdenes con fecha de recepción registrada.
    Si no hay órdenes cerradas, los indicadores quedan en N/D.
    """
    cols = ["proveedor", "ordenes", "valor_pedido", "valor_recibido", "nivel_servicio", "entregas_a_tiempo",
            "lead_time_real_dias", "ordenes_pendientes"]
    if purchases.empty:
        return pd.DataFrame(columns=cols)
    p = purchases.copy()
    p["valor_pedido"] = p["cantidad_pedida"] * p["costo_unitario"]
    p["valor_recibido"] = p["cantidad_recibida"] * p["costo_unitario"]
    closed = p[p["estado"].isin(["RECIBIDA", "PARCIAL"])]
    orders = p.drop_duplicates("compra_id")
    closed_orders = orders[orders["fecha_recepcion"].notna()].copy()
    closed_orders["a_tiempo"] = closed_orders["fecha_recepcion"] <= closed_orders["fecha_esperada"]
    closed_orders["lead"] = (closed_orders["fecha_recepcion"] - closed_orders["fecha_orden"]).dt.days
    rows = []
    for sup, grp in p.groupby("proveedor"):
        cl = closed[closed["proveedor"] == sup]
        co = closed_orders[closed_orders["proveedor"] == sup]
        rows.append({
            "proveedor": sup, "ordenes": grp["compra_id"].nunique(),
            "valor_pedido": int(grp["valor_pedido"].sum()), "valor_recibido": int(grp["valor_recibido"].sum()),
            "nivel_servicio": pct(cl["cantidad_recibida"].sum(), cl["cantidad_pedida"].sum()) if not cl.empty else None,
            "entregas_a_tiempo": pct(co["a_tiempo"].sum(), len(co)) if not co.empty else None,
            "lead_time_real_dias": float(co["lead"].mean()) if not co.empty else None,
            "ordenes_pendientes": int((grp.drop_duplicates("compra_id")["estado"] == "PENDIENTE").sum()),
        })
    return pd.DataFrame(rows, columns=cols).sort_values("valor_pedido", ascending=False).reset_index(drop=True)


def cost_at(cost_history: pd.DataFrame, when: pd.Timestamp) -> pd.Series:
    """Costo vigente por producto a una fecha (última vigencia <= fecha)."""
    h = cost_history[cost_history["fecha_vigencia"] <= when].sort_values("fecha_vigencia")
    return h.groupby("producto_id").costo_unitario.last()


def cost_index_by_category(cost_history: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """Índice de costo unitario promedio por categoría (base 100 = primer mes)."""
    if cost_history.empty or not months:
        return pd.DataFrame(columns=["mes", "categoria", "indice"])
    cats = cost_history.drop_duplicates("producto_id").set_index("producto_id")["categoria"]
    base = cost_at(cost_history, pd.Period(months[0], "M").end_time)
    rows = []
    for mth in months:
        cur = cost_at(cost_history, pd.Period(mth, "M").end_time)
        rel = (cur / base.reindex(cur.index) * 100).dropna()
        for cat, val in rel.groupby(cats.reindex(rel.index)).mean().items():
            rows.append({"mes": mth, "categoria": cat, "indice": float(val)})
    return pd.DataFrame(rows)


def cost_changes(cost_history: pd.DataFrame, reference: date, window_days: int = 90) -> pd.DataFrame:
    """Variación del costo unitario por producto en la ventana [referencia - window, referencia]."""
    if cost_history.empty:
        return pd.DataFrame()
    ref = pd.Timestamp(reference)
    before = cost_at(cost_history, ref - pd.Timedelta(days=window_days))
    now = cost_at(cost_history, ref)
    info = cost_history.drop_duplicates("producto_id").set_index("producto_id")[["sku", "producto", "categoria"]]
    df = info.join(before.rename("costo_inicial"), how="inner").join(now.rename("costo_actual"), how="inner")
    df["variacion_pct"] = [pct(a - b, b) for a, b in zip(df["costo_actual"], df["costo_inicial"])]
    return df.reset_index().sort_values("variacion_pct", ascending=False).reset_index(drop=True)


def purchases_monthly(purchases: pd.DataFrame) -> pd.DataFrame:
    if purchases.empty:
        return pd.DataFrame(columns=["mes", "proveedor", "valor_pedido"])
    p = purchases.copy()
    p["mes"] = p["fecha_orden"].dt.to_period("M").astype(str)
    p["valor_pedido"] = p["cantidad_pedida"] * p["costo_unitario"]
    return p.groupby(["mes", "proveedor"]).valor_pedido.sum().reset_index()


def reference_date(lines: pd.DataFrame, fallback: date | None = None) -> date:
    if lines.empty:
        return fallback or date.today()
    return pd.Timestamp(lines["fecha"].max()).date()

