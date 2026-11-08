"""Centro de datos: importación ETL, consulta, estructura y calidad."""
import json
from pathlib import Path

import streamlit as st

from app.components import formatting as fmt, state, ui
from src.config import MAX_UPLOAD_MB, SAMPLE_DIR
from src.data.demo_generator import load_demo
from src.data.etl import SPECS, run_etl
from src.data.quality import run_quality_checks
from src.data.sample_files import write_samples
from src.database import repository as repo
from src.database.models import ALL_TABLES
from src.reports.exporter import to_csv

eng = state.engine()
ui.page_header("Centro de datos", "Importación, consulta y calidad de la información")

tab_load, tab_query, tab_schema, tab_quality, tab_admin = st.tabs(
    ["Cargar archivos", "Consultar registros", "Estructura", "Calidad de datos", "Administración"])

STATUS_ICON = {"EXITOSO": ":material/check_circle:", "PARCIAL": ":material/warning:",
               "SIN_CAMBIOS": ":material/info:", "FALLIDO": ":material/error:", "VALIDADO": ":material/fact_check:"}


def show_result(res) -> None:
    s = res.summary()
    msg = {"EXITOSO": st.success, "PARCIAL": st.warning, "SIN_CAMBIOS": st.info, "FALLIDO": st.error,
           "VALIDADO": st.info}[res.estado]
    msg(f"Estado: **{res.estado}** · {s['archivo']} ({s['entidad']})", icon=STATUS_ICON[res.estado])
    ui.kpi_row([
        dict(label="Filas leídas", value=fmt.num(s["filas_leidas"]), show_delta=False),
        dict(label="Válidas", value=fmt.num(s["filas_validas"]), show_delta=False),
        dict(label="Cargadas", value=fmt.num(s["filas_cargadas"]), show_delta=False),
        dict(label="Rechazadas", value=fmt.num(s["filas_rechazadas"]), show_delta=False),
        dict(label="Duplicados", value=fmt.num(s["duplicados_archivo"] + s["duplicados_base"]), show_delta=False,
             foot=f"Archivo: {s['duplicados_archivo']} · Base: {s['duplicados_base']}"),
    ])
    with st.expander("Resumen del proceso ETL", expanded=True):
        for p in res.pasos:
            st.markdown(f"- {p}")
        if s["nulos"]:
            st.caption("Nulos por columna: " + ", ".join(f"{k}: {v}" for k, v in s["nulos"].items()))
    if res.errores:
        ui.section("Errores de calidad detectados")
        errs = res.errors_frame()
        ui.table(errs, rename={"fila": "Fila", "columna": "Columna", "valor": "Valor", "error": "Error"})
        st.download_button("Descargar errores (CSV)", to_csv(errs), file_name=f"errores_{res.entidad}.csv",
                           mime="text/csv", icon=":material/download:", key=f"err_{res.estado}")


with tab_load:
    c1, c2 = st.columns([1, 2])
    with c1:
        entity = st.selectbox("Tipo de información", list(SPECS), format_func=lambda k: SPECS[k].description,
                              key="etl_entity")
        spec = SPECS[entity]
        st.markdown("**Columnas obligatorias:** " + ", ".join(f"`{c}`" for c in spec.required))
        st.markdown("**Opcionales:** " + (", ".join(f"`{c}`" for c in spec.optional) or "—"))
        st.caption("Se aceptan encabezados con tildes, mayúsculas o espacios (p. ej. 'Código Cliente'). "
                   "Fechas AAAA-MM-DD o DD/MM/AAAA; importes '12.500', '$ 12.500' o '12500'.")
    with c2:
        up = st.file_uploader("Archivo CSV o Excel", type=["csv", "xlsx"], key="etl_file",
                              help=f"Tamaño máximo {MAX_UPLOAD_MB} MB")
        if up is not None:
            data = up.getvalue()
            if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
                st.error(f"El archivo supera el límite de {MAX_UPLOAD_MB} MB.")
            else:
                b1, b2 = st.columns(2)
                if b1.button("1. Validar sin cargar", icon=":material/fact_check:", width="stretch"):
                    st.session_state["etl_result"] = run_etl(data, entity, up.name, engine=eng, dry_run=True)
                if b2.button("2. Validar y cargar", type="primary", icon=":material/upload:", width="stretch"):
                    res = run_etl(data, entity, up.name, engine=eng)
                    st.session_state["etl_result"] = res
                    if res.filas_cargadas:
                        state.invalidate()
                        st.toast(f"{res.filas_cargadas} registros cargados.", icon=":material/check_circle:")
    if st.session_state.get("etl_result") is not None:
        show_result(st.session_state["etl_result"])

    ui.section("Archivos de ejemplo", "Contienen registros válidos y errores intencionales para probar el ETL.")
    if not any(SAMPLE_DIR.glob("*_ejemplo.*")):
        write_samples(SAMPLE_DIR)
    cols = st.columns(4)
    for i, path in enumerate(sorted(SAMPLE_DIR.glob("*_ejemplo.*"))):
        cols[i % 4].download_button(path.name, path.read_bytes(), file_name=path.name, icon=":material/description:",
                                    key=f"sample_{path.name}", width="stretch")

