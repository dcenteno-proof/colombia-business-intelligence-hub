# CLAUDE.md — guía para asistentes de código

Colombia Business Intelligence Hub: app Streamlit + SQLite para BI de pymes colombianas. Datos 100 % sintéticos (DEMO).

## Comandos (Windows, desde la raíz)

- Ejecutar app: `.venv\Scripts\python -m streamlit run app\dashboard.py`
- Pruebas: `.venv\Scripts\python -m pytest`
- Reconstruir base DEMO: `.venv\Scripts\python scripts\setup_demo.py --reset`
- Regenerar DDL y diccionario tras cambiar modelos: `.venv\Scripts\python scripts\generate_schema_docs.py`

## Reglas del proyecto

- **Capas**: `app/` sólo presenta; no escribe SQL ni fórmulas. Lógica en `src/analytics` (funciones puras
  sobre DataFrames). Acceso a datos sólo vía `src/database/repository.py` y `sql/queries/*.sql`.
- **Dinero**: enteros COP (BIGINT). Nunca floats para montos almacenados. Ratios sólo al final.
- **Datos faltantes**: los indicadores devuelven `None` (se muestra "N/D"), nunca 0/NaN/inf. Usar
  `metrics.safe_divide`, `growth_pct`, etc.
- **Alertas**: toda regla nueva debe verificar datos suficientes y registrar su evaluación; incluir motivo,
  indicador, valor observado, umbral y recomendación; umbral configurable en `AlertThresholds` + `.env.example`.
- **SQL**: siempre parámetros enlazados (`:param`). No poner `:palabra` en comentarios `--` de los .sql
  (se eliminan al cargar, pero mantener la convención). Nombres de tabla dinámicos sólo vía lista blanca `ALL_TABLES`.
- **DEMO**: cualquier dato ficticio nuevo lleva prefijo/etiqueta DEMO. No usar nombres de empresas reales.
- **Pruebas**: usar las fixtures de `tests/conftest.py` (bases temporales). No escribir en `data/processed` desde
  tests (`run_etl(..., keep_copy=False, errors_dir=tmp_path)`).
- **Streamlit 1.67**: usar `width="stretch"` (no `use_container_width`). Los módulos importados no siempre se
  recargan en caliente: reiniciar el servidor tras cambios en `src/` o `app/components/`.
- Textos de interfaz y documentación en español; formato colombiano (miles con punto, decimales con coma)
  mediante `app/components/formatting.py`.
