# Colombia Business Intelligence Hub

Plataforma de inteligencia de negocios para pequeñas y medianas empresas colombianas. Integra información
comercial, financiera, operativa y de clientes en un solo lugar y la convierte en indicadores, alertas y
reportes para tomar decisiones.

> **Todos los datos incluidos son sintéticos (DEMO)** y corresponden a una distribuidora ficticia,
> *Distribuidora Andina DEMO S.A.S.* No representan a ninguna empresa real.

**Vista en línea (sin instalar nada):** https://dcenteno-proof.github.io/colombia-business-intelligence-hub/
— se regenera con `.venv\Scripts\python scripts\build_showcase.py`.

---

## Problema que resuelve

En muchas pymes la información vive en archivos de Excel dispersos, exportes del software contable y
reportes manuales. Responder preguntas básicas — *¿cuánto ganamos realmente este mes?, ¿qué región cayó?,
¿qué productos se van a agotar?, ¿dependemos demasiado de un cliente?* — toma días y depende de una persona.

Colombia BI Hub centraliza esos datos en un modelo relacional, valida su calidad al importarlos y calcula
indicadores con fórmulas documentadas y verificables, incluyendo un centro de alertas basado en reglas de negocio.

## Funcionalidades

| Módulo | Contenido |
|---|---|
| **Dashboard ejecutivo** | 10 KPIs (ingresos, ventas netas, costo, utilidad bruta, margen, gastos, utilidad operacional, crecimiento, transacciones, ticket) con variación vs periodo anterior; tendencias; mezcla por categoría, región y canal; resumen de alertas. |
| **Inteligencia comercial** | Evolución mensual, ventas por producto/categoría/región/vendedor/canal/tipo de cliente, top productos, productos de bajo rendimiento, clientes principales, Pareto y concentración (HHI). |
| **Inteligencia financiera** | Estado de resultados de gestión con cascada, variaciones mensuales, márgenes, rentabilidad por dimensión e indicadores con su fórmula. |
| **Inteligencia operacional** | Rotación y días de inventario, productos bajo mínimo con días de cobertura, productos sin movimiento, desempeño de proveedores, índice de evolución de costos. |
| **Inteligencia de clientes** | Segmentación RFM por quintiles, clientes activos/inactivos, frecuencia, valor y ranking. |
| **Centro de alertas** | 7 reglas (caída de ventas total y por región, margen, inventario bajo, concentración, costos, gastos) con motivo, indicador, valor observado, umbral y recomendación. |
| **Reportes** | Comercial, financiero, inventario, clientes y alertas en Excel (multihoja, con notas) y CSV. |
| **Centro de datos** | Importación ETL de CSV/Excel (validar o cargar), consulta de tablas, estructura, controles de calidad, historial de importaciones, regeneración de la base DEMO. |
| **Metodología** | Documentación de fórmulas, reglas, modelo de datos y ETL dentro de la app. |

Filtros globales en el panel lateral: **periodo (meses), región, categoría y producto**.

## Arquitectura

```
app/            Presentación (Streamlit): router, páginas y componentes visuales
src/analytics/  Lógica de negocio pura (pandas): métricas, comercial, financiero, operacional, RFM, alertas
src/reports/    Generación de Excel/CSV
src/data/       ETL, generador de datos DEMO, archivos de ejemplo, controles de calidad
src/database/   Modelo SQLAlchemy, conexión y repositorio de consultas parametrizadas
sql/            schema.sql (DDL generado) y queries/*.sql
```

La interfaz no ejecuta SQL ni calcula fórmulas: llama a la capa analítica, que recibe y devuelve DataFrames y
está cubierta por pruebas. Detalle en [docs/arquitectura.md](docs/arquitectura.md).

## Tecnologías

Python 3.11 / 3.12 · Streamlit · pandas · Plotly · SQLite · SQLAlchemy 2 · OpenPyXL · python-dotenv · Pytest · Git

## Estructura

```
Colombiabusinesshub/
├── app/
│   ├── dashboard.py            # punto de entrada (navegación, filtros, arranque)
│   ├── pages/                  # ejecutivo, comercial, financiero, operacional, clientes,
│   │                           # alertas, reportes, centro_datos, metodologia
│   └── components/             # ui, charts, formatting, state, context
├── src/
│   ├── config.py               # configuración y umbrales (.env)
│   ├── analytics/              # metrics, filters, commercial, financial, operational,
│   │                           # customers, alerts, dataset
│   ├── data/                   # etl, demo_generator, sample_files, quality
│   ├── database/               # models, connection, repository
│   └── reports/                # exporter
├── sql/                        # schema.sql, queries/*.sql
├── data/                       # raw/ (copias importadas), processed/ (base SQLite), sample/ (ejemplos ETL)
├── scripts/                    # setup_demo.py, generate_schema_docs.py
├── tests/                      # 60 pruebas Pytest
├── docs/                       # documentación técnica y funcional
├── .streamlit/config.toml      # tema corporativo
├── iniciar.bat                 # arranque con doble clic en Windows
├── requirements.txt · .env.example · .gitignore · CLAUDE.md
```

