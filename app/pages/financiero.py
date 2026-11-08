"""Inteligencia financiera."""
import pandas as pd
import streamlit as st

from app.components import charts, formatting as fmt, ui
from app.components.context import get_context
from src.analytics import financial

ctx = get_context()
ui.page_header("Inteligencia financiera", "Estado de resultados de gestión, márgenes y rentabilidad",
               period=ctx.f.label())
st.caption("Cifras de gestión calculadas a partir de transacciones operativas (facturas, costo por línea y gastos "
           "registrados). No reemplazan los estados financieros contables: no incluyen depreciaciones, "
           "provisiones, impuestos ni gastos financieros.")
if ctx.f.dimension_filtered:
    st.info("Con filtros de región, categoría o producto los gastos operativos no son atribuibles: se muestra "
            "el estado de resultados hasta la utilidad bruta.", icon=":material/filter_alt:")

pnl = financial.income_statement(ctx.lines, ctx.opex, ctx.prev_lines if ctx.has_previous else None, ctx.prev_opex)
val = dict(zip(pnl["clave"], pnl["valor"]))

tab_pnl, tab_month, tab_profit, tab_ind = st.tabs(["Estado de resultados", "Variaciones mensuales",
                                                   "Rentabilidad", "Indicadores"])
with tab_pnl:
    c1, c2 = st.columns([2, 3])
    with c1:
        ui.table(pnl.drop(columns="clave"), money=["valor", "periodo_anterior", "variacion"],
                 percent=["pct_ventas_netas", "variacion_pct"],
                 rename={"concepto": "Concepto", "valor": "Periodo actual", "pct_ventas_netas": "% ventas netas",
                         "periodo_anterior": "Periodo anterior", "variacion": "Variación",
                         "variacion_pct": "Variación %"})
    with c2:
        items = [("Ventas brutas", val["ventas_brutas"], "absolute"), ("Descuentos", -val["descuentos"], "relative"),
                 ("Devoluciones", -val["devoluciones"], "relative"), ("Ventas netas", 0, "total"),
                 ("Costo de ventas", -val["costo_ventas"], "relative"), ("Utilidad bruta", 0, "total")]
        if val["gastos_operativos"] is not None:
            items += [("Gastos operativos", -val["gastos_operativos"], "relative"),
                      ("Utilidad operacional", 0, "total")]
        charts.show(charts.waterfall(items, "De ventas brutas a utilidad"))

monthly = financial.monthly_pnl(ctx.lines, ctx.expenses)
with tab_month:
    if monthly.empty:
        ui.empty_state("No hay datos para el periodo seleccionado.")
    else:
        m = monthly.melt(id_vars="mes", value_vars=[c for c in ["margen_bruto", "margen_operacional",
                                                                "gastos_sobre_ventas"]
                                                    if monthly[c].notna().any()],
                         var_name="indicador", value_name="valor")
        m["indicador"] = m["indicador"].map({"margen_bruto": "Margen bruto", "margen_operacional": "Margen operacional",
                                             "gastos_sobre_ventas": "Gastos / ventas"})
        charts.show(charts.lines(m, "mes", "valor", "indicador", "Márgenes mensuales (%)", money=False, suffix=" %"))
        ui.table(monthly[["mes", "ventas_netas", "costo_ventas", "utilidad_bruta", "margen_bruto", "gastos_operativos",
                          "utilidad_operacional", "margen_operacional", "var_ventas_netas_pct",
                          "var_utilidad_bruta_pct", "var_margen_bruto_pp"]],
                 money=["ventas_netas", "costo_ventas", "utilidad_bruta", "gastos_operativos", "utilidad_operacional"],
                 percent=["margen_bruto", "margen_operacional", "var_ventas_netas_pct", "var_utilidad_bruta_pct"],
                 pp_cols=["var_margen_bruto_pp"],
                 rename={"mes": "Mes", "ventas_netas": "Ventas netas", "costo_ventas": "Costo de ventas",
                         "utilidad_bruta": "Utilidad bruta", "margen_bruto": "Margen bruto",
                         "gastos_operativos": "Gastos operativos", "utilidad_operacional": "Utilidad operacional",
                         "margen_operacional": "Margen operacional", "var_ventas_netas_pct": "Var. ventas (m/m)",
                         "var_utilidad_bruta_pct": "Var. utilidad bruta (m/m)",
                         "var_margen_bruto_pp": "Var. margen bruto (pp)"})
        if ctx.expenses is not None and not ctx.expenses.empty:
            ui.section("Gastos operativos por categoría")
            exp = ctx.expenses.groupby(["mes", "categoria_gasto"]).monto.sum().reset_index()
            charts.show(charts.stacked(exp, "mes", "monto", "categoria_gasto", "Gastos operativos mensuales"))

with tab_profit:
    dim = st.segmented_control("Rentabilidad por", ["categoria", "producto", "region", "tipo_cliente", "vendedor"],
                               format_func=lambda k: {"categoria": "Categoría", "producto": "Producto",
                                                      "region": "Región", "tipo_cliente": "Tipo de cliente",
                                                      "vendedor": "Vendedor"}[k], default="categoria", key="fin_dim")
    dim = dim or "categoria"
    prof = financial.profitability_by(ctx.lines, dim)
    c1, c2 = st.columns(2)
    with c1:
        charts.show(charts.hbar(prof.head(15), "utilidad_bruta", dim, "Utilidad bruta", height=400))
    with c2:
        charts.show(charts.hbar(prof.head(15).dropna(subset=["margen_bruto"]), "margen_bruto", dim, "Margen bruto %",
                                money=False, color=ui.PALETTE["gold"], height=400))
    ui.table(prof, money=["ventas_netas", "costo_ventas", "utilidad_bruta"],
             percent=["margen_bruto", "participacion_utilidad"],
             rename={dim: dim.capitalize(), "ventas_netas": "Ventas netas", "costo_ventas": "Costo de ventas",
                     "utilidad_bruta": "Utilidad bruta", "margen_bruto": "Margen bruto",
                     "participacion_utilidad": "Participación en utilidad"})

with tab_ind:
    ind = pd.DataFrame(financial.financial_indicators(ctx.lines, ctx.opex))
    ind["valor_fmt"] = [fmt.cop(v) if u == "COP" else fmt.pct(v) for v, u in zip(ind["valor"], ind["unidad"])]
    cols = st.columns(4)
    for i, r in ind.iterrows():
        with cols[i % 4]:
            ui.kpi_card(r["indicador"], r["valor_fmt"], show_delta=False, foot=r["formula"])
            st.write("")
    st.caption("N/D = no calculable con la información disponible (por ejemplo, gastos no atribuibles al filtro "
               "o denominador en cero). Ver la página Metodología para fórmulas y limitaciones.")
