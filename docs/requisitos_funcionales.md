# Requisitos funcionales (v1)

Estado: ✅ implementado y cubierto por pruebas automatizadas · 🟡 implementado, verificado manualmente en la
interfaz · ⏳ pendiente.

## Plataforma y datos

| ID | Requisito | Estado |
|---|---|---|
| RF-01 | Crear la base SQLite y su esquema automáticamente al iniciar | ✅ |
| RF-02 | Generar datos sintéticos DEMO coherentes (22 meses) identificados como DEMO | ✅ |
| RF-03 | Importar CSV y Excel de clientes, productos, ventas y gastos | ✅ |
| RF-04 | Validar columnas, tipos, fechas, cantidades e importes; detectar nulos y duplicados | ✅ |
| RF-05 | Normalizar categorías, regiones y nombres | ✅ |
| RF-06 | Registrar el resultado y los errores de cada importación | ✅ |
| RF-07 | Validar un archivo sin cargarlo | ✅ |
| RF-08 | Consultar registros de cualquier tabla con búsqueda y descarga | 🟡 |
| RF-09 | Ver la estructura de las tablas y controles de calidad de la base | 🟡 |

## Análisis

| ID | Requisito | Estado |
|---|---|---|
| RF-10 | KPIs ejecutivos: ingresos, ventas netas, costo, utilidad bruta, margen, gastos, utilidad operacional, crecimiento, transacciones, ticket | ✅ |
| RF-11 | Comparación contra el periodo anterior de igual duración | ✅ |
| RF-12 | Filtros globales por periodo, región, categoría y producto | ✅ |
| RF-13 | Ventas por producto, categoría, región, vendedor, canal y tipo de cliente | ✅ |
| RF-14 | Ranking de clientes y productos; productos de bajo rendimiento | ✅ |
| RF-15 | Concentración de ingresos (top N, Pareto, HHI) | ✅ |
| RF-16 | Estado de resultados simplificado con variaciones y márgenes | ✅ |
| RF-17 | Rentabilidad por categoría, producto, región, tipo de cliente y vendedor | ✅ |
| RF-18 | Rotación de inventario, días de inventario y cobertura | ✅ |
| RF-19 | Productos bajo mínimo y sin movimiento | ✅ |
| RF-20 | Compras y cumplimiento por proveedor (nivel de servicio, entregas a tiempo) | ✅ |
| RF-21 | Evolución de costos por categoría | ✅ |
| RF-22 | Segmentación RFM, actividad, frecuencia y ranking de clientes | ✅ |

## Alertas y reportes

| ID | Requisito | Estado |
|---|---|---|
| RF-23 | Alertas de caída de ventas, margen, inventario bajo, concentración, costos y gastos | ✅ |
| RF-24 | Cada alerta con motivo, indicador, valor observado, umbral y recomendación | ✅ |
| RF-25 | No generar alertas sin datos suficientes | ✅ |
| RF-26 | Umbrales configurables por variables de entorno | ✅ |
| RF-27 | Reportes comercial, financiero, inventario, clientes y alertas en Excel y CSV | ✅ |

## Requisitos no funcionales

| ID | Requisito | Estado |
|---|---|---|
| RNF-01 | Ejecutable en Windows 11 con 4 GB de RAM, sin Docker ni servidores | ✅ |
| RNF-02 | Montos en COP sin errores de precisión | ✅ |
| RNF-03 | Consultas parametrizadas y sin credenciales en el código | ✅ |
| RNF-04 | Formato colombiano: miles con punto, decimales con coma | 🟡 |
| RNF-05 | Interfaz adaptable (escritorio y pantallas angostas) | 🟡 |

## Pendiente (próximas versiones)

| ID | Requisito | Estado |
|---|---|---|
| RF-28 | Ventas importadas que actualicen kardex e inventario | ⏳ |
| RF-29 | Importación de compras e inventario desde archivo | ⏳ |
| RF-30 | Autenticación y roles de usuario | ⏳ |
| RF-31 | Presupuesto vs real y pronóstico de ventas | ⏳ |