## Instalación (Windows)

Requisitos: Python 3.11 o 3.12 y Git. No requiere Docker ni servidores de base de datos.

```bash
git clone <url-del-repositorio> Colombiabusinesshub
```

```bash
cd Colombiabusinesshub
```

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

Opcional — crear la base DEMO antes del primer arranque (la app también la crea sola si no existe):

```bash
.venv\Scripts\python scripts\setup_demo.py
```

Opcional — personalizar umbrales: copiar `.env.example` como `.env` y editar los valores.

## Ejecución

```bash
.venv\Scripts\python -m streamlit run app\dashboard.py
```

La aplicación abre en `http://localhost:8501`. También puede hacer doble clic en **`iniciar.bat`**, que crea el
entorno la primera vez y luego inicia la app.

Reconstruir la base DEMO desde cero (borra los datos importados):

```bash
.venv\Scripts\python scripts\setup_demo.py --reset
```

## Modelo de datos

15 tablas en SQLite: `regiones`, `vendedores`, `categorias`, `proveedores`, `productos`, `clientes`, `ventas`,
`detalle_ventas`, `compras`, `detalle_compras`, `inventario` (fotos mensuales), `movimientos_inventario`
(kardex), `gastos_operativos`, `costos` (historial) y `registro_importaciones` (bitácora ETL), con llaves
primarias y foráneas, restricciones CHECK/UNIQUE e índices.

**Montos en pesos colombianos como enteros (BIGINT)**: elimina errores de redondeo de punto flotante; los ratios
se calculan sólo en la capa analítica.

- Diagrama entidad-relación y decisiones de diseño: [docs/modelo_entidad_relacion.md](docs/modelo_entidad_relacion.md)
- Diccionario de datos (generado desde el código): [docs/diccionario_datos.md](docs/diccionario_datos.md)
- DDL: [sql/schema.sql](sql/schema.sql)

Datos DEMO: 22 meses (ene-2025 a oct-2026), ~6.400 facturas, ~28.000 líneas de venta, 180 clientes,
49 productos en 7 categorías, 6 regiones, 12 vendedores, 8 proveedores, kardex e inventario que cuadran entre sí.

## Indicadores

| Indicador | Fórmula |
|---|---|
| Ventas netas | ventas brutas − descuentos − devoluciones |
| Utilidad bruta | ventas netas − costo de ventas |
| Margen bruto | utilidad bruta / ventas netas × 100 |
| Utilidad operacional | utilidad bruta − gastos operativos |
| Margen operacional | utilidad operacional / ventas netas × 100 |
| Ticket promedio | ventas netas / número de facturas |
| Crecimiento | (actual − anterior) / anterior × 100 |
| Rotación de inventario | costo de ventas / inventario promedio |

Cuando falta información (denominador cero, sin periodo comparable, gastos no atribuibles a un filtro) el
indicador se muestra como **N/D** con su explicación, nunca como 0 o un valor engañoso. Metodología completa,
RFM y limitaciones: [docs/metodologia_indicadores.md](docs/metodologia_indicadores.md). Reglas de alertas:
[docs/reglas_alertas.md](docs/reglas_alertas.md). ETL: [docs/proceso_etl.md](docs/proceso_etl.md).

## Pruebas

```bash
.venv\Scripts\python -m pytest
```

60 pruebas sobre bases SQLite temporales (no tocan la base de trabajo): conexión, creación de tablas,
restricciones e integridad referencial, carga DEMO y consistencia kardex/inventario, consultas parametrizadas,
importación CSV y Excel, validaciones y normalización, idempotencia del ETL, fórmulas (ventas netas, utilidad,
márgenes, crecimiento, ticket, rotación), indicadores de inventario y proveedores, RFM, reglas de alertas
(disparo, no disparo y datos insuficientes) y validez de los cinco reportes Excel.

## Limitaciones

- Cifras de **gestión**, no contables: sin depreciaciones, provisiones, impuestos ni gastos financieros.
- El costo de ventas usa el costo unitario vigente a la fecha (costo estándar), no promedio ponderado contable.
- Los gastos operativos no se asignan por región/categoría/producto (con esos filtros el resultado operacional es N/D).
- Las ventas importadas no actualizan el kardex ni las fotos de inventario (v1).
- La segmentación RFM es relativa a la cartera del periodo seleccionado.
- Sin autenticación de usuarios: pensada para uso local o demostración.
- SQLite es adecuado para un usuario / volumen pyme; para uso concurrente se recomienda migrar a un motor servidor.

## Próximas versiones

1. Importación de compras e inventario y actualización del kardex desde ventas importadas.
2. Conectores a bases de datos y exportes de software contable/ERP (SQL Server, PostgreSQL, APIs).
3. Presupuesto vs real y pronóstico de ventas (modelos estadísticos ligeros).
4. Asignación de gastos por centro de costo y rentabilidad por cliente.
5. Autenticación, roles y bitácora de usuarios; despliegue en la nube.
6. Envío programado de reportes y alertas por correo.
