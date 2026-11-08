"""Generación y descarga de reportes en Excel y CSV."""
import streamlit as st

from app.components import ui
from app.components.context import get_context
from src.reports import exporter

ctx = get_context()
ui.page_header("Reportes", "Descarga de reportes con los filtros activos", period=ctx.f.label())
st.caption("Cada Excel incluye una hoja 'Notas' con el periodo, los filtros aplicados y la identificación de los "
           "datos como DEMO. El CSV usa separador ';' y decimales con coma (compatible con Excel en español).")

REPORTS = [
    ("comercial", "Reporte comercial", ":material/storefront:", exporter.commercial_report,
     "Resumen mensual, ventas por categoría, región, vendedor y producto, top clientes y concentración."),
    ("financiero", "Reporte financiero", ":material/account_balance:", exporter.financial_report,
     "Estado de resultados de gestión, P&G mensual, rentabilidad por categoría y producto, indicadores."),
    ("inventario", "Reporte de inventario", ":material/inventory_2:", exporter.inventory_report,
     "Existencias, rotación por producto y categoría, bajo mínimo, sin movimiento y proveedores."),
    ("clientes", "Reporte de clientes", ":material/groups:", exporter.customers_report,
     "Segmentos RFM, puntajes por cliente y estado de actividad."),
    ("alertas", "Reporte de alertas", ":material/notifications_active:", exporter.alerts_report,
     "Alertas generadas y resultado de cada regla evaluada."),
]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
suffix = (ctx.f.label().replace(" a ", "_").replace(" ", "_")).lower()

cols = st.columns(2)
for i, (key, title, icon, builder, desc) in enumerate(REPORTS):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(desc)
            try:
                xlsx, main = builder(ctx.ds, ctx.f)
            except Exception as exc:
                st.error(f"No fue posible generar el reporte: {exc}")
                continue
            b1, b2 = st.columns(2)
            b1.download_button("Excel", xlsx, file_name=f"reporte_{key}_{suffix}.xlsx", mime=XLSX, icon=icon,
                               key=f"x_{key}", width="stretch")
            b2.download_button("CSV (tabla principal)", exporter.to_csv(main), file_name=f"reporte_{key}_{suffix}.csv",
                               mime="text/csv", icon=":material/table:", key=f"c_{key}", width="stretch")
            st.caption(f"Tabla principal: {len(main)} filas")
