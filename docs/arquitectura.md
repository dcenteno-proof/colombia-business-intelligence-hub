# Arquitectura

## Principios

- **Ligera**: Python + Streamlit + SQLite en un solo proceso. Sin Docker, sin servidores de base de datos.
  Memoria medida con la base DEMO completa (~28.000 líneas de venta) tras recorrer todas las páginas:
  pico de ~260 MB de RAM en uso (working set) para el proceso de Streamlit.
- **Separación de capas**: la interfaz no ejecuta SQL ni calcula fórmulas; sólo presenta.
- **Lógica pura y testeable**: la capa analítica recibe y devuelve `DataFrame`; no conoce Streamlit.
- **Preparada para crecer**: cambiar `CBH_DATABASE_URL` permite apuntar SQLAlchemy a otro motor
  (PostgreSQL, SQL Server) sin tocar la capa analítica; las consultas de `sql/queries` usan SQL estándar
  (salvo los `PRAGMA` del Centro de datos, exclusivos de SQLite).

## Capas

```
┌──────────────────────────────────────────────────────────────────────────┐
│ app/  (Presentación – Streamlit)                                         │
│   dashboard.py        router (st.navigation), filtros globales, arranque │
│   pages/*.py          una página por módulo                              │
│   components/         tema, tarjetas KPI, tablas, gráficos, formato COP  │
├──────────────────────────────────────────────────────────────────────────┤
│ src/reports/          Reportes Excel/CSV en memoria                      │
│ src/analytics/        Lógica de negocio (funciones puras sobre pandas)   │
│   metrics.py          fórmulas base y KPIs                               │
│   filters.py          periodo, región, categoría, producto               │
│   commercial.py · financial.py · operational.py · customers.py (RFM)     │
│   alerts.py           motor de reglas                                    │
│   dataset.py          carga única del conjunto analítico                 │
├──────────────────────────────────────────────────────────────────────────┤
│ src/data/             ETL, generador DEMO, archivos de ejemplo, calidad  │
├──────────────────────────────────────────────────────────────────────────┤
│ src/database/         Acceso a datos                                     │
│   models.py           modelo relacional (SQLAlchemy ORM)                 │
│   connection.py       motor, sesiones transaccionales, PRAGMA FK         │
│   repository.py       ejecuta sql/queries/*.sql con parámetros enlazados │
├──────────────────────────────────────────────────────────────────────────┤
│ sql/                  schema.sql (DDL generado) y queries/*.sql          │
│ data/                 processed/cbh_demo.db · raw/ · sample/             │
└──────────────────────────────────────────────────────────────────────────┘
```

## Flujo de datos

1. **Arranque**: `app/dashboard.py` crea las tablas si no existen y, si la base está vacía, genera los datos DEMO.
2. **Lectura**: `dataset.load_dataset` ejecuta 8 consultas parametrizadas y enriquece las líneas de venta con
   montos derivados (enteros COP). El resultado se guarda en caché de Streamlit (`st.cache_data`) y se invalida
   cuando cambia el archivo de base de datos o tras una importación.
3. **Filtrado**: el `Filters` del panel lateral se aplica en memoria (pandas). El periodo anterior se deriva
   automáticamente para las comparaciones.
4. **Cálculo**: cada página llama funciones de `src/analytics`.
5. **Escritura**: sólo el ETL y la regeneración DEMO escriben, siempre dentro de una transacción.

## Seguridad y calidad

| Aspecto | Medida |
|---|---|
| Inyección SQL | Parámetros enlazados (`:param`) en todas las consultas; nombres de tabla validados contra lista blanca. |
| Credenciales | Ninguna en el código. Configuración por variables de entorno (`.env`, excluido de Git). |
| Integridad | Llaves foráneas activas, restricciones CHECK y UNIQUE, transacciones con rollback. |
| Archivos subidos | Extensión permitida (CSV/XLSX), tamaño máximo configurable, lectura como texto, validación completa antes de cargar. |
| HTML en la interfaz | Textos dinámicos escapados (`html.escape`) antes de insertarse en tarjetas. |
| Errores | Mensajes claros en la interfaz; una regla de alerta fallida no bloquea las demás. |
| Pruebas | 60 pruebas automatizadas (Pytest) sobre bases temporales aisladas. |

## Decisiones técnicas

- **Python 3.11/3.12**: el código es compatible con ambas versiones (en el equipo de desarrollo sólo estaba
  disponible 3.11.9).
- **`st.navigation`** en lugar del descubrimiento automático de páginas: permite agrupar el menú por secciones e
  iconos. La carpeta `app/pages/` se conserva según la estructura solicitada.
- **Fotos de inventario mensuales** en vez de recalcular el kardex en cada consulta: rotación eficiente.