with tab_query:
    c1, c2, c3 = st.columns([2, 1, 2])
    table_name = c1.selectbox("Tabla", ALL_TABLES, index=ALL_TABLES.index("ventas"), key="q_table")
    limit = c2.number_input("Máx. registros", min_value=10, max_value=50_000, value=500, step=100, key="q_limit")
    search = c3.text_input("Buscar texto en cualquier columna", key="q_search")
    df = repo.read_table(table_name, eng, int(limit))
    if search:
        mask = df.astype(str).apply(lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
        df = df[mask]
    cols_sel = st.multiselect("Columnas", list(df.columns), default=list(df.columns), key=f"q_cols_{table_name}")
    st.caption(f"{len(df)} registros mostrados (más recientes primero).")
    st.dataframe(df[cols_sel], hide_index=True, height=420)
    st.download_button("Descargar consulta (CSV)", to_csv(df[cols_sel]), file_name=f"{table_name}.csv",
                       mime="text/csv", icon=":material/download:")

with tab_schema:
    counts = repo.table_counts(eng)
    c1, c2 = st.columns([1, 2])
    with c1:
        ui.table(counts, integers=["registros"], rename={"tabla": "Tabla", "registros": "Registros"})
    with c2:
        t = st.selectbox("Estructura de la tabla", ALL_TABLES, key="schema_table")
        ui.table(repo.table_schema(t, eng), rename={"columna": "Columna", "tipo": "Tipo", "obligatoria": "Obligatoria",
                                                    "llave_primaria": "PK", "valor_defecto": "Valor por defecto",
                                                    "llave_foranea": "FK"})
        st.caption("Diagrama entidad-relación y diccionario de datos: docs/modelo_entidad_relacion.md y "
                   "docs/diccionario_datos.md")

with tab_quality:
    ui.section("Controles sobre la base de datos")
    ui.table(run_quality_checks(eng), rename={"control": "Control", "resultado": "Resultado", "esperado": "Esperado",
                                              "estado": "Estado"})
    ui.section("Historial de importaciones")
    log = repo.import_log(eng)
    if log.empty:
        ui.empty_state("Aún no se han importado archivos.")
    else:
        ui.table(log.drop(columns=["detalle"]),
                 integers=["filas_leidas", "filas_cargadas", "filas_rechazadas", "duplicados"])
        pick = st.selectbox("Ver detalle de la importación", log["id"].tolist(),
                            format_func=lambda i: f"#{i} · {log.set_index('id').at[i, 'archivo']}", key="log_pick")
        detail = json.loads(log.set_index("id").at[pick, "detalle"] or "{}")
        st.json(detail, expanded=False)

with tab_admin:
    st.warning("Regenerar la base DEMO elimina TODOS los datos actuales (incluidos los importados) y crea de nuevo "
               "los datos sintéticos. Esta acción no se puede deshacer.", icon=":material/warning:")
    ok = st.checkbox("Entiendo que se borrarán los datos actuales de la base de datos", key="regen_ok")
    if st.button("Regenerar base DEMO", disabled=not ok, icon=":material/restart_alt:"):
        with st.spinner("Regenerando datos DEMO…"):
            counts = load_demo(eng)
            write_samples(SAMPLE_DIR)
        state.invalidate()
        st.session_state.pop("etl_result", None)
        st.success("Base regenerada: " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    st.caption(f"Archivo de base de datos: {Path(eng.url.database).name} (carpeta data/processed)")
