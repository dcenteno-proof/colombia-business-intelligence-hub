"""Dashboard ejecutivo: KPIs del periodo, tendencias y comparación entre periodos."""
import streamlit as st

from app.components import charts, formatting as fmt, ui
from app.components.context import get_context
from src.analytics import commercial
from src.analytics.alerts import evaluate_alerts
from src.analytics.metrics import change_pp, growth_pct, summarize

ctx = get_context()
ui.page_header("Dashboard ejecutivo", "Visión consolidada del desempeño comercial y financiero",
               period=ctx.f.label())

cur = summarize(ctx.lines, ctx.opex)
prev = summarize(ctx.prev_lines, ctx.prev_opex) if ctx.has_previous else None


def d(key: str):
    return growth_pct(cur[key], prev[key]) if prev and cur[key] is not None and prev[key] is not None else None


def dpp(key: str):
    return change_pp(cur[key], prev[key]) if prev else None


if ctx.f.dimension_filtered:
    st.info("Hay filtros de región, categoría o producto activos: los gastos operativos no se asignan a esas "
            "dimensiones, por lo que la utilidad y el margen operacional se muestran como N/D.",
            icon=":material/filter_alt:")
if not ctx.has_previous:
    st.caption("No hay un periodo anterior completo de igual duración dentro del histórico: "
               "las variaciones se muestran como 'sin base comparable'.")

growth = d("ventas_netas")
ui.kpi_row([
    dict(label="Ingresos totales (brutos)", value=fmt.cop_short(cur["ventas_brutas"]), delta=d("ventas_brutas"),
         help_text="Suma de cantidad × precio unitario antes de descuentos y devoluciones."),
    dict(label="Ventas netas", value=fmt.cop_short(cur["ventas_netas"]), delta=growth,
         help_text="Ventas brutas - descuentos - devoluciones."),
    dict(label="Costo de ventas", value=fmt.cop_short(cur["costo_ventas"]), delta=d("costo_ventas"), inverse=True,
         help_text="Unidades netas vendidas × costo unitario vigente a la fecha de venta."),
    dict(label="Utilidad bruta", value=fmt.cop_short(cur["utilidad_bruta"]), delta=d("utilidad_bruta")),
    dict(label="Margen bruto", value=fmt.pct(cur["margen_bruto"]), delta=dpp("margen_bruto"), delta_kind="pp"),
])
st.write("")
ui.kpi_row([
    dict(label="Gastos operativos", value=fmt.cop_short(cur["gastos_operativos"]), delta=d("gastos_operativos"),
         inverse=True, show_delta=cur["gastos_operativos"] is not None),
    dict(label="Utilidad operacional", value=fmt.cop_short(cur["utilidad_operacional"]),
         delta=d("utilidad_operacional"), show_delta=cur["utilidad_operacional"] is not None,
         foot=f"Margen operacional {fmt.pct(cur['margen_operacional'])}"),
    dict(label="Crecimiento de ventas", value=fmt.pct(growth, signed=True), show_delta=False,
         foot=f"Ventas netas vs {ctx.prev_f.label() if ctx.prev_f else 'N/D'}"),
    dict(label="Transacciones", value=fmt.num(cur["transacciones"]), delta=d("transacciones"),
         foot=f"{fmt.num(cur['clientes_activos'])} clientes compradores"),
    dict(label="Ticket promedio", value=fmt.cop(cur["ticket_promedio"]), delta=d("ticket_promedio")),
])

monthly = commercial.monthly(ctx.lines)
prev_monthly = commercial.monthly(ctx.prev_lines) if ctx.has_previous else monthly.iloc[0:0]

left, right = st.columns([3, 2])
with left:
    charts.show(charts.sales_trend(monthly))
with right:
    charts.show(charts.period_comparison(monthly, prev_monthly))

c1, c2, c3 = st.columns(3)
with c1:
    charts.show(charts.donut(commercial.by_dimension(ctx.lines, "categoria"), "categoria", "ventas_netas",
                             "Ventas netas por categoría"))
with c2:
    charts.show(charts.hbar(commercial.by_dimension(ctx.lines, "region"), "ventas_netas", "region",
                            "Ventas netas por región", height=340))
with c3:
    charts.show(charts.hbar(commercial.by_dimension(ctx.lines, "canal"), "ventas_netas", "canal",
                            "Ventas netas por canal", color=ui.PALETTE["navy"], height=340))

ui.section("Alertas del último mes completo")
alerts, _, month = evaluate_alerts(ctx.ds.lines, ctx.ds.expenses, ctx.ds.snapshots, ctx.ds.costs,
                                   end_month=ctx.f.end_month)
if alerts.empty:
    st.success(f"Sin alertas para {month}.", icon=":material/task_alt:")
else:
    a, b, c = st.columns([1, 1, 2])
    a.metric("Alertas altas", int((alerts["severidad"] == "Alta").sum()))
    b.metric("Alertas medias", int((alerts["severidad"] == "Media").sum()))
    with c:
        for _, row in alerts.head(3).iterrows():
            st.markdown(f"**{row['severidad']}** · {row['titulo']}")
        st.page_link("pages/alertas.py", label="Ver centro de alertas", icon=":material/arrow_forward:")
