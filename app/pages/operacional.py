"""Inteligencia operacional: inventario, abastecimiento y costos."""
import pandas as pd
import streamlit as st

from app.components import charts, formatting as fmt, ui
from app.components.context import get_context
from src.analytics import operational as op
from src.analytics.alerts import evaluate_alerts
from src.analytics.filters import apply_dimensions
from src.config import NO_MOVEMENT_DAYS

ctx = get_context()
ui.page_header("Inteligencia operacional", "Inventario, rotación, abastecimiento y evolución de costos",
               period=ctx.f.label())

snaps_all = apply_dimensions(ctx.ds.snapshots, ctx.f)
snaps = snaps_all[snaps_all["fecha_corte"] <= pd.Timestamp(ctx.end)]
hist_lines = apply_dimensions(ctx.ds.lines, ctx.f)
hist_lines = hist_lines[hist_lines["fecha"] <= pd.Timestamp(ctx.end)]
purchases = apply_dimensions(ctx.ds.purchases, ctx.f)
purchases = purchases[(purchases["fecha_orden"] >= pd.Timestamp(ctx.start)) &
                      (purchases["fecha_orden"] <= pd.Timestamp(ctx.end))]

turn = op.turnover_summary(ctx.lines, snaps, ctx.start, ctx.end)
stock = op.latest_stock(snaps, hist_lines)
low = op.low_stock(snaps, hist_lines)
idle = op.no_movement(apply_dimensions(ctx.ds.movements, ctx.f), snaps, ctx.end, NO_MOVEMENT_DAYS)
sup = op.supplier_performance(purchases)
closed = purchases[purchases["estado"].isin(["RECIBIDA", "PARCIAL"])]
fill = (closed["cantidad_recibida"].sum() / closed["cantidad_pedida"].sum() * 100) if not closed.empty else None

ui.kpi_row([
    dict(label="Rotación de inventario", value=fmt.times(turn["rotacion"]), show_delta=False,
         foot=f"En {turn['dias_periodo']} días del periodo"),
    dict(label="Días de inventario", value=fmt.days(turn["dias_inventario"]), show_delta=False,
         foot="Días del periodo / rotación"),
    dict(label="Valor del inventario", value=fmt.cop_short(stock["valor"].sum() if not stock.empty else None),
         show_delta=False, foot=f"Corte {stock['fecha_corte'].max():%Y-%m-%d}" if not stock.empty else None),
    dict(label="Productos bajo mínimo", value=fmt.num(len(low)), show_delta=False,
         foot=f"Sin movimiento > {NO_MOVEMENT_DAYS} días: {len(idle)}"),
    dict(label="Nivel de servicio proveedores", value=fmt.pct(fill), show_delta=False,
         foot="Unidades recibidas / pedidas (órdenes cerradas)"),
])

tab_inv, tab_rot, tab_sup, tab_cost, tab_alert = st.tabs(["Inventario", "Rotación", "Proveedores", "Costos",
                                                         "Alertas operativas"])
stock_rename = {"producto": "Producto", "categoria": "Categoría", "cantidad": "Existencias", "stock_minimo": "Mínimo",
                "valor": "Valor al costo", "dias_cobertura": "Días de cobertura", "demanda_diaria": "Demanda diaria",
                "faltante_para_minimo": "Faltante para mínimo", "sku": "SKU", "ultima_salida": "Última venta",
                "dias_sin_venta": "Días sin venta", "fecha_corte": "Fecha de corte"}
with tab_inv:
    ui.section("Productos con inventario bajo el mínimo")
    ui.table(low[["sku", "producto", "categoria", "cantidad", "stock_minimo", "faltante_para_minimo",
                  "demanda_diaria", "dias_cobertura"]] if not low.empty else low,
             integers=["cantidad", "stock_minimo", "faltante_para_minimo"], decimals=["demanda_diaria", "dias_cobertura"],
             rename=stock_rename)
    ui.section(f"Productos sin movimiento (sin ventas en más de {NO_MOVEMENT_DAYS} días y con existencias)")
    ui.table(idle[["sku", "producto", "categoria", "cantidad", "valor", "ultima_salida", "dias_sin_venta"]]
             if not idle.empty else idle, money=["valor"], integers=["cantidad", "dias_sin_venta"],
             dates=["ultima_salida"], rename=stock_rename)
    with st.expander("Existencias de todos los productos"):
        ui.table(stock[["fecha_corte", "sku", "producto", "categoria", "cantidad", "stock_minimo", "valor",
                        "dias_cobertura"]] if not stock.empty else stock, money=["valor"],
                 integers=["cantidad", "stock_minimo"], decimals=["dias_cobertura"], dates=["fecha_corte"],
                 rename=stock_rename)

