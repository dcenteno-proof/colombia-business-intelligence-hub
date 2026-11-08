"""Documentación de metodología visible dentro de la app."""
import streamlit as st

from app.components import ui
from src.config import DOCS_DIR

ui.page_header("Metodología y documentación", "Fórmulas, reglas de negocio, modelo de datos y proceso ETL")

DOCS = {
    "Metodología de indicadores": "metodologia_indicadores.md",
    "Reglas del centro de alertas": "reglas_alertas.md",
    "Proceso ETL": "proceso_etl.md",
    "Modelo entidad-relación": "modelo_entidad_relacion.md",
    "Diccionario de datos": "diccionario_datos.md",
    "Arquitectura": "arquitectura.md",
    "Requisitos funcionales": "requisitos_funcionales.md",
}
choice = st.segmented_control("Documento", list(DOCS), default="Metodología de indicadores", key="doc_pick")
path = DOCS_DIR / DOCS[choice or "Metodología de indicadores"]
if path.exists():
    content = path.read_text(encoding="utf-8")
    if "```mermaid" in content:
        st.caption("El diagrama Mermaid se visualiza en GitHub o VS Code; aquí se muestra su código fuente.")
    st.markdown(content)
else:
    st.warning(f"No se encontró el documento {path.name}.")
