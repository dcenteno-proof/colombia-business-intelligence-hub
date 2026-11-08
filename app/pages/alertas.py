"""Centro de alertas: reglas de negocio con motivo, indicador, valor observado y recomendación."""
from dataclasses import asdict

import pandas as pd
import streamlit as st

from app.components import ui
from app.components.context import get_context
from src.analytics.alerts import evaluate_alerts
from src.config import AlertThresholds
from src.reports.exporter import to_csv, to_excel

ctx = get_context()
alerts, evaluations, month = evaluate_alerts(ctx.ds.lines, ctx.ds.expenses, ctx.ds.snapshots, ctx.ds.costs,
                                             end_month=ctx.f.end_month)
ui.page_header("Centro de alertas", "Reglas de negocio evaluadas sobre el último mes completo (nivel compañía)",
               period=f"Mes evaluado: {month or 'N/D'}")

n = len(alerts)
ui.kpi_row([
    dict(label="Alertas totales", value=str(n), show_delta=False),
    dict(label="Severidad alta", value=str(int((alerts["severidad"] == "Alta").sum())) if n else "0", show_delta=False),
    dict(label="Severidad media", value=str(int((alerts["severidad"] == "Media").sum())) if n else "0",
         show_delta=False),
    dict(label="Reglas sin datos suficientes", value=str(int((evaluations["estado"] == "Sin datos suficientes").sum())),
         show_delta=False, foot="No generan alerta"),
])
st.caption("Las alertas ignoran los filtros de región/categoría/producto y usan el mes de cierre del periodo "
           "seleccionado. Si el último mes está incompleto, se evalúa el mes anterior.")

tab_list, tab_rules, tab_cfg = st.tabs(["Alertas", "Reglas evaluadas", "Umbrales"])
with tab_list:
    if alerts.empty:
        st.success("No se generaron alertas para el mes evaluado.", icon=":material/task_alt:")
    else:
        c1, c2 = st.columns(2)
        mods = c1.multiselect("Módulo", sorted(alerts["modulo"].unique()), placeholder="Todos", key="al_mod")
        sevs = c2.multiselect("Severidad", ["Alta", "Media", "Baja"], placeholder="Todas", key="al_sev")
        view = alerts
        if mods:
            view = view[view["modulo"].isin(mods)]
        if sevs:
            view = view[view["severidad"].isin(sevs)]
        for _, a in view.iterrows():
            ui.alert_card(a.to_dict())
        d1, d2, _ = st.columns([1, 1, 3])
        d1.download_button("Descargar Excel", to_excel({"Alertas": alerts, "Reglas evaluadas": evaluations},
                                                       "Reporte de alertas", ctx.f, [f"Mes evaluado: {month}"]),
                           file_name=f"alertas_{month}.xlsx", icon=":material/download:",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        d2.download_button("Descargar CSV", to_csv(alerts), file_name=f"alertas_{month}.csv", mime="text/csv",
                           icon=":material/download:")

with tab_rules:
    ui.table(evaluations, rename={"regla": "Regla", "estado": "Estado", "detalle": "Detalle"})

with tab_cfg:
    t = AlertThresholds()
    labels = {
        "sales_drop_pct": ("Caída de ventas vs promedio 3 meses (%)", "CBH_ALERT_SALES_DROP_PCT"),
        "region_sales_drop_pct": ("Caída de ventas regional (%)", "CBH_ALERT_REGION_DROP_PCT"),
        "margin_drop_pp": ("Caída de margen bruto total (pp)", "CBH_ALERT_MARGIN_DROP_PP"),
        "category_margin_drop_pp": ("Caída de margen por categoría (pp)", "CBH_ALERT_CAT_MARGIN_DROP_PP"),
        "top_customer_share_pct": ("Participación máxima de un cliente (%)", "CBH_ALERT_TOP1_SHARE_PCT"),
        "top10_customer_share_pct": ("Participación máxima top 10 (%)", "CBH_ALERT_TOP10_SHARE_PCT"),
        "cost_increase_pct": ("Aumento de costo en 90 días (%)", "CBH_ALERT_COST_INCREASE_PCT"),
        "opex_ratio_pct": ("Gastos / ventas máximo (%)", "CBH_ALERT_OPEX_RATIO_PCT"),
        "opex_increase_pct": ("Crecimiento de gastos vs promedio 3 meses (%)", "CBH_ALERT_OPEX_INCREASE_PCT"),
        "min_months_history": ("Meses previos mínimos para comparar", "CBH_ALERT_MIN_MONTHS"),
        "min_customers_concentration": ("Clientes mínimos para concentración", "CBH_ALERT_MIN_CUSTOMERS"),
    }
    rows = [{"Parámetro": labels[k][0], "Valor": v, "Variable .env": labels[k][1]} for k, v in asdict(t).items()]
    ui.table(pd.DataFrame(rows))
    st.caption("Los umbrales se ajustan en el archivo .env (ver .env.example) y aplican al reiniciar la app.")