with tab_rot:
    by_cat = op.turnover_by(ctx.lines, snaps, ctx.start, ctx.end, "categoria")
    by_prod = op.turnover_by(ctx.lines, snaps, ctx.start, ctx.end, "producto")
    st.caption("Rotación = costo de ventas del periodo / inventario promedio al costo (promedio de la foto de "
               "apertura y las fotos de cierre de cada mes del periodo).")
    if not by_cat.empty:
        charts.show(charts.hbar(by_cat.dropna(subset=["rotacion"]), "rotacion", "categoria",
                                "Rotación por categoría (veces en el periodo)", money=False, height=340))
    rot_rename = {"categoria": "Categoría", "producto": "Producto", "costo_ventas": "Costo de ventas",
                  "inventario_promedio": "Inventario promedio", "rotacion": "Rotación (veces)",
                  "dias_inventario": "Días de inventario"}
    ui.table(by_prod, money=["costo_ventas", "inventario_promedio"], decimals=["rotacion", "dias_inventario"],
             rename=rot_rename)

with tab_sup:
    st.caption("Nivel de servicio = unidades recibidas / pedidas en órdenes cerradas. Entregas a tiempo = órdenes "
               "recibidas en o antes de la fecha esperada. Las órdenes pendientes no entran en estos cálculos.")
    if not sup.empty:
        charts.show(charts.stacked(op.purchases_monthly(purchases), "mes", "valor_pedido", "proveedor",
                                   "Compras mensuales por proveedor (valor pedido)"))
    ui.table(sup, money=["valor_pedido", "valor_recibido"], percent=["nivel_servicio", "entregas_a_tiempo"],
             decimals=["lead_time_real_dias"], integers=["ordenes", "ordenes_pendientes"],
             rename={"proveedor": "Proveedor", "ordenes": "Órdenes", "valor_pedido": "Valor pedido",
                     "valor_recibido": "Valor recibido", "nivel_servicio": "Nivel de servicio",
                     "entregas_a_tiempo": "Entregas a tiempo", "lead_time_real_dias": "Lead time real (días)",
                     "ordenes_pendientes": "Pendientes"})

with tab_cost:
    costs = apply_dimensions(ctx.ds.costs, ctx.f)
    months = [m for m in ctx.ds.months if (ctx.f.start_month or "") <= m <= (ctx.f.end_month or "9999")]
    idx = op.cost_index_by_category(costs, months)
    if not idx.empty:
        charts.show(charts.lines(idx, "mes", "indice", "categoria",
                                 f"Índice de costo unitario por categoría (base 100 = {months[0]})", money=False))
    ui.section("Variación de costo unitario en los últimos 90 días")
    ch = op.cost_changes(costs, ctx.end, 90)
    ui.table(ch.head(25), money=["costo_inicial", "costo_actual"], percent=["variacion_pct"],
             rename={"sku": "SKU", "producto": "Producto", "categoria": "Categoría", "costo_inicial": "Costo hace 90 días",
                     "costo_actual": "Costo actual", "variacion_pct": "Variación"})

with tab_alert:
    alerts, _, month = evaluate_alerts(ctx.ds.lines, ctx.ds.expenses, ctx.ds.snapshots, ctx.ds.costs,
                                       end_month=ctx.f.end_month)
    ops = alerts[alerts["modulo"] == "Operacional"] if not alerts.empty else alerts
    if ops.empty:
        st.success(f"Sin alertas operativas para {month}.", icon=":material/task_alt:")
    for _, a in ops.iterrows():
        ui.alert_card(a.to_dict())
