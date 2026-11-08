"""Inteligencia de clientes: actividad, ranking y segmentación RFM."""
import streamlit as st

from app.components import charts, formatting as fmt, ui
from app.components.context import get_context
from src.analytics import commercial, customers as cu
from src.analytics.filters import apply_dimensions
from src.config import ACTIVE_CUSTOMER_DAYS

ctx = get_context()
ui.page_header("Inteligencia de clientes", "Segmentación RFM, actividad, frecuencia y valor", period=ctx.f.label())

ref = cu.reference_for_period(ctx.end)
metrics = cu.customer_metrics(ctx.lines, ref)
customers_master = ctx.ds.customers
if ctx.f.regions:
    customers_master = customers_master[customers_master["region"].isin(ctx.f.regions)]
status = cu.activity_status(apply_dimensions(ctx.ds.lines, ctx.f), customers_master, ref, ACTIVE_CUSTOMER_DAYS)
counts = status["estado"].value_counts()
conc = commercial.concentration(ctx.lines, "cliente")

ui.kpi_row([
    dict(label="Clientes activos", value=fmt.num(counts.get("Activo", 0)), show_delta=False,
         foot=f"Compraron en los últimos {ACTIVE_CUSTOMER_DAYS} días"),
    dict(label="Clientes inactivos", value=fmt.num(counts.get("Inactivo", 0)), show_delta=False,
         foot=f"Sin compras hace más de {ACTIVE_CUSTOMER_DAYS} días; sin compras nunca: {counts.get('Sin compras', 0)}"),
    dict(label="Frecuencia promedio", value=fmt.num(metrics["frecuencia"].mean() if not metrics.empty else None, 1),
         show_delta=False, foot="Facturas por cliente en el periodo"),
    dict(label="Valor promedio por cliente", value=fmt.cop_short(metrics["valor"].mean() if not metrics.empty else None),
         show_delta=False, foot="Ventas netas / clientes compradores"),
    dict(label="Días entre compras", value=fmt.num(metrics["dias_entre_compras"].median() if not metrics.empty
                                                   else None, 0), show_delta=False, foot="Mediana"),
])

tab_rfm, tab_rank, tab_act, tab_method = st.tabs(["Segmentación RFM", "Ranking", "Actividad", "Metodología RFM"])
rename = {"cliente": "Cliente", "tipo_cliente": "Tipo", "region": "Región", "ultima_compra": "Última compra",
          "recencia_dias": "Recencia (días)", "frecuencia": "Facturas", "valor": "Ventas netas",
          "ticket_promedio": "Ticket promedio", "segmento": "Segmento", "accion_sugerida": "Acción sugerida",
          "dias_entre_compras": "Días entre compras", "clientes": "Clientes", "participacion_valor": "% del valor",
          "recencia_promedio": "Recencia promedio", "frecuencia_promedio": "Frecuencia promedio",
          "primera_compra": "Primera compra"}

with tab_rfm:
    try:
        rfm = cu.rfm(ctx.lines, ref)
    except cu.InsufficientDataError as exc:
        ui.empty_state(str(exc))
        rfm = None
    if rfm is not None:
        seg = cu.segment_summary(rfm)
        c1, c2 = st.columns([2, 3])
        with c1:
            charts.show(charts.treemap(rfm, ["segmento"], "valor", "Valor (ventas netas) por segmento"))
        with c2:
            charts.show(charts.scatter(rfm, "recencia_dias", "valor", "segmento", "cliente",
                                       "Recencia vs valor por cliente", size="frecuencia",
                                       labels={"recencia_dias": "Recencia (días)", "valor": "Ventas netas (escala log)",
                                               "segmento": "Segmento", "frecuencia": "Facturas"}))
        ui.table(seg, money=["valor"], percent=["participacion_valor"],
                 decimals=["recencia_promedio", "frecuencia_promedio"], integers=["clientes"],
                 rename=rename | {"segmento": "Segmento"})
        sel = st.multiselect("Filtrar clientes por segmento", list(cu.SEGMENT_ACTIONS), key="rfm_seg",
                             placeholder="Todos los segmentos")
        view = rfm[rfm["segmento"].isin(sel)] if sel else rfm
        ui.table(view[["cliente", "tipo_cliente", "region", "recencia_dias", "frecuencia", "valor", "R", "F", "M",
                       "RFM", "segmento", "accion_sugerida"]], money=["valor"],
                 integers=["recencia_dias", "frecuencia"], rename=rename)

with tab_rank:
    search = st.text_input("Buscar cliente", key="cli_search", placeholder="Nombre o código")
    view = metrics[metrics["cliente"].str.contains(search, case=False, regex=False)] if search else metrics
    view = view.reset_index(drop=True)
    view.insert(0, "posicion", view.index + 1)
    ui.table(view.drop(columns=["cliente_id"]), money=["valor", "ticket_promedio"],
             integers=["posicion", "recencia_dias", "frecuencia"], decimals=["dias_entre_compras"],
             dates=["primera_compra", "ultima_compra"], rename=rename | {"posicion": "#"})

with tab_act:
    st.caption(f"Estado a la fecha de referencia {ref:%Y-%m-%d} usando todo el historial: Activo = compra en los "
               f"últimos {ACTIVE_CUSTOMER_DAYS} días; Inactivo = última compra anterior; Sin compras = registrado "
               "sin facturas.")
    by_state = status.groupby(["estado", "tipo_cliente"]).size().reset_index(name="clientes")
    charts.show(charts.stacked(by_state.rename(columns={"clientes": "valor"}), "tipo_cliente", "valor", "estado",
                               "Clientes por tipo y estado").update_yaxes(tickprefix="", tickformat=",d")
                .update_traces(hovertemplate="%{x}<br>%{y} clientes<extra></extra>"))
    inactive = status[status["estado"] != "Activo"].sort_values("dias_sin_compra", ascending=False)
    ui.table(inactive[["codigo", "cliente", "tipo_cliente", "region", "ultima_compra", "dias_sin_compra", "estado"]],
             integers=["dias_sin_compra"], dates=["ultima_compra"],
             rename=rename | {"codigo": "Código", "dias_sin_compra": "Días sin compra", "estado": "Estado"})

with tab_method:
    st.markdown(f"""
**Segmentación RFM básica por quintiles** (periodo seleccionado, referencia {ref:%Y-%m-%d}).

| Dimensión | Definición | Puntaje |
|---|---|---|
| R · Recencia | Días desde la última compra hasta la fecha de referencia | 5 = más reciente |
| F · Frecuencia | Número de facturas en el periodo | 5 = más frecuente |
| M · Valor | Ventas netas en el periodo (COP) | 5 = mayor valor |

Los puntajes se asignan por quintiles sobre el *ranking* (evita fallas con empates). FM = (F + M) / 2.
Reglas evaluadas en orden:

1. **Campeones**: R ≥ 4 y FM ≥ 4
2. **Leales**: R ≥ 3 y FM ≥ 3,5
3. **Nuevos**: R ≥ 4 y F ≤ 2
4. **Potenciales leales**: R ≥ 3
5. **En riesgo**: R ≤ 2 y FM ≥ 3,5
6. **Hibernando**: R = 2
7. **Perdidos**: resto

Requiere al menos {cu.MIN_CUSTOMERS_RFM} clientes con compras. Limitación: los quintiles son relativos a la
cartera del periodo; no son comparables entre periodos con carteras muy diferentes.
""")
