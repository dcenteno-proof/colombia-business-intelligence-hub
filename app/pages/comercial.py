"""Inteligencia comercial."""
import pandas as pd
import streamlit as st

from app.components import charts, formatting as fmt, ui
from app.components.context import get_context
from src.analytics import commercial
from src.analytics.metrics import growth_pct, summarize

ctx = get_context()
ui.page_header("Inteligencia comercial", "Ventas por producto, categoría, región, vendedor y cliente",
               period=ctx.f.label())

cur = summarize(ctx.lines, None)
prev = summarize(ctx.prev_lines, None) if ctx.has_previous else None
conc = commercial.concentration(ctx.lines, "cliente")
ui.kpi_row([
    dict(label="Ventas netas", value=fmt.cop_short(cur["ventas_netas"]),
         delta=growth_pct(cur["ventas_netas"], prev["ventas_netas"]) if prev else None),
    dict(label="Ticket promedio", value=fmt.cop(cur["ticket_promedio"]),
         delta=growth_pct(cur["ticket_promedio"], prev["ticket_promedio"]) if prev else None),
    dict(label="Unidades netas", value=fmt.num(cur["unidades"]),
         delta=growth_pct(cur["unidades"], prev["unidades"]) if prev else None),
    dict(label="Clientes compradores", value=fmt.num(cur["clientes_activos"]),
         delta=growth_pct(cur["clientes_activos"], prev["clientes_activos"]) if prev else None),
    dict(label="Top 10 clientes", value=fmt.pct(conc["top10"]), show_delta=False,
         foot=f"Concentración HHI: {commercial.hhi_label(conc['hhi'])} ({fmt.num(conc['hhi'])})"),
])

tab_trend, tab_dim, tab_prod, tab_cli = st.tabs(["Evolución", "Por dimensión", "Productos", "Clientes y concentración"])

money_cols = ["ventas_netas", "utilidad_bruta", "ticket_promedio", "ventas_periodo_anterior"]
rename = {"ventas_netas": "Ventas netas", "utilidad_bruta": "Utilidad bruta", "margen_bruto": "Margen bruto",
          "unidades": "Unidades", "transacciones": "Facturas", "ticket_promedio": "Ticket promedio",
          "participacion": "Participación", "producto": "Producto", "categoria": "Categoría", "region": "Región",
          "vendedor": "Vendedor", "cliente": "Cliente", "canal": "Canal", "tipo_cliente": "Tipo de cliente",
          "crecimiento": "Crecimiento", "ventas_periodo_anterior": "Ventas periodo anterior",
          "motivo_bajo_rendimiento": "Motivo", "bajo_rendimiento": "Bajo rendimiento", "mes": "Mes",
          "clientes": "Clientes"}

with tab_trend:
    monthly = commercial.monthly(ctx.lines)
    charts.show(charts.sales_trend(monthly, "Evolución mensual de ventas netas"))
    dim = st.segmented_control("Desagregar evolución por", ["categoria", "region", "canal", "tipo_cliente"],
                               format_func=lambda k: commercial.DIMENSIONS[k], default="categoria", key="trend_dim")
    if dim:
        charts.show(charts.stacked(commercial.monthly_by(ctx.lines, dim), "mes", "ventas_netas", dim,
                                   f"Ventas netas mensuales por {commercial.DIMENSIONS[dim].lower()}"))
    ui.table(monthly, money=["ventas_netas", "utilidad_bruta", "ticket_promedio"],
             percent=["margen_bruto", "crecimiento"], integers=["transacciones", "clientes"], rename=rename)

with tab_dim:
    dim = st.segmented_control("Ver ventas por", ["categoria", "region", "vendedor", "canal", "tipo_cliente"],
                               format_func=lambda k: commercial.DIMENSIONS[k], default="categoria", key="dim_sel")
    dim = dim or "categoria"
    table = commercial.by_dimension(ctx.lines, dim)
    c1, c2 = st.columns([3, 2])
    with c1:
        charts.show(charts.hbar(table.head(15), "ventas_netas", dim, f"Ventas netas por "
                                f"{commercial.DIMENSIONS[dim].lower()}", text_pct="participacion",
                                height=max(320, 28 * min(len(table), 15) + 80)))
    with c2:
        charts.show(charts.hbar(table.head(15).dropna(subset=["margen_bruto"]), "margen_bruto", dim,
                                "Margen bruto %", money=False, color=ui.PALETTE["gold"],
                                height=max(320, 28 * min(len(table), 15) + 80)))
    ui.table(table, money=["ventas_netas", "utilidad_bruta", "ticket_promedio"],
             percent=["margen_bruto", "participacion"], integers=["unidades", "transacciones"], rename=rename)

with tab_prod:
    perf = commercial.product_performance(ctx.lines, ctx.prev_lines if ctx.has_previous else None)
    if perf.empty:
        ui.empty_state("No hay ventas de productos para los filtros seleccionados.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            charts.show(charts.hbar(perf.head(10), "ventas_netas", "producto", "Top 10 productos más vendidos",
                                    height=380))
        with c2:
            top_units = perf.sort_values("unidades", ascending=False).head(10)
            charts.show(charts.hbar(top_units, "unidades", "producto", "Top 10 por unidades", money=False,
                                    color=ui.PALETTE["navy"], height=380))
        ui.section("Productos con bajo rendimiento",
                   "Criterio: quintil inferior de ventas netas del periodo, o caída superior al 30 % frente al "
                   "periodo anterior de igual duración.")
        low = perf[perf["bajo_rendimiento"]]
        ui.table(low[["producto", "categoria", "ventas_netas", "ventas_periodo_anterior", "crecimiento",
                      "margen_bruto", "unidades", "motivo_bajo_rendimiento"]],
                 money=money_cols, percent=["crecimiento", "margen_bruto"], integers=["unidades"], rename=rename)
        with st.expander("Ver todos los productos"):
            search = st.text_input("Buscar producto", key="prod_search", placeholder="Ej. arroz")
            view = perf[perf["producto"].str.contains(search, case=False, regex=False)] if search else perf
            ui.table(view.drop(columns=["bajo_rendimiento"]), money=money_cols,
                     percent=["margen_bruto", "participacion", "crecimiento"], integers=["unidades", "transacciones"],
                     rename=rename)

with tab_cli:
    c1, c2 = st.columns([3, 2])
    with c1:
        if conc["n"]:
            charts.show(charts.pareto(conc["pareto"], "cliente"))
    with c2:
        ui.section("Indicadores de concentración")
        ui.table(
            pd.DataFrame([
                {"Indicador": "Clientes con compras", "Valor": fmt.num(conc["n"])},
                {"Indicador": "Participación cliente principal", "Valor": fmt.pct(conc["top1"])},
                {"Indicador": "Participación top 5", "Valor": fmt.pct(conc["top5"])},
                {"Indicador": "Participación top 10", "Valor": fmt.pct(conc["top10"])},
                {"Indicador": "Participación 20 % de clientes", "Valor": fmt.pct(conc["top20pct"])},
                {"Indicador": "Clientes que suman el 80 %", "Valor": fmt.num(conc["n_80pct"])},
                {"Indicador": "Índice HHI (0-10.000)",
                 "Valor": f"{fmt.num(conc['hhi'])} · {commercial.hhi_label(conc['hhi'])}"},
            ]))
    ui.section("Clientes principales")
    top = commercial.by_dimension(ctx.lines, "cliente").head(20)
    ui.table(top, money=["ventas_netas", "utilidad_bruta", "ticket_promedio"],
             percent=["margen_bruto", "participacion"], integers=["unidades", "transacciones"], rename=rename)
